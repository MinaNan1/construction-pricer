"""Website for the BOQ pricing agent:  .venv\\Scripts\\streamlit run app.py"""
import os
import time
import pandas as pd
import streamlit as st
from boq_agent.pricebook import PriceBook
from boq_agent.pipeline import price_bill, answer, PRICED, CHECK, ASK
from boq_agent.memory import Memory
from boq_agent.units import factor, UNIT_EN, UNIT_AR
from boq_agent.writer import write_priced_bill
from boq_agent.ai import Resolver, read_price_change
from boq_agent.pdf_reader import read_pdf_bill, write_bill_xlsx
from boq_agent.research import research_price

PRICE_LIST = "Price list - steel and metal works.xlsx"
os.makedirs("data/uploads", exist_ok=True)
os.makedirs("output", exist_ok=True)

T = {
    "title": ("BOQ pricing agent", "وكيل تسعير المقايسات"),
    "intro": ("Send me a bill of quantities (Excel) and I'll price every line from your price list. "
              "I only ask you about what I can't price.",
              "ابعتلي المقايسة (Excel) وأنا أسعّر كل البنود من قائمة أسعارك، ومش هسألك غير عن اللي مش عارف أسعّره."),
    "upload": ("Your bill of quantities (Excel or PDF)", "المقايسة بتاعتك (Excel أو PDF)"),
    "pdf_read": ("I read {n} lines from pages {pages} of your PDF and turned them into Excel.",
                 "قريت {n} بند من صفحات {pages} في الـ PDF وحوّلتهم لـ Excel."),
    "pdf_wait": ("Reading the bill pages of your PDF (about 20-40 seconds)...", "بقرا صفحات المقايسة في الـ PDF (حوالي 20-40 ثانية)..."),
    "pdf_fail": ("I couldn't read a bill from this PDF. Please send it as Excel.", "مقدرتش أقرا مقايسة من الـ PDF ده. ابعتها Excel لو سمحت."),
    "q_margin": ("What margin should I add on top of cost?", "أضيف هامش ربح كام على التكلفة؟"),
    "other": ("Other", "نسبة تانية"),
    "q_vat": ("Should the prices include 14% VAT?", "الأسعار تكون شاملة ضريبة القيمة المضافة 14%؟"),
    "yes": ("Yes", "أيوه"), "no": ("No", "لأ"),
    "go": ("Price it", "سعّر"),
    "done": ("I priced **{priced}** of **{lines}** lines from your price list{rem}. {check_txt}{ask_txt}",
             "سعّرت **{priced}** من **{lines}** بند من قائمة أسعارك{rem}. {check_txt}{ask_txt}"),
    "rem": (" ({n} from your earlier answers)", " ({n} من ردودك السابقة)"),
    "by_ai": (" ({n} chosen by the AI)", " ({n} اختارهم الذكاء الاصطناعي)"),
    "check_txt": ("{n} are priced but please check them. ", "{n} متسعّرين بس راجعهم. "),
    "ask_txt": ("**Still open: {n}** - see below.", "**فاضل {n}** محتاجين ردك - تحت."),
    "why_open": ("Of those, {nl} are work that isn't in your price list yet{eg} and {ls} are lump sums. "
                 "I don't guess prices. Give me your price once and I'll remember it for the next bill.",
                 "منهم {nl} شغل مش موجود في قائمة أسعارك لسه{eg} و{ls} مقطوعية. "
                 "أنا مش بخمّن أسعار. قولّي سعرك مرة واحدة وهفتكره في المقايسة الجاية."),
    "all_done": ("Everything is priced. Download your file below.", "كل البنود اتسعّرت. نزّل الملف تحت."),
    "total": ("Total of priced lines", "إجمالي البنود المسعّرة"),
    "time": ("Time", "الوقت"), "ai": ("AI calls", "استدعاءات الذكاء الاصطناعي"), "tokens": ("AI tokens", "توكنز الذكاء الاصطناعي"),
    "questions": ("Questions for you", "أسئلة ليك"),
    "which": ("Which item is it?", "البند ده أنهي واحد؟"),
    "which_unit": ("The line and its unit column disagree. Which unit is right?", "الوصف وعمود الوحدة مختلفين. أنهي وحدة صح؟"),
    "own": ("My own cost per unit (before margin)", "تكلفتي أنا للوحدة (قبل الهامش)"),
    "lump": ("Your price for this lump sum (before margin)", "سعرك للمقطوعية دي (قبل الهامش)"),
    "research": ("🔎 Look up a price online", "🔎 دوّر على سعر أونلاين"),
    "researching": ("Searching the web and reading the price pages (about 20-40 seconds)...",
                    "بدوّر على النت وبقرا صفحات الأسعار (حوالي 20-40 ثانية)..."),
    "research_none": ("I couldn't find a price I can trust online for this. Please enter yours.",
                      "ملقتش سعر أقدر أثق فيه على النت للبند ده. دخّل سعرك."),
    "research_found": ("Found online: **{low:,.0f} to {high:,.0f} EGP per {unit}** (typical {typical:,.0f}). Covers: {includes}.",
                       "لقيت على النت: **من {low:,.0f} لـ {high:,.0f} جنيه لكل {unit}** (المعتاد {typical:,.0f}). بيشمل: {includes}."),
    "use_research": ("Use {p:,.0f} as my cost", "استخدم {p:,.0f} كتكلفتي"),
    "research_unit": ("These prices are per {unit}, not the bill's unit, so I can't use them directly.",
                      "الأسعار دي لكل {unit} مش بوحدة البند، فمينفعش أستخدمها على طول."),
    "save": ("Save answer", "احفظ الرد"),
    "cant": ("units don't fit", "الوحدة مش مناسبة"),
    "download": ("Download the priced bill", "نزّل المقايسة المسعّرة"),
    "lines": ("All lines", "كل البنود"),
    "sidebar_prices": ("Update a price", "تحديث سعر"),
    "which_price": ("Which price changed?", "أنهي سعر اتغيّر؟"),
    "new_value": ("New value", "القيمة الجديدة"),
    "apply": ("Update all prices", "حدّث كل الأسعار"),
    "updated": ("Updated. Every item that uses it was re-priced.", "اتحدّث. كل البنود اللي بتستخدمه اتسعّرت من جديد."),
    "memory": ("Answers I remember: {n}", "ردود فاكرها: {n}"),
    "forget": ("Forget my answers", "امسح ردودي"),
    "chat_ph": ("Tell me if a price changed, e.g. \"rebar is now 42,000\"", "قولّي لو سعر اتغيّر، مثلاً \"حديد التسليح بقى 42 ألف\""),
    "apply_change": ("Yes, update", "أيوه، حدّث"),
    "cancel": ("Cancel", "إلغاء"),
    "big": ("That's a big change from the current price - please double-check.", "ده تغيير كبير عن السعر الحالي - اتأكد تاني."),
    "no_ai": ("I can't reach the AI right now. Use \"Update a price\" in the side panel.", "مش قادر أوصل للذكاء الاصطناعي دلوقتي. استخدم \"تحديث سعر\" في الجنب."),
    "changed": ("Prices changed in this app: {n}", "أسعار اتغيّرت في البرنامج: {n}"),
    "reset": ("Reset to the price list", "رجّع أسعار القائمة"),
    "status": ({PRICED: "Priced", CHECK: "Please check", ASK: "Needs you"},
               {PRICED: "تم التسعير", CHECK: "راجع", ASK: "يحتاج ردك"}),
}


