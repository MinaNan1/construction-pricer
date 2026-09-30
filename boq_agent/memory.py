"""The agent's memory: every answer the owner gives is saved, so the same line in the next bill is priced
without asking. One SQLite file per workspace (contractor)."""
import datetime
import sqlite3
from rapidfuzz import fuzz
from .text import tokens

SIMILAR = 92   # a new line counts as "the same" as a remembered one at this fuzzy score or above


def _key(desc):
    return " ".join(tokens(desc))


class Memory:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS answers (
            key TEXT PRIMARY KEY, desc TEXT, unit TEXT, code TEXT, price REAL, saved TEXT)""")
        self.db.commit()

    def remember(self, desc, unit, code=None, price=None):
        """code = price-list item the owner picked, or price = the owner's own cost per bill unit."""
        self.db.execute("INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?)",
                        (_key(desc), desc[:500], unit, code, price, datetime.date.today().isoformat()))
        self.db.commit()

    def recall(self, desc, unit):
        """The saved answer for this line (same or near-identical wording and same unit), or None."""
        k = _key(desc)
        rows = self.db.execute("SELECT key, unit, code, price, saved FROM answers").fetchall()
        best = None
        for key, u, code, price, saved in rows:
            if u != unit:
                continue
            s = 100 if key == k else fuzz.token_sort_ratio(key, k)
            if s >= SIMILAR and (best is None or s > best[0]):
                best = (s, {"code": code, "price": price, "saved": saved})
        return best[1] if best else None

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM answers").fetchone()[0]

    def forget_all(self):
        self.db.execute("DELETE FROM answers")
        self.db.commit()
