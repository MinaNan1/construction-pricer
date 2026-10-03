# Agents at Work — submission answers (Construction Pricer)

Copy each answer into the form. Questions 3–5 I couldn't read in the video, so check the wording on screen and use the matching paragraph below.

---

### 1. Full name
Your name.

### 2. Email address
Your email.

---

## Your Agent

### Agent name
**Construction Pricer** (مُسعِّر المقايسات)

### What problem does it solve / what does it do?
Egyptian contractors price every tender by hand. A bill of quantities runs from 20 to 500 lines, and someone has to find a price for each one, convert units, and redo the whole thing every time steel moves. It takes days per tender, and a mistake on one line can lose the job or the margin.

Construction Pricer takes the tender's bill of quantities — Excel or PDF, Arabic or English — and prices every line from the contractor's own price list. It asks only about the lines it genuinely cannot price, remembers each answer for the next tender, and returns the contractor's own file filled in and ready to submit.

### Who is it for?
Small and medium Egyptian contracting companies: the ones who bid on government and private tenders but cannot afford a full-time estimator.

### 6. What kind of agent is it?
Tick **Workflow / task automation** and **Data analysis / reporting**, then tick **Other** and write:
> Construction tender pricing — reads a bill of quantities and prices it from the contractor's own price list.

---

## How You Built It

### 7. Which tools, frameworks, or models did you use?
Python, with Streamlit for the web app.

Models (both on free tiers, so a priced bill costs 0 EGP):
- **Google Gemini 3.1 Flash-Lite** — matches unclear lines, reads bill pages out of PDFs, and understands typed price updates.
- **Groq (openai/gpt-oss-120b)** — automatic fallback whenever Gemini is unavailable.

Libraries: openpyxl and **pycel** (recalculates the contractor's own price-list workbook in Python, so one price change updates every item exactly as Excel would), PyMuPDF for PDFs, RapidFuzz for text matching, SQLite for memory, ddgs for the optional web price lookup.

No agent framework. The loop is written directly, so every decision point is explicit and testable.

### 8. Briefly, how does your agent work?
1. **Reads the bill.** It finds the header, sections and item lines in Excel. For a PDF it locates the bill pages, then sends only those pages to Gemini as images (Arabic PDF text layers are often scrambled). Quantities are copied as printed, parsed in code, and checked back against the numbers printed in the PDF — anything that doesn't match is flagged and never priced as certain.
2. **Asks two questions:** profit margin and whether to add 14% VAT.
3. **Prices in plain code first.** Arabic normalisation, synonyms and rarity-weighted keyword matching, plus unit conversion (kg↔ton, m²↔m³ using the thickness stated in the line). It refuses to match across different kinds of work — demolition is not excavation — and catches contradictions such as a line reading "per kg" while its unit column says m².
4. **AI only for what's left.** The model picks **one of the 5 closest price-list items, or "none"**. It never writes a price. Anything outside those options is discarded, and fallback-model picks are always marked for review.
5. **The owner decides the rest.** Unpriced lines become one-click questions, or an optional web lookup that returns a price range with source links.
6. **It remembers.** Every answer is stored, so the next tender asks fewer questions.
7. **Output:** the contractor's own Excel with the rate column filled, plus a report showing where each price came from.

Accuracy is enforced by design: the agent either has a source for a price, or it asks.

### 9. Did you build this agent yourself?
**Mostly me, with some help or guidance.** — I directed the work and made every design and pricing decision; I used Claude Code as a coding assistant. (Pick the answer that matches how you see it, but this is the honest one.)

---

## Links & Proof

### 10. GitHub repository (public link)
Paste the link after the repo is pushed.

### 11. Live demo or video
Choose **Upload video** and upload your recording (or paste a link if you put it on Drive/YouTube).

### 13. Any supporting documents (optional)
Worth attaching: `Price list - steel and metal works.xlsx` — it shows the price sources and the build-up behind every rate.

### 16. This is my own work and I built it during the prep month.
**Yes.**

---

## Numbers worth quoting anywhere the form gives you room

- Tested on **7 real bills of quantities, 549 lines**: 2 English UNDP tenders, 4 Arabic Suez Canal Economic Zone tenders, and one engineer-priced building bill.
- **505/505 quantities read correctly** from 5 unseen tenders, each one verified against the PDF's own printed numbers.
- **Zero wrong confident prices** across every test.
- On the engineer-priced bill: **21/21 lines priced with no questions, all correct**, matching his own prices exactly.
- Cost per bill: **about 2 AI calls, free tier, 0 EGP.**
- Price sources: Ministry of Housing building-materials bulletin (August 2026) plus Egyptian market rates reviewed by a practising engineer.
