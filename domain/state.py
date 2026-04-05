"""
domain/state.py — Anamnese_App

Datamodel en persistentie voor één consult-sessie.

Bronnen (letterlijk overgenomen uit TEMP/main.py):
  - default_state()
  - load_state_from() / save_state_to()
  - path_filled()
  - sanitize_pid_and_date()
  - init_consult_dir()
"""

from __future__ import annotations

import json
import os
import re
from datetime import date


# ---------------------------------------------------------------------------
# Datamodel
# ---------------------------------------------------------------------------

def default_state(required_fields: list) -> dict:
    """Leeg anamnese-datamodel. Bron: TEMP/main.py default_state()."""
    return {
        "patient": {"initialen": "", "leeftijd": "", "geslacht": ""},
        "context": {"datum_consult": "", "instelling": "", "bron": "handmatig"},
        "HPI": {
            "begin": "",
            "beloop": "",
            "provocatie": "",
            "verlichting": "",
            "functionele_impact": [],
        },
        "pijn": {
            "locaties": [],
            "intensiteit_NRS": "",
            "karakter": [],
            "referred_pain": None,
            "slaapverstoring": None,
        },
        "mechanisme_suspect": {
            "dominant": "",
            "secundair": [],
            "onderbouwing": "",
            "centrale_sensitisatie_signalen": [],
        },
        "Smart_screen": {
            "nociceptief_kenmerken": [],
            "neuropathisch_kenmerken": [],
            "nociplastisch_kenmerken": [],
        },
        "Baron_cluster": "null",
        "rode_vlaggen": [],
        "psychosociaal": {
            "catastroferen": None,
            "kinesiofobie": None,
            "angst": None,
            "PTSS": None,
            "notities": "",
        },
        "medicatie_relevant": [],
        "plan": {
            "diagnostiek": [],
            "voorlichting": [],
            "niet_farmacologisch": [],
            "farmacologisch": [],
            "interventioneel": [],
        },
        "notities_vrij": "",
        "transcript": {
            "tekst": "",        # ruwe transcripttekst (geplakt of geüpload)
            "bron": "",         # "geplakt" | "upload"
            "bestandsnaam": "", # originele bestandsnaam bij upload
        },
        "required_fields": required_fields or [],
        "suggested_questions": [],
    }


# ---------------------------------------------------------------------------
# Persistentie
# ---------------------------------------------------------------------------

def load_state_from(consult_dir: str, required_fields: list) -> dict:
    """Laad state.json uit consultmap, of geef default_state terug."""
    os.makedirs(consult_dir, exist_ok=True)
    p = os.path.join(consult_dir, "state.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_state(required_fields)


def save_state_to(consult_dir: str, state: dict) -> None:
    """Sla state op als state.json in de consultmap."""
    os.makedirs(consult_dir, exist_ok=True)
    p = os.path.join(consult_dir, "state.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def path_filled(dct: dict, path: str) -> bool:
    """Controleer of een genest veld niet leeg/None/[] is. Bron: TEMP/main.py."""
    cur = dct
    for key in path.split("."):
        if isinstance(cur, dict) and key in cur and cur[key] not in (None, "", []):
            cur = cur[key]
        else:
            return False
    return True


def sanitize_pid_and_date(pid_raw: str, date_raw: str) -> tuple[str, str]:
    """Normaliseer patiënt-ID en datum. Bron: TEMP/main.py."""
    pid = (pid_raw or "").strip()
    d = (date_raw or "").strip()
    for ext in (".txt", ".md", ".rtf", ".pdf"):
        if pid.lower().endswith(ext):
            pid = pid[: -len(ext)]
        if d.lower().endswith(ext):
            d = d[: -len(ext)]
    pid = re.sub(r"[^A-Za-z0-9_\-\. ]+", "_", pid).strip() or "demo_patient"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        d = date.today().isoformat()
    return pid, d


def init_consult_dir(base_dir: str, pid: str, datum: str) -> str:
    """Maak consultmap aan: {base_dir}/{pid}/{datum}/. Bron: TEMP/main.py."""
    for ext in (".txt", ".md", ".rtf", ".pdf"):
        if pid.lower().endswith(ext):
            pid = pid[: -len(ext)]
        if datum.lower().endswith(ext):
            datum = datum[: -len(ext)]
    pid = re.sub(r"[^A-Za-z0-9_\-\. ]+", "_", (pid or "").strip()) or "demo_patient"
    datum = (datum or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        datum = date.today().isoformat()
    consult_dir = os.path.join(base_dir, pid, datum)
    os.makedirs(consult_dir, exist_ok=True)
    return consult_dir
