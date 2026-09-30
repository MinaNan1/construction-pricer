"""Match a bill line to price-list items with plain code (no AI): shared key words weighted by how rare
they are, fuzzy text similarity, and whether the units fit. Arabic lines are compared with the Arabic
item names and English lines with the English names."""
import math
import re
from rapidfuzz import fuzz
from .text import tokens
from .units import factor

# A match is taken without asking only when all three hold; everything else goes to the AI / the owner.
AUTO_COVERAGE = 0.60   # share of the item's key words (weighted by rarity) found in the line
AUTO_SCORE = 0.60
AUTO_MARGIN = 0.10     # lead over the runner-up

_ARABIC = re.compile(r"[ء-ي]")

# The kind of work a line is about. A line can only be matched automatically to an item of the same kind:
# "تكسير خرسانة مع نقل الناتج خارج الموقع" is demolition, not excavation, even though it shares words with it.
WORK_KINDS = {
    "excavate": {"حفر", "excavation", "excavate", "excavating"},
    "backfill": {"ردم", "backfill", "backfilling", "filling"},
    "demolish": {"تكسير", "هدم", "فك", "ازاله", "تقشير", "كحت", "demolition", "demolish", "dismantle", "dismantling",
                 "removal", "remove", "removing", "breaking", "break"},
    "repair": {"اصلاح", "صيانه", "ترميم", "معالجه", "مرمات", "repair", "repairs", "maintenance", "rehabilitation", "restore"},
}
MAIN_WORDS = 8     # the main verb of a tender line is at its start; later text mentions other work ("ردم مكان الحفر")


def work_kind(toks):
    """The kind of the first work verb near the start of a text, or None."""
    for t in toks[:MAIN_WORDS]:
        for k, words in WORK_KINDS.items():
            if t in words:
                return k
    return None


def is_arabic(text):
    return len(_ARABIC.findall(text or "")) >= 3


class Matcher:
    def __init__(self, pricebook):
        self.pb = pricebook
        n = len(pricebook.items)
        self.idf = {}
        for lang in ("ar", "en"):
            df = {}
            for it in pricebook.items:
                for t in set(it["tokens_" + lang]):
                    df[t] = df.get(t, 0) + 1
            self.idf.update({t: math.log(1 + n / c) for t, c in df.items()})

    def _unglue(self, toks):
        """"وردم" -> "ردم" when only the shorter word is known to the price list (so "وردي" stays "وردي")."""
        out = []
        for t in toks:
            if t not in self.idf and len(t) > 3 and t[0] in "وبلف" and t[1:] in self.idf:
                t = t[1:]
            out.append(t)
        return out

    def _score(self, line_toks, line_text, line, item, lang):
        itoks = set(item["tokens_" + lang])
        if not itoks:
            return 0.0, 0.0, None
        shared = itoks & line_toks
        coverage = sum(self.idf.get(t, 0) for t in shared) / sum(self.idf.get(t, 0) for t in itoks)
        fuzzy = fuzz.token_set_ratio(line_text, " ".join(item["tokens_" + lang])) / 100
        score = 0.65 * coverage + 0.35 * fuzzy
        f, _ = factor(line["unit"], item["unit"], line["desc"])
        if f is None:
            score -= 0.5
        elif f != 1.0:
            score -= 0.03 if line["unit"] in ("kg", "ton") else 0.10
        return score, coverage, f

    def candidates(self, line, k=3):
        lang = "ar" if is_arabic(line["desc"]) else "en"
        desc_toks = self._unglue(tokens(line["desc"]))
        toks = desc_toks + self._unglue(tokens(line.get("section", "")))
        text = " ".join(toks[:60])
        kind = work_kind(desc_toks)
        scored = []
        for it in self.pb.items:
            s, cov, f = self._score(set(toks), text, line, it, lang)
            clash = kind is not None and work_kind(it["tokens_" + lang]) != kind
            scored.append({"code": it["code"], "score": round(s, 3), "coverage": round(cov, 3), "factor": f,
                           "kind_clash": clash})
        scored.sort(key=lambda c: -c["score"])
        return scored[:k]

    def decide(self, cands):
        """'auto' when the best candidate is good, covers the item's key words, and is clearly ahead; else 'unclear'."""
        if not cands:
            return "unclear"
        top = cands[0]
        second = cands[1]["score"] if len(cands) > 1 else 0
        if (top["factor"] is not None and not top.get("kind_clash") and top["coverage"] >= AUTO_COVERAGE
                and top["score"] >= AUTO_SCORE and top["score"] - second >= AUTO_MARGIN):
            return "auto"
        return "unclear"