def t(key, **kw):
    s = T[key][1 if st.session_state.lang == "ar" else 0]
    return s.format(**kw) if kw else s


@st.cache_resource
def load():
    return PriceBook(PRICE_LIST, "data/price_changes.json"), Memory("data/memory.sqlite")


st.set_page_config(page_title="BOQ pricing agent", page_icon="📋", layout="wide")
st.session_state.setdefault("lang", "en")
with st.sidebar:
    st.session_state.lang = "ar" if st.radio("Language / اللغة", ["English", "العربية"],
                                             index=1 if st.session_state.lang == "ar" else 0) == "العربية" else "en"
if st.session_state.lang == "ar":
    st.markdown("<style>.main .block-container, [data-testid='stSidebar'] {direction: rtl; text-align: right;}</style>",
                unsafe_allow_html=True)

pb, mem = load()
st.title(t("title"))
with st.chat_message("assistant"):
    st.write(t("intro"))


def run(path):
    start = time.time()
    st.session_state.out = price_bill(path, pb, margin=st.session_state.margin, add_vat=st.session_state.vat,
                                      memory=mem, resolver=Resolver())
    st.session_state.seconds = time.time() - start


# ---- sidebar: update a material/labour price, memory ----
with st.sidebar:
    st.subheader(t("sidebar_prices"))
    ins = pb.inputs()
    labels = ["%s (%s)" % (i["ar"] if st.session_state.lang == "ar" else i["en"], i["unit"]) for i in ins]
    k = st.selectbox(t("which_price"), range(len(ins)), format_func=lambda i: labels[i])
    new = st.number_input(t("new_value"), value=ins[k]["value"], step=100.0 if ins[k]["value"] > 100 else 0.01)
    if st.button(t("apply")):
        pb.change_input(ins[k]["address"], new, ins[k]["en"])
        if "path" in st.session_state:
            run(st.session_state.path)
        st.success(t("updated"))
    if pb.changes():
        st.caption(t("changed", n=len(pb.changes())))
        if st.button(t("reset")):
            os.remove(pb.changes_path)
            load.clear()
            st.rerun()
    st.divider()
    st.caption(t("memory", n=mem.count()))
    if st.button(t("forget")):
        mem.forget_all()
        st.rerun()

