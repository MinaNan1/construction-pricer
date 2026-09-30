# BOQ pricing agent for Egyptian contractors

A contractor uploads a tender's bill of quantities (مقايسة), in Excel or PDF, Arabic or English. The agent prices every line from the contractor's own price list, asks only about the lines it can't price, and returns the contractor's own Excel filled in, ready to submit.

## What it does

1. **Reads the bill.** It finds the header, sections and item lines in Excel. For PDFs it finds the bill pages, and Gemini reads only those pages (as images, so broken Arabic PDF text doesn't matter).
2. **Asks two questions:** the margin and whether to add 14% VAT.
3. **Prices lines with plain code first.** It uses Arabic normalization, synonyms and weighted key-word matching, and converts units (kg↔ton, m²↔m³ using the stated thickness). It catches conflicts such as a line that says "per kg" while its unit column says m².
4. **Uses AI only for unclear lines.** A small model (Gemini Flash-Lite, with Groq as backup) picks **one of the 5 closest price-list items or "none"**. It never writes a price. Picks outside the options are ignored, and backup-model picks are always marked for checking.
5. **Leaves the rest to the owner.** Anything uncertain becomes a question with one-click choices or a price box.
6. **Remembers every answer,** so the next bill asks fewer questions.
7. **Looks up missing prices online, on request.** For work that isn't in the price list, one click searches the web (a free search engine, then the small model reads only the price sentences of the top pages). It shows a low–high range, what the price covers and the source links. Numbers not found in the sources are thrown away. It is only a suggestion: the owner accepts it or types their own.
8. **Updates prices from typed text,** e.g. "حديد التسليح بقى 42 ألف". The agent maps the message to the right input, asks for confirmation, and every dependent item is re-priced. The approved price-list workbook is never modified; changes go to a log.

## The five components

| Component | Here |
|---|---|
| LLM | Gemini 3.1 Flash-Lite (free tier), Groq gpt-oss-120b as the backup |
| Harness | `boq_agent/pipeline.py`: code first, AI only picks from candidates, confidence rules, owner in the loop |
| Tools | Excel reader/writer, PDF page finder, formula engine (pycel) that recalculates the price-list workbook |
| Context | `Price list - steel and metal works.xlsx`: 37 items; material prices from the Ministry of Housing bulletin (Aug 2026) plus a reviewer's cost model (Jul 2026) |
| Memory | `boq_agent/memory.py`: SQLite of owner answers, plus a log of price changes |

## Accuracy and cost (`python evaluate.py`)

| Bill | Result | AI use |
|---|---|---|
| Bill 1: residential building, 21 lines, answer key = a reviewer's priced bill | **21/21 priced, 0 wrong**, 100% of the bill value | 1 call, ~1.2k tokens |
| Bill 2: a real Suez Canal Economic Zone tender, 23 lines | **0 wrong confident prices**; 4 priced, 4 priced-but-check, 15 questions (lump sums and work not in the price list); unit conflict caught | 2 calls, ~10k tokens |
| Same tender from its PDF | 23/23 lines read with correct quantities | +1 call, ~12k tokens |

The AI runs on the free tier, so the cost per bill is 0 EGP.

### Robustness test: 5 real tenders the agent had never seen (`test_tenders.py`, `review_tenders.py`)

The set was 2 English UNDP bills (a steel warehouse, 40 flats) and 3 Arabic Suez Canal Zone booklets (a pier, 45 pages of port maintenance, piles and foundations): **505 lines, 7–45 bill pages each.**

| | Result |
|---|---|
| Reading | Every quantity was checked against the PDF's own text: **505/505 read with the right unit and quantity**. The only extra lines were a few items the text-layer check itself missed. |
| Priced outright | **16 lines, 16 correct** |
| Priced but marked "check" | 43 lines: 40 right, 3 rough (e.g. damp-proof course → waterproofing) |
| Asked | 446: 404 work not in the 39-item price list (tiles, doors, electrical, plumbing…), 22 lump sums, the rest unclear |

Problems the test found, all now fixed:
1. With 5 pages per request the model silently skipped pages (50 of 105 lines). It now reads 2 pages per request.
2. Bills longer than 15 pages were cut off, and continuation pages without a header were missed. Pages now keep being read while they still look like bill lines.
3. "30,000" was sometimes read as 30. Quantities are now copied as printed, parsed by code, and checked against the PDF text; if one isn't found, the line is flagged and never priced as certain. Right-to-left PDFs that store Arabic digits backwards are handled.
4. Demolition and sand backfill were priced as excavation (3 wrong prices). A line is now only matched automatically to an item of the same kind of work (excavation / backfill / demolition / repair, taken from its first verb).
5. A summary page listing section names was read as items. Lines with no quantity are dropped.
6. Repeated item numbers broke the questions. Line keys are now unique.
7. Rebar per kg/ton and general metal works per kg had no item. Added CW-26 and MW-07, built from existing rates and marked for the reviewer.

**Honest limit:** accuracy is high where the price list covers the work, but a 39-item list covers only about 12% of a typical tender's lines. The rest comes back as questions, and every answer is remembered.

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      (then add GEMINI_API_KEY and GROQ_API_KEY)
.venv\Scripts\streamlit run app.py
```

Command line: `python price_bill.py "demo bills/Bill 1 - residential building.xlsx" 15` (15% margin; add `--vat`, or `--no-ai`).

`pycel` needs `openpyxl==3.0.10`, and requirements.txt pins it.
