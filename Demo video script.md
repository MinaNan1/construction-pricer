# Construction Pricer — demo video script (about 3 minutes)

**Before you record**
1. The site is at **http://localhost:8501**. If it isn't running: open the project folder and run `.venv\Scripts\streamlit run app.py`.
2. Click **"Forget my answers"** in the left panel, so the memory part works.
3. Have ready: `demo bills\Bill 1 - residential building.xlsx`, `sources\SCZone tender 5 of 2020-2021 - port fence and gates.pdf`, and `Price list - steel and metal works.xlsx`.
4. Record the browser window only. Speak in whichever language you're comfortable with.

---

| Time | What you show | What you say |
|---|---|---|
| **0:00** | The site's front page | "Egyptian contractors price every tender by hand. A bill of quantities is 20 to 500 lines, each one needs a price, and it all changes the moment steel moves. It takes days, and one wrong line loses the job." |
| **0:15** | The price list Excel, Price list sheet | "This is the contractor's own price list — 39 items. Material prices come from the Ministry of Housing bulletin, and the rates were reviewed by a practising engineer." |
| **0:35** | Back to the site: upload Bill 1, pick 15%, No VAT, press **Price it** | "I give it a 21-line tender bill. It asks me two things only: my margin, and VAT." |
| **0:45** | The result line and the four metrics | "All 21 lines priced in seconds. Plain code matched 19; the AI only chose between the closest items on 2. One AI call, about 1,200 tokens — free tier, so this bill cost nothing." |
| **1:00** | Scroll the All lines table, point at the Source column | "Every price shows where it came from. It never invents one." |
| **1:10** | Press **Download the priced bill**, open it | "It fills the contractor's own file, ready to submit, plus a report of every decision. Checked against the engineer's own priced bill: 21 out of 21 correct." |
| **1:25** | Upload the port fence **PDF** | "Now a real government tender, as a PDF — Suez Canal Economic Zone." |
| **1:40** | The "I read 23 lines from pages 29–35" message | "It found the bill pages inside a 39-page booklet and read all 23 lines. Every quantity is checked back against the numbers printed in the PDF." |
| **1:55** | Expand question **1.4** (the steel line) | "This line says 'per kilogram' but its unit column says square metres — a real mistake in the real tender. It caught it and asked me instead of guessing." |
| **2:10** | Expand a "Not in your price list yet" line, press **🔎 Look up a price online** | "For work the price list doesn't cover, it searches the web and brings back a price range with the source links — still my decision." |
| **2:30** | Choose an answer, press **Save answer** | "I answer once." |
| **2:40** | In the chat box type `حديد التسليح بقى 42 ألف`, then press **Yes, update** | "And when steel moves, I just say so. It finds the right price, confirms with me, and re-prices everything that uses rebar." |
| **2:55** | Upload Bill 1 again — fewer questions | "It remembers. The next tender asks less." |
| **3:00** | Close on the site | "Tested on 7 real bills, 549 lines. Zero wrong confident prices. Free to run." |

---

**If Gemini is slow on the day** (it was busy during testing): use Bill 1 only — a couple of seconds — and skip the PDF part. The fallback model takes over by itself, it's just slower.
