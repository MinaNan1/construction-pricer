"""Units: read them from a bill (unit column or the wording "بالمتر المكعب ...") and convert between them."""
import re
from .text import normalize

M3, M2, M, KG, TON, NO, LS = "m3", "m2", "m", "kg", "ton", "no", "ls"

_ALIASES = {
    M3: ["م3", "متر مكعب", "m3", "cum", "cu m", "cubic meter", "cubic metre"],
    M2: ["م2", "متر مربع", "متر مسطح", "m2", "sqm", "sq m", "square meter", "square metre"],
    M: ["م ط", "مط", "م طولي", "متر طولي", "م", "m", "lm", "rm", "linear meter", "linear metre", "lin m", "linm", "l m", "rmt"],
    KG: ["كجم", "كج", "كيلو", "كيلوجرام", "كغ", "kg", "kgs"],
    TON: ["طن", "ton", "tons", "t", "tonne"],
    NO: ["عدد", "بالعدد", "قطعه", "no", "nr", "nos", "each", "pcs", "pc", "unit", "set", "sets", "pair", "piece", "ea"],
    LS: ["مقطوعيه", "بالمقطوعيه", "ls", "lump sum", "lumpsum", "lot", "item"],
}
_LOOKUP = {normalize(a): u for u, names in _ALIASES.items() for a in names}

# How a tender line starts: "بالمتر المكعب توريد ..." (after normalize()).
_DESC_PATTERNS = [
    (M3, r"^(بالمتر|المتر|متر) (المكعب|مكعب)"),
    (M2, r"^(بالمتر|المتر|متر) (المسطح|المربع|مسطح|مربع)"),
    (M, r"^(بالمتر|المتر|متر) (الطولي|طولي)"),
    (KG, r"^(بالكجم|بالكيلو|بالكيلوجرام)"),
    (TON, r"^(بالطن)"),
    (NO, r"^(بالعدد)"),
    (LS, r"^(بالمقطوعيه|مقطوعيه)"),
    (M3, r"^per (m3|cubic)"), (M2, r"^per (m2|square)"), (M, r"^per (m|linear)\b"),
    (KG, r"^per kg"), (TON, r"^per ton"), (NO, r"^per (no|nr|each)"),
]


def parse_unit(raw):
    """A unit cell such as "م2", "م.ط", "ton / طن" -> canonical unit, or None."""
    if raw is None:
        return None
    s = str(raw)
    if "/" in s:                      # price-list style "m² / م²": the English part is first
        s = s.split("/")[0]
    n = normalize(s.replace(".", " "))
    if n in _LOOKUP:
        return _LOOKUP[n]
    n2 = n.replace(" ", "")
    for alias, u in _LOOKUP.items():
        if alias.replace(" ", "") == n2:
            return u
    return None


def unit_from_description(desc):
    """The unit a tender line states in its own wording, e.g. "بالكجم توريد ..." -> kg."""
    n = normalize(desc)
    for u, pat in _DESC_PATTERNS:
        if re.search(pat, n):
            return u
    return None


def thickness_m(desc):
    """Thickness stated in a line ("بسمك 25 سم", "سمك لا يقل عن 25 سم", "15 cm thick") in metres."""
    n = normalize(desc)
    m = re.search(r"(?:بسمك|سمك|بسماكه|سماكه)(?: (?:لا يقل عن|لا تقل عن|متوسط|حوالي))? (\d+(?:\.\d+)?) ?(سم|مم|م|cm|mm)\b", n)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?) ?(cm|mm) thick", n)
    if not m:
        return None
    v, u = float(m.group(1)), m.group(2)
    return v / 100 if u in ("سم", "cm") else v / 1000 if u in ("مم", "mm") else v


UNIT_AR = {M3: "م³", M2: "م²", M: "م.ط", KG: "كجم", TON: "طن", NO: "عدد", LS: "مقطوعية"}
UNIT_EN = {M3: "m³", M2: "m²", M: "m", KG: "kg", TON: "ton", NO: "no.", LS: "lump sum"}


def _msg(en, ar):
    return {"en": en, "ar": ar}


def factor(bill_unit, item_unit, desc=""):
    """How many price-list units one bill unit holds, and why (bilingual).
    Returns (factor, note) or (None, reason) when they cannot be converted; note is "" when nothing changes."""
    if bill_unit is None or item_unit is None:
        return None, _msg("unit missing", "الوحدة مش موجودة")
    if bill_unit == item_unit:
        return 1.0, ""
    if bill_unit == KG and item_unit == TON:
        return 0.001, _msg("price per ton / 1000 = price per kg", "سعر الطن ÷ 1000 = سعر الكيلو")
    if bill_unit == TON and item_unit == KG:
        return 1000.0, _msg("price per kg x 1000 = price per ton", "سعر الكيلو × 1000 = سعر الطن")
    if {bill_unit, item_unit} == {M2, M3}:
        t = thickness_m(desc)
        if not t:
            return None, _msg("needs the thickness to convert between m² and m³", "محتاج السمك عشان أحوّل بين م² و م³")
        if bill_unit == M2:
            return t, _msg("price per m³ x %.2f m thickness = price per m²" % t, "سعر م³ × سمك %.2f م = سعر م²" % t)
        return 1 / t, _msg("price per m² / %.2f m thickness = price per m³" % t, "سعر م² ÷ سمك %.2f م = سعر م³" % t)
    return None, _msg("units %s and %s cannot be converted" % (UNIT_EN.get(bill_unit), UNIT_EN.get(item_unit)),
                      "مينفعش أحوّل بين %s و %s" % (UNIT_AR.get(bill_unit), UNIT_AR.get(item_unit)))