# ---- step 1 and 2: the bill and two questions ----
up = st.file_uploader(t("upload"), type=["xlsx", "pdf"], key="bill")
if up:
    path = os.path.join("data/uploads", up.name)
    with open(path, "wb") as f:
        f.write(up.getbuffer())
    if path.lower().endswith(".pdf"):
        xlsx = os.path.splitext(path)[0] + ".xlsx"
        if st.session_state.get("pdf_done") != path:
            with st.spinner(t("pdf_wait")):
                ai = Resolver()
                lines, pages = read_pdf_bill(path, ai)
            st.session_state.pdf_done = path
            st.session_state.pdf_info = (len(lines), pages, ai.tokens)
            if lines:
                write_bill_xlsx(lines, xlsx, up.name)
        n, pages, tok = st.session_state.pdf_info
        with st.chat_message("assistant"):
            if n:
                st.write(t("pdf_read", n=n, pages="%d-%d" % (pages[0] + 1, pages[-1] + 1)) + " (%s tokens)" % "{:,}".format(tok))
            else:
                st.write(t("pdf_fail"))
        path = xlsx if n else None
    c1, c2 = st.columns(2)
    with c1:
        m = st.radio(t("q_margin"), ["10%", "15%", "20%", t("other")], horizontal=True, index=1)
        margin = (st.number_input("%", value=12.0, step=1.0) if m == t("other") else float(m[:-1])) / 100
    with c2:
        vat = st.radio(t("q_vat"), [t("no"), t("yes")], horizontal=True) == t("yes")
    if path and st.button(t("go"), type="primary"):
        st.session_state.update(margin=margin, vat=vat, path=path)
        run(path)

