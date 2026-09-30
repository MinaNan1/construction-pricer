"""Price a whole bill: read it, reuse remembered answers, match each line, let the AI pick among the closest
items for unclear lines, convert units, run the checks, and decide what to ask the owner."""
from .reader import read_bill
from .matcher import Matcher
from .units import unit_from_description, factor, LS, UNIT_AR, UNIT_EN

PRICED, CHECK, ASK = "priced", "check", "ask"   # priced / priced but please confirm / needs the owner
VAT = 0.14
AI_CANDIDATES = 5
AI_MIN_COVERAGE = 0.30   # an AI pick is priced outright only if the line shares at least this much of the item's key words


def note(res, kind, en, ar):
    res["notes"].append({"kind": kind, "en": en, "ar": ar})


def has_note(res, kind):
    return any(n["kind"] == kind for n in res["notes"])


def _uplift(margin, add_vat):
    return (1 + margin) * ((1 + VAT) if add_vat else 1)


def price_from_code(res, code, pricebook, uplift, source=None, status=None):
    """Price a line with a price-list item, converting units. Returns False if the units can't be converted."""
    item = pricebook.by_code[code]
    f, how = factor(res["unit_used"], item["unit"], res["desc"])
    if f is None:
        note(res, "units", "%s: %s." % (code, how["en"]), "%s: %s." % (code, how["ar"]))
        return False
    base = pricebook.price(code) * f
    converted = f != 1.0 and res["unit_used"] not in ("kg", "ton")
    res.update(code=code, item=item["name_ar"], base_price=base, unit_price=round(base * uplift, 2),
               source=source or pricebook.source(code), status=status or (CHECK if converted else PRICED))
    if how:
        note(res, "converted", how["en"] + ".", how["ar"] + ".")
    res["total"] = round(res["unit_price"] * res["qty"], 2) if res["qty"] else None
    return True


def price_from_owner(res, cost, uplift, source):
    res.update(base_price=cost, unit_price=round(cost * uplift, 2), source=source, status=PRICED)
    res["total"] = round(res["unit_price"] * res["qty"], 2) if res["qty"] else None


def summarize(results, margin, add_vat, ai=None):
    s = {
        "lines": len(results),
        "priced": sum(r["status"] == PRICED for r in results),
        "check": sum(r["status"] == CHECK for r in results),
        "ask": sum(r["status"] == ASK for r in results),
        "remembered": sum(r["source"].startswith("Your") for r in results),
        "by_ai": sum(r["source"].startswith("AI") for r in results),
        "not_in_list": sum(r["status"] == ASK and has_note(r, "not_in_list") for r in results),
        "lump": sum(r["status"] == ASK and has_note(r, "lump") for r in results),
        "total_priced": round(sum(r["total"] or 0 for r in results if r["status"] != ASK), 2),
        "margin": margin, "vat": add_vat,
        "ai_calls": 0, "ai_tokens": 0, "ai_model": "", "ai_errors": [],
    }
    if ai:
        s.update(ai_calls=ai.calls, ai_tokens=ai.tokens, ai_model=ai.model_used, ai_errors=ai.errors)
    return s


def price_bill(path, pricebook, margin=0.0, add_vat=False, matcher=None, memory=None, resolver=None):
    bill = read_bill(path)
    matcher = matcher or Matcher(pricebook)
    uplift = _uplift(margin, add_vat)
    results = []
    for line in bill["lines"]:
        desc_unit = unit_from_description(line["desc"])
        res = dict(line, status=ASK, code=None, item=None, base_price=None, unit_price=None, total=None,
                   source="", notes=[], candidates=[], unit_used=line["unit"] or desc_unit)
        if line["unit"] and desc_unit and line["unit"] != desc_unit:
            note(res, "conflict",
                 "Unit conflict: the description says per %s but the unit column says %s." % (UNIT_EN[desc_unit], line["unit_raw"]),
                 "تعارض في الوحدة: الوصف بيقول بال%s لكن عمود الوحدة مكتوب فيه %s." % (UNIT_AR[desc_unit], line["unit_raw"]))
        if line["qty"] is None or line["qty"] <= 0:
            note(res, "qty", "No quantity.", "مفيش كمية.")
        conflict = has_note(res, "conflict")

        known = memory.recall(line["desc"], res["unit_used"]) if memory and not conflict else None
        if known:
            src = "Your answer from %s" % known["saved"]
            if not (known["code"] and price_from_code(res, known["code"], pricebook, uplift, src, PRICED)) \
                    and known["price"] is not None:
                price_from_owner(res, known["price"], uplift, src)
            results.append(res)
            continue
        if res["unit_used"] == LS:
            note(res, "lump", "Lump sum: needs your price.", "مقطوعية: محتاج سعرك.")
            results.append(res)
            continue

        cands = matcher.candidates(dict(line, unit=res["unit_used"]), k=AI_CANDIDATES)
        res["candidates"] = cands
        if matcher.decide(cands) == "auto" and not conflict:
            price_from_code(res, cands[0]["code"], pricebook, uplift)
        results.append(res)

    unclear = [r for r in results if r["status"] == ASK and r["candidates"]]
    if unclear and resolver and resolver.available():
        _ai_step(unclear, pricebook, uplift, resolver)
    for r in results:
        if r["status"] == ASK and r["candidates"] and not has_note(r, "ai") and not has_note(r, "not_in_list"):
            note(r, "unsure", "Not sure which price-list item this is. Closest: %s."
                 % ", ".join(c["code"] for c in r["candidates"][:3]),
                 "مش متأكد البند ده أنهي بند في قائمة الأسعار. الأقرب: %s." % "، ".join(c["code"] for c in r["candidates"][:3]))
    return {"bill": bill, "results": results, "summary": summarize(results, margin, add_vat, resolver),
            "margin": margin, "vat": add_vat, "resolver": resolver}


