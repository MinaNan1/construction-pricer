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
        toks = tokens(line["desc"]) + tokens(line.get("section", ""))
        text = " ".join(toks[:60])
        scored = []
        for it in self.pb.items:
            s, cov, f = self._score(set(toks), text, line, it, lang)
            scored.append({"code": it["code"], "score": round(s, 3), "coverage": round(cov, 3), "factor": f})
        scored.sort(key=lambda c: -c["score"])
        return scored[:k]

    def decide(self, cands):
        """'auto' when the best candidate is good, covers the item's key words, and is clearly ahead; else 'unclear'."""
        if not cands:
            return "unclear"
        top = cands[0]
        second = cands[1]["score"] if len(cands) > 1 else 0
        if (top["factor"] is not None and top["coverage"] >= AUTO_COVERAGE and top["score"] >= AUTO_SCORE
                and top["score"] - second >= AUTO_MARGIN):
            return "auto"
        return "unclear"