# ---- step 3: results, questions, download ----
out = st.session_state.get("out")
if out:
    s = out["summary"]
    with st.chat_message("assistant"):
        if s["ask"] == 0 and s["check"] == 0:
            st.write(t("all_done"))
        else:
            st.markdown(t("done", priced=s["priced"] + s["check"], lines=s["lines"],
                          rem=(t("rem", n=s["remembered"]) if s["remembered"] else "")
                          + (t("by_ai", n=s["by_ai"]) if s["by_ai"] else ""),
                          check_txt=t("check_txt", n=s["check"]) if s["check"] else "",
                          ask_txt=t("ask_txt", n=s["ask"]) if s["ask"] else ""))
            if s["not_in_list"] or s["lump"]:
                st.write(t("why_open", nl=s["not_in_list"], ls=s["lump"], eg=""))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("total"), "{:,.0f} EGP".format(s["total_priced"]))
    c2.metric(t("time"), "%.1f s" % st.session_state.get("seconds", 0))
    c3.metric(t("ai"), s["ai_calls"])
    c4.metric(t("tokens"), "{:,}".format(s["ai_tokens"]))

    todo = [r for r in out["results"] if r["status"] in (ASK, CHECK)]
    if todo:
        st.subheader(t("questions"))
    for r in todo:
        head = "%s  |  %s  |  %s %s" % (r["key"], r["desc"][:90], "{:,.0f}".format(r["qty"] or 0), r["unit_raw"] or "")
        with st.expander(head, expanded=r["status"] == ASK):
            st.write(r["desc"])
            for n in r["notes"]:
                st.caption(n[st.session_state.lang])
            if r["status"] == ASK and r["unit_used"] != "ls":
                found_all = st.session_state.setdefault("research", {})
                if st.button(t("research"), key="r" + r["key"]):
                    with st.spinner(t("researching")):
                        found_all[r["key"]] = research_price(r, Resolver()) or {"none": True}
                found = found_all.get(r["key"])
                if found and found.get("none"):
                    st.info(t("research_none"))
                elif found:
                    st.info(t("research_found", low=found["low"], high=found["high"], typical=found["typical"],
                              unit=found["unit"], includes=found["includes"]) + "  \n" + found["note_" + st.session_state.lang])
                    for src in found["sources"][:4]:
                        st.markdown("- [%s](%s)" % (src["title"][:80].replace("[", "").replace("]", ""), src["url"]))
                    if found["unit_ok"]:
                        if st.button(t("use_research", p=found["typical"]), key="u" + r["key"]):
                            answer(out, r["key"], pb, mem, cost=found["typical"],
                                   source="Web research, accepted by you: " + ", ".join(s["url"] for s in found["sources"][:2]))
                            st.rerun()
                    else:
                        st.warning(t("research_unit", unit=found["unit"]))
            if any(n["kind"] == "conflict" for n in r["notes"]) and r.get("unit_desc"):
                from boq_agent.units import parse_unit
                units = list(dict.fromkeys(u for u in (parse_unit(r["unit_raw"]), r["unit_desc"]) if u))
                names = UNIT_AR if st.session_state.lang == "ar" else UNIT_EN
                guess = parse_unit((r.get("ai") or {}).get("unit_guess"))
                r["unit_used"] = st.radio(t("which_unit"), units, format_func=lambda u: names.get(u, u), horizontal=True,
                                          index=units.index(guess) if guess in units else len(units) - 1, key="u_" + r["key"])
            opts, codes = [], []
            if r["unit_used"] != "ls":
                for c in r["candidates"]:
                    item = pb.by_code[c["code"]]
                    f, _ = factor(r["unit_used"], item["unit"], r["desc"])
                    if f:                      # only items whose units fit this line
                        opts.append("%s - %s (%s)" % (c["code"], item["name_ar"], "{:,.2f}".format(pb.price(c["code"]) * f)))
                        codes.append(c["code"])
            ai = r.get("ai") or {}
            confident = r["status"] == CHECK or (ai.get("confidence") in ("high", "medium") and codes
                                                  and ai.get("choice") == codes[0])
            opts.append(t("own") if r["unit_used"] != "ls" else t("lump"))
            codes.append("own")
            choice = st.radio(t("which"), range(len(opts)), format_func=lambda i: opts[i], key="c" + r["key"],
                              index=0 if confident else len(opts) - 1) if len(opts) > 1 else 0
            cost = None
            if codes[choice] == "own":
                cost = st.number_input(opts[-1], min_value=0.0, step=10.0, key="p" + r["key"])
            if st.button(t("save"), key="s" + r["key"]):
                if codes[choice] == "own":
                    answer(out, r["key"], pb, mem, cost=cost)
                else:
                    answer(out, r["key"], pb, mem, code=codes[choice])
                st.rerun()

    st.subheader(t("lines"))
    st.dataframe(pd.DataFrame([{
        "#": r["key"], "Description": r["desc"][:120], "Unit": r["unit_raw"], "Qty": r["qty"],
        "Status": T["status"][1 if st.session_state.lang == "ar" else 0][r["status"]],
        "Code": r["code"], "Unit price": r["unit_price"], "Total": r["total"], "Source": r["source"],
    } for r in out["results"]]), use_container_width=True, hide_index=True)

    dest = os.path.join("output", os.path.splitext(os.path.basename(st.session_state.path))[0] + " - priced.xlsx")
    write_priced_bill(out, dest, PRICE_LIST, lang=st.session_state.lang)
    with open(dest, "rb") as f:
        st.download_button(t("download"), f.read(), file_name=os.path.basename(dest), type="primary")

# ---- price changes typed in plain words ----
msg = st.chat_input(t("chat_ph"))
if msg:
    ai = Resolver()
    st.session_state.pending = read_price_change(ai, msg, pb.inputs()) if ai.available() else None
    st.session_state.pending_msg = msg
    if st.session_state.pending is None:
        st.session_state.pending = {"updates": [], "error": True}
p = st.session_state.get("pending")
if p:
    ins = pb.inputs()
    lang = st.session_state.lang
    with st.chat_message("user"):
        st.write(st.session_state.pending_msg)
    with st.chat_message("assistant"):
        if p.get("error"):
            st.write(t("no_ai"))
        elif p["updates"]:
            st.write(p["understood_" + lang])
            for u in p["updates"]:
                x = ins[u["id"]]
                st.write("- %s: %s → **%s** %s" % (x["ar"] if lang == "ar" else x["en"], "{:,.2f}".format(x["value"]),
                                                    "{:,.2f}".format(u["new_value"]), x["unit"]))
                if x["value"] and not 0.5 <= u["new_value"] / x["value"] <= 2:
                    st.warning(t("big"))
            c1, c2 = st.columns(2)
            if c1.button(t("apply_change"), type="primary"):
                for u in p["updates"]:
                    pb.change_input(ins[u["id"]]["address"], u["new_value"], ins[u["id"]]["en"])
                st.session_state.pending = None
                if "path" in st.session_state:
                    run(st.session_state.path)
                st.rerun()
            if c2.button(t("cancel")):
                st.session_state.pending = None
                st.rerun()
        else:
            st.write(p.get("question_" + lang) or p.get("understood_" + lang))
