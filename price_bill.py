"""Price a bill from the command line:  python price_bill.py "demo bills/Bill 1 - residential building.xlsx" [margin%] [--vat]"""
import os
import sys
from boq_agent.pricebook import PriceBook
from boq_agent.pipeline import price_bill
from boq_agent.writer import write_priced_bill
from boq_agent.ai import Resolver

PRICE_LIST = "Price list - steel and metal works.xlsx"

if __name__ == "__main__":
    path = sys.argv[1]
    if path.lower().endswith(".pdf"):
        from boq_agent.pdf_reader import read_pdf_bill, write_bill_xlsx
        lines, pages = read_pdf_bill(path, Resolver())
        os.makedirs("output", exist_ok=True)
        path = write_bill_xlsx(lines, os.path.join("output", os.path.splitext(os.path.basename(path))[0] + ".xlsx"))
        print("Read %d lines from PDF pages %s" % (len(lines), [p + 1 for p in pages]))
    margin = float(sys.argv[2]) / 100 if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 0.0
    ai = None if "--no-ai" in sys.argv else Resolver()
    out = price_bill(path, PriceBook(PRICE_LIST), margin=margin, add_vat="--vat" in sys.argv, resolver=ai)
    os.makedirs("output", exist_ok=True)
    dest = os.path.join("output", os.path.splitext(os.path.basename(path))[0] + " - priced.xlsx")
    write_priced_bill(out, dest, PRICE_LIST)
    s = out["summary"]
    print("%d lines: %d priced, %d to check, %d need you (%d picked by AI). Priced total: %s EGP -> %s"
          % (s["lines"], s["priced"], s["check"], s["ask"], s["by_ai"], format(s["total_priced"], ",.0f"), dest))
    print("AI: %d call(s), %d tokens, model %s %s" % (s["ai_calls"], s["ai_tokens"], s["ai_model"] or "-", s["ai_errors"] or ""))
