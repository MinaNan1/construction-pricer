"""PDF bills: find the pages that hold the bill of quantities, have Gemini read only those pages into lines,
and write them to an Excel bill that the normal pipeline prices."""
import json
import re
import pymupdf
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from .text import normalize

PDF_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest"]
MAX_PAGES = 60
PAGES_PER_REQUEST = 2   # with 5 pages the model silently skipped whole pages; 2 read 105/105 lines
_BOQ_WORDS = ("الكميه", "الوحده", "الفيه", "بيان الاعمال", "quantity", "unit", "rate")
# what bill lines look like on continuation pages that don't repeat the table header
_LINE_UNITS = re.compile(r"(?:^|\s)(?:م3|م2|م ط|مط|عدد|طن|كجم|بالمتر|بالعدد|بالمقطوعيه|مقطوعيه|m3|m2|lm|ls|nos?|kg|ton|item)(?=\s|$)")

SYSTEM = (
    "You read a bill of quantities (جدول الكميات / مقايسة) from tender pages. Return every priced line in order: "
    "no (the item number as printed), section (the section title it is under, e.g. \"أولاً: الأعمال المدنية\"), "
    "desc (the full item description, copied word for word; join text broken across lines; fix only letters that "
    "are clearly broken by the PDF), unit (as printed in the unit column), qty (the quantity copied exactly as "
    "printed, with its commas and dots, e.g. \"30,000\" or \"2.75\"; \"0\" if there is none). Skip headers, totals and "
    "blank price columns, and skip summary / recap tables that only list section names. Do not invent or "
    "translate anything. These pages may be part of a longer bill: if the "
    "first item continues from an earlier page, set continued=true on it; if the last item's text runs onto a later "
    "page and its quantity is not on these pages, set continues=true and qty=0. JSON only."
)
SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
        "no": {"type": "string"}, "section": {"type": "string"}, "desc": {"type": "string"},
        "unit": {"type": "string"}, "qty": {"type": "string"},
        "continued": {"type": "boolean"}, "continues": {"type": "boolean"}},
        "required": ["no", "section", "desc", "unit", "qty", "continued", "continues"]}}},
    "required": ["lines"],
}


def parse_qty(text):
    """A printed quantity -> number. "30,000" and "30.000" (dot before exactly 3 digits and more digits before it
    is ambiguous, so only commas count as thousands) -> 30000; "2.75" -> 2.75; "1,5" -> 1.5; Arabic digits too."""
    digits = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
    s = str(text).translate(digits).replace(" ", "").replace(" ", "") if text is not None else ""
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    elif re.fullmatch(r"\d+,\d{1,2}", s):
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
        return float(m.group()) if m else 0.0


def _page_numbers(doc, pages):
    """Every number printed on the bill pages (from the text layer), for checking quantities."""
    out = set()
    for p in pages:
        raw = doc[p].get_text()
        text = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,"))
        found = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
        # right-to-left PDFs often store Arabic-Indic digits backwards ("٠٦١" for 160): accept both orders
        found += [n[::-1] for n in re.findall(r"[٠-٩][٠-٩٫٬.,]*", raw)]
        for n in found:
            out.add(round(parse_qty(n), 4))
    return out


def bill_pages(pdf_path):
    """Pages (0-based) of the bill table: pages with the table header, plus the pages that follow them while they
    still look like bill lines (long bills often print the header only once). Scanned PDFs: the first MAX_PAGES."""
    doc = pymupdf.open(pdf_path)
    texts = [normalize(p.get_text()) for p in doc]
    if not any(len(t) > 50 for t in texts):
        return list(range(min(len(doc), MAX_PAGES)))
    header = [sum(w in t for w in _BOQ_WORDS) >= 2 and bool(re.search(r"\d", t)) for t in texts]
    looks_like_lines = [len(_LINE_UNITS.findall(t)) >= 2 and bool(re.search(r"\d", t)) for t in texts]
    pages, in_bill = [], False
    for i in range(len(doc)):
        in_bill = header[i] or (in_bill and looks_like_lines[i])
        if in_bill:
            pages.append(i)
    return pages[:MAX_PAGES]


