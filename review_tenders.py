"""Review the robustness test: reading accuracy against each PDF's own text layer (unit + quantity of every
line), and every line the agent priced, listed for a manual correctness check."""
import collections
import glob
import json
import os
import re
import sys
import pymupdf
from boq_agent.units import parse_unit

NUM = re.compile(r"^[\d,]+(?:\.\d+)?$")


def truth_pairs(pdf, pages):
    """(unit, qty) of every line whose unit cell sits right before its quantity in the text layer."""
    doc = pymupdf.open(pdf)
    out = []
    for p in pages:
        ls = [l.strip() for l in doc[p - 1].get_text().split("\n") if l.strip()]
        for i in range(len(ls) - 1):
            u = parse_unit(ls[i])
            if u and len(ls[i]) <= 12 and NUM.match(ls[i + 1]):
                out.append((u, float(ls[i + 1].replace(",", ""))))
    return out


for path in sorted(glob.glob("test tenders/results/*.json")):
    r = json.load(open(path, encoding="utf-8"))
    name = os.path.basename(path)[:-5]
    truth = collections.Counter(truth_pairs(r["pdf"], r["pages"]))
    read = collections.Counter((parse_unit(l["unit"]), float(l["qty"])) for l in r["raw_lines"])
    s = r["summary"]
    print("=" * 110)
    print("%s | pages %d-%d | text-layer lines %d | read %d | matching unit+qty %d | missed %d | extra %d | "
          "read %ds, %d calls, %d tokens, errors %d"
          % (name, r["pages"][0], r["pages"][-1], sum(truth.values()), sum(read.values()), sum((truth & read).values()),
             sum((truth - read).values()), sum((read - truth).values()), r["read_seconds"], r["read_calls"],
             r["read_tokens"], len(r["read_errors"])))
    print("   priced %s | check %s | ask %s (not in list %s, lump %s) | AI calls %s, tokens %s | price error: %s"
          % (s.get("priced"), s.get("check"), s.get("ask"), s.get("not_in_list"), s.get("lump"),
             s.get("ai_calls"), s.get("ai_tokens"), r["price_error"]))
    if "-v" in sys.argv:
        print("   missed:", list((truth - read).elements())[:12], "| extra:", list((read - truth).elements())[:12])
        for x in r["results"]:
            if x["status"] in ("priced", "check"):
                print("   %-6s %-6s %-6s %-5s | %s" % (x["key"], x["status"], x["code"], x["unit_used"], x["desc"][:95]))
