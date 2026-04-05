"""
domain/coverage.py — Anamnese_App

Dekkingsmeter: drie niveaus per veld.

  "leeg"          — veld is None / "" / []
  "twijfelachtig" — veld is ingevuld maar waarschijnlijk niet bruikbaar
                    (te kort, nietszeggend keyword, NRS buiten 0-10)
  "bruikbaar"     — veld lijkt inhoudelijk gevuld

Alleen "bruikbaar" telt mee in coverage_score.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

# Minimale tekst-lengte per veld (na strip). Kortere waarden → twijfelachtig.
_MIN_LENGTH: dict[str, int] = {
    "HPI.begin":                    10,
    "HPI.beloop":                   10,
    "HPI.provocatie":               5,
    "HPI.verlichting":              5,
    "mechanisme_suspect.dominant":  5,
}
_DEFAULT_MIN_LENGTH = 2

# Enkelvoudige woorden/tekens die altijd als twijfelachtig worden beschouwd.
_MEANINGLESS = frozenset({
    "nvt", "nee", "ja", "ok", "oke", "?", "-", ".", "geen", "neen",
    "onbekend", "weet niet", "wn", "/", "n/a", "na",
})


# ---------------------------------------------------------------------------
# Kwaliteitsbeoordeling per veld
# ---------------------------------------------------------------------------

def field_quality(state: dict, path: str) -> str:
    """
    Beoordeelt de kwaliteit van één veld.
    Retourneert "leeg" | "twijfelachtig" | "bruikbaar".
    """
    cur = state
    for key in path.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return "leeg"

    # Leeg
    if cur in (None, "", []):
        return "leeg"

    # NRS — speciale numerieke check
    if path == "pijn.intensiteit_NRS":
        try:
            v = float(str(cur).strip().replace(",", "."))
            return "bruikbaar" if 0 <= v <= 10 else "twijfelachtig"
        except (ValueError, AttributeError):
            return "twijfelachtig"

    # Lijst
    if isinstance(cur, list):
        meaningful = [
            v for v in cur
            if isinstance(v, str)
            and len(v.strip()) >= 3
            and v.strip().lower() not in _MEANINGLESS
        ]
        return "bruikbaar" if meaningful else "twijfelachtig"

    # String
    if isinstance(cur, str):
        s = cur.strip()
        min_len = _MIN_LENGTH.get(path, _DEFAULT_MIN_LENGTH)
        if len(s) < min_len:
            return "twijfelachtig"
        if s.lower() in _MEANINGLESS:
            return "twijfelachtig"
        return "bruikbaar"

    # Bool / int / float / overig
    return "bruikbaar"


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------

_ICON = {
    "bruikbaar":     "✅",
    "twijfelachtig": "⚠️",
    "leeg":          "❌",
}


def missing_table(state: dict, required: list) -> list[tuple[str, str, str]]:
    """
    Geeft lijst van (icoon, veldpad, kwaliteit) per verplicht veld.
    Iconen: ✅ bruikbaar · ⚠️ twijfelachtig · ❌ leeg
    """
    rows = []
    for p in required:
        q = field_quality(state, p)
        rows.append((_ICON[q], p, q))
    return rows


def coverage_score(state: dict, required: list) -> tuple[int, int]:
    """
    Geeft (bruikbaar_ingevuld, totaal).
    Alleen "bruikbaar" telt mee — twijfelachtig telt NIET mee.
    """
    filled = sum(1 for p in required if field_quality(state, p) == "bruikbaar")
    return filled, len(required)


def compute_open_fields_hint(state: dict, required: list) -> tuple[list[str], str]:
    """
    Geeft (lijst van niet-bruikbare velden, hint-tekst).
    Gebruikt door dekkingsmeter en toekomstige coach-prompt.
    """
    open_fields = [p for p in required if field_quality(state, p) != "bruikbaar"]
    if not open_fields:
        hint = "Alle kernvelden zijn bruikbaar ingevuld."
    else:
        hint = f"{len(open_fields)} veld(en) nog open of twijfelachtig: {', '.join(open_fields)}"
    return open_fields, hint
