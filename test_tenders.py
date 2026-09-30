"""Robustness test on real tenders the agent has never seen: read each PDF bill, price it, save everything
to "test tenders/results/" for review."""
import glob
import json
import os
import sys
import time
from boq_agent.ai import Resolver
from boq_agent.pdf_reader import read_pdf_bill, write_bill_xlsx
from boq_agent.pricebook import PriceBook
from boq_agent.pipeline import price_bill

OUT = "test tenders/results"
os.makedirs(OUT, exist_ok=True)
pb = PriceBook("Price list - steel and metal works.xlsx")
for pdf in sorted(glob.glob("test tenders/*.pdf")):
    name = os.path.splitext(os.path.basename(pdf))[0]
    old = os.path.join(OUT, name + ".json")
    read_ai, t = Resolver(), time.time()
    if "--reuse" in sys.argv and any(k in name for k in sys.argv[sys.argv.index("--reuse") + 1:]) and os.path.exists(old):
        prev = json.load(open(old, encoding="utf-8"))        # keep an earlier reading (saves time and quota)
        lines, pages = prev["raw_lines"], [p - 1 for p in prev["pages"]]
    else:
        lines, pages = read_pdf_bill(pdf, read_ai)
    read_s = time.time() - t
    xlsx = write_bill_xlsx(lines, os.path.join(OUT, name + ".xlsx"), name)
    price_ai, t = Resolver(), time.time()
    try:
        out = price_bill(xlsx, pb, resolver=price_ai)
        results = [{k: r[k] for k in ("key", "no", "section", "desc", "unit_raw", "unit_used", "qty", "status", "code", "unit_price", "source")}
                   | {"notes": [n["en"] for n in r["notes"]], "ai": r.get("ai")} for r in out["results"]]
        summary = out["summary"]
        err = None
    except Exception as e:
        results, summary, err = [], {}, "%s: %s" % (type(e).__name__, e)
    price_s = time.time() - t
    report = {"pdf": pdf, "pages": [p + 1 for p in pages], "lines_read": len(lines), "read_seconds": round(read_s),
              "read_calls": read_ai.calls, "read_tokens": read_ai.tokens, "read_errors": read_ai.errors,
              "price_seconds": round(price_s), "price_error": err,
              "summary": {k: v for k, v in summary.items() if k != "ai_errors"}, "price_ai_errors": summary.get("ai_errors"),
              "raw_lines": lines, "results": results}
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    s = report["summary"]
    print("%s | pages %d | read %d lines in %ds (%d calls, %d tok, %d errors) | priced %s check %s ask %s | %s"
          % (name[:34], len(pages), len(lines), read_s, read_ai.calls, read_ai.tokens, len(read_ai.errors),
             s.get("priced"), s.get("check"), s.get("ask"), err or "ok"), flush=True)
