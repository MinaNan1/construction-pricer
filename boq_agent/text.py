"""Arabic/English text cleanup and tokens for matching bill lines to price-list items."""
import re

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_KEEP = re.compile(r"[^a-z0-9ء-ي.]+")
_TRANS = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "²": "2", "³": "3", "×": " x ", "–": " ", "—": " ",
})

# Leading Arabic particles glued to a word ("والحوائط", "للبلاطات", "بالطوب").
_PREFIXES = ("وبال", "وال", "بال", "كال", "فال", "لل", "ال")

# Common Egyptian site words that mean the same thing, mapped to the price-list wording.
SYNONYMS = {
    "بياض": "محاره", "لياسه": "محاره",
    "طفلي": "وردي",
    "بير": "بيت",            # بئر المصعد -> بيت المصعد
    "رطوبه": "مائي",
    "دهانات": "دهان",
    "بولسترين": "فوم", "بوليسترين": "فوم", "مبثوق": "فوم",
    "مجلفن": "مجلفن",
}

_STOP_AR = set("""
توريد وتوريد تركيب وتركيب عمل وعمل بند والبند البند يشمل ويشمل تشمل وتشمل فيه فئه والفئه سعر والسعر الثمن والثمن شامل شامله
طبقا للمواصفات مواصفات المواصفات وتعليمات تعليمات مهندس المهندس مشرف المشرف جهاز الاشراف اشراف كل ما يلزم لنهو
الاعمال اعمال العمل اصول الصناعه صناعه من في فى علي على مع الي الى عن لا يقل يزيد او و ب ل حتي ذلك كذا وكذا هذا هذه
التي الذي مما جميعه القياس قياس هندسي هندسى والقياس الرسومات رسومات المرفقه لزوم بعد قبل كامل كاملا محمل عليه
متر المتر بالمتر مكعب المكعب مسطح المسطح مربع المربع طولي الطولي بالعدد عدد بالكجم كجم بالطن طن بالمقطوعيه مقطوعيه
جيدا ان يتم ايضا خلافه وخلافه بطريقه طريقه نوع اي اى
""".split())
_STOP_EN = set("""
supply install installation and the of with including incl per for a an to in on by at or all as is be m m2 m3 no ton kg
""".split())


def _normalized_set(words):
    return {normalize(w) for w in words}


def normalize(text):
    """Lower-case, strip diacritics, unify alef/ya/ta-marbuta and digits, keep letters, digits and dots."""
    if text is None:
        return ""
    s = str(text).lower().translate(_TRANS)
    s = _DIACRITICS.sub("", s)
    s = _KEEP.sub(" ", s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)   # dots only inside numbers
    return re.sub(r"\s+", " ", s).strip()


_STOP_AR = _normalized_set(_STOP_AR)
SYNONYMS = {normalize(k): normalize(v) for k, v in SYNONYMS.items()}


def stem(tok):
    for p in _PREFIXES:
        if tok.startswith(p) and len(tok) - len(p) >= 3:
            return tok[len(p):]
    return tok


def tokens(text):
    """Content words of a text: normalized, stemmed, synonyms unified, stop words removed."""
    out = []
    for t in normalize(text).split():
        t = SYNONYMS.get(stem(t), stem(t))
        if t in _STOP_AR or t in _STOP_EN or len(t) < 2 and not t.isdigit():
            continue
        out.append(t)
    return out
