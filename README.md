# BOQ pricing agent for Egyptian contractors

A contractor uploads a tender's bill of quantities (مقايسة), in Excel or PDF, Arabic or English. The agent prices every line from the contractor's own price list, asks only about the lines it can't price, and returns the contractor's own Excel filled in, ready to submit.

## What it does

1. **Reads the bill.** It finds the header, sections and item lines in Excel. For PDFs it finds the bill pages, and Gemini reads only those pages (as images, so broken Arabic PDF text doesn't matter).
2. **Asks two questions:** the margin and whether to add 14% VAT.
3. **Prices lines with plain code first.** It uses Arabic normalization, synonyms and weighted key-word matching, and converts units (kg↔ton, m²↔m³ using the stated thickness). It catches conflicts such as a line that says "per kg" while its unit column says m².
4. **Uses AI only for unclear lines.** A small model (Gemini Flash-Lite, with Groq as backup) picks **one of the 5 closest price-list items or "none"**. It never writes a price. Picks outside the options are ignored, and backup-model picks are always marked for checking.
5. **Leaves the rest to the owner.** Anything uncertain becomes a question with one-click choices or a price box.
6. **Remembers every answer,** so the next bill asks fewer questions.
7. **Updates prices from typed text,** e.g. "حديد التسليح بقى 42 ألف". The agent maps the message to the right input, asks for confirmation, and every dependent item is re-priced. The approved price-list workbook is never modified; changes go to a log.

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

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      (then add GEMINI_API_KEY and GROQ_API_KEY)
.venv\Scripts\streamlit run app.py
```

Command line: `python price_bill.py "demo bills/Bill 1 - residential building.xlsx" 15` (15% margin; add `--vat`, or `--no-ai`).

`pycel` needs `openpyxl==3.0.10`, and requirements.txt pins it.