def _ai_step(unclear, pricebook, uplift, resolver):
    """Let the model pick among the closest items. high -> priced, medium -> priced but check, else ask."""
    payload = []
    for r in unclear:
        payload.append({
            "key": r["key"], "text": r["desc"][:350], "unit": r["unit_raw"], "section": r["section"],
            "unit_conflict": next((n["en"] for n in r["notes"] if n["kind"] == "conflict"), ""),
            "candidates": [{"code": c["code"], "name": pricebook.by_code[c["code"]]["name_ar"],
                            "name_en": pricebook.by_code[c["code"]]["name_en"],
                            "unit": pricebook.by_code[c["code"]]["unit"]} for c in r["candidates"]],
        })
    answers = resolver.resolve(payload)
    if not answers:
        for r in unclear:
            note(r, "ai_down", "The AI check isn't available right now, so please choose.",
                 "مراجعة الذكاء الاصطناعي مش متاحة دلوقتي، اختار انت.")
        return
    for r in unclear:
        a = answers.get(r["key"])
        if not a:
            continue
        valid = {c["code"] for c in r["candidates"]}
        choice = a.get("choice") if a.get("choice") in valid else None
        if choice and a.get("confidence") in ("high", "medium"):
            # a confident AI pick goes first in the options shown to the owner
            r["candidates"].sort(key=lambda c: c["code"] != choice)
        r["ai"] = a
        if a.get("choice") not in valid | {"none", "", None}:
            note(r, "ai", "The AI answered %s, which was not one of the options, so I ignored it." % a.get("choice"),
                 "الذكاء الاصطناعي اختار %s وده مش من الاختيارات، فتجاهلته." % a.get("choice"))
            continue
        if not choice:
            note(r, "not_in_list", "Not in your price list yet: %s" % a.get("reason_en", ""),
                 "مش موجود في قائمة أسعارك لسه: %s" % a.get("reason_ar", ""))
            continue
        note(r, "ai", "AI: %s" % a.get("reason_en", ""), "الذكاء الاصطناعي: %s" % a.get("reason_ar", ""))
        if choice and a.get("confidence") in ("high", "medium") and not has_note(r, "conflict"):
            cov = next(c["coverage"] for c in r["candidates"] if c["code"] == choice)
            status = PRICED if a["confidence"] == "high" and cov >= AI_MIN_COVERAGE else CHECK
            price_from_code(r, choice, pricebook, uplift,
                            "AI choice (%s confidence): %s" % (a["confidence"], pricebook.source(choice)), status)
            if r["status"] == PRICED and has_note(r, "converted"):
                r["status"] = CHECK


def answer(out, key, pricebook, memory=None, code=None, cost=None):
    """Apply the owner's answer to one line (a price-list item or their own cost per unit) and remember it."""
    res = next(r for r in out["results"] if r["key"] == key)
    uplift = _uplift(out["margin"], out["vat"])
    res["notes"] = [n for n in res["notes"] if n["kind"] not in ("unsure", "ai_down", "converted")]
    if code:
        if not price_from_code(res, code, pricebook, uplift, "Your choice: %s" % pricebook.source(code), PRICED):
            return False
    else:
        price_from_owner(res, float(cost), uplift, "Your price")
    if memory:
        memory.remember(res["desc"], res["unit_used"], code=code, price=None if code else float(cost))
    out["summary"] = summarize(out["results"], out["margin"], out["vat"], out.get("resolver"))
    return True