def read_pdf_bill(pdf_path, resolver):
    """Returns (lines, pages) using Gemini on the bill pages only. Records calls/tokens on the resolver."""
    pages = bill_pages(pdf_path)
    if not pages or not resolver.gemini_key:
        return [], pages
    # pages go as pictures: PDF text layers often hold broken Arabic letters (swapped lam-alef), pictures don't
    src = pymupdf.open(pdf_path)
    images = [src[p].get_pixmap(dpi=130).tobytes("png") for p in pages]
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=resolver.gemini_key)
    cfg = types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0,
                                      response_mime_type="application/json", response_schema=SCHEMA)
    lines, section = [], ""
    for i in range(0, len(images), PAGES_PER_REQUEST):
        chunk = images[i:i + PAGES_PER_REQUEST]
        prompt = "Read the bill of quantities on these pages."
        if section:
            prompt += " The previous pages ended in the section: %s" % section
        got = None
        for model in PDF_MODELS:
            try:
                r = client.models.generate_content(
                    model=model, config=cfg,
                    contents=[types.Part.from_bytes(data=img, mime_type="image/png") for img in chunk] + [prompt])
                resolver.calls += 1
                u = r.usage_metadata
                resolver.tokens += (u.prompt_token_count or 0) + (u.candidates_token_count or 0)
                got = json.loads(r.text)["lines"]
                break
            except Exception as e:
                resolver.errors.append("pdf %s pages %d-%d: %s" % (model, pages[i] + 1, pages[min(i + PAGES_PER_REQUEST, len(pages)) - 1] + 1, str(e)[:100]))
        if got is None:
            continue
        for ln in got:
            if ln.get("continued") and lines and lines[-1].get("continues"):
                prev = lines[-1]                       # the item that was split across the page break
                prev["desc"] = prev["desc"].rstrip() + " " + ln["desc"].lstrip()
                prev.update(qty=ln["qty"] or prev["qty"], unit=ln["unit"] or prev["unit"], continues=ln.get("continues", False))
            else:
                if not ln.get("section") and section:
                    ln["section"] = section
                lines.append(ln)
        if lines:
            section = lines[-1].get("section") or section
    for ln in lines:
        ln["qty_text"] = ln.get("qty")
        ln["qty"] = parse_qty(ln.get("qty"))
    lines = [ln for ln in lines if ln["qty"] > 0]                  # summary rows have no quantity
    has_text = any(len(src[p].get_text().strip()) > 50 for p in pages)
    if has_text:                                                    # a quantity not printed anywhere = misread
        printed = _page_numbers(src, pages)
        for ln in lines:
            ln["qty_ok"] = round(ln["qty"], 4) in printed
    return lines, pages


def write_bill_xlsx(lines, path, title=""):
    """The standard bill layout the reader understands: م | بيان الأعمال | الوحدة | الكمية | الفئة | الإجمالي."""
    wb = Workbook()
    ws = wb.active
    ws.title = "المقايسة"
    ws.sheet_view.rightToLeft = True
    for col, w in zip("ABCDEF", [6, 70, 10, 11, 12, 15]):
        ws.column_dimensions[col].width = w
    ws["B1"] = title
    ws["B1"].font = Font(bold=True)
    for i, h in enumerate(["م", "بيان الأعمال", "الوحدة", "الكمية", "الفئة", "الإجمالي", "ملاحظة القراءة"], 1):
        ws.cell(3, i, h).font = Font(bold=True)
    r, section = 4, None
    for ln in lines:
        if ln.get("section") and ln["section"] != section:
            section = ln["section"]
            ws.cell(r, 2, section).font = Font(bold=True)
            r += 1
        ws.cell(r, 1, ln.get("no"))
        ws.cell(r, 2, ln.get("desc")).alignment = Alignment(wrap_text=True, horizontal="right", readingOrder=2)
        ws.cell(r, 3, ln.get("unit"))
        ws.cell(r, 4, ln.get("qty"))
        ws.cell(r, 6, '=IF(E{0}="","",D{0}*E{0})'.format(r))
        if ln.get("qty_ok") is False:
            ws.cell(r, 7, "QTY? الكمية مش موجودة بالظبط في نص الـ PDF (مكتوبة %s) - راجعها" % ln.get("qty_text"))
        r += 1
    wb.save(path)
    return path
