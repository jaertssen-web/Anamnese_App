"""
domain/exporter.py — Anamnese_App

Markdown-export van het anamnese-rapport.

Bron: LETTERLIJK overgenomen uit TEMP/exporter.py
  - default_report_name()
  - build_markdown()

Geen wijzigingen aangebracht in v1.
"""

from __future__ import annotations

import datetime as _dt


def default_report_name(state: dict, pid: str = "patient") -> str:
    ini = (state.get("patient", {}) or {}).get("initialen", "").strip() or "NA"
    today = _dt.date.today().isoformat()
    return f"{today}_{pid}_{ini}_anamnese.md"


def build_markdown(state: dict) -> str:
    p = state.get("patient", {}) or {}
    mech = state.get("mechanisme_suspect", {}) or {}
    pijn = state.get("pijn", {}) or {}
    smart = state.get("Smart_screen", {}) or {}
    plan = state.get("plan", {}) or {}
    hpi = state.get("HPI", {}) or {}
    notities = state.get("notities_vrij", "") or ""
    transcript = state.get("transcript", {}) or {}
    transcript_tekst = transcript.get("tekst", "") or ""
    transcript_bron = transcript.get("bron", "") or ""
    transcript_bestand = transcript.get("bestandsnaam", "") or ""

    lines = []
    lines.append(f"# Anamnese – {p.get('initialen', '')}")
    lines.append("")

    # Patiëntgegevens
    leeftijd = p.get("leeftijd", "")
    geslacht = p.get("geslacht", "")
    datum = (state.get("context", {}) or {}).get("datum_consult", "")
    if leeftijd or geslacht or datum:
        lines.append(f"**Leeftijd:** {leeftijd}  |  **Geslacht:** {geslacht}  |  **Datum:** {datum}")
        lines.append("")

    # HPI
    lines.append("## HPI")
    for key, label in [
        ("begin", "Begin"),
        ("beloop", "Beloop"),
        ("provocatie", "Provocatie"),
        ("verlichting", "Verlichting"),
    ]:
        val = hpi.get(key, "") or ""
        lines.append(f"- **{label}:** {val or '-'}")
    fi = hpi.get("functionele_impact", []) or []
    lines.append(f"- **Functionele impact:** {', '.join(fi) if fi else '-'}")
    lines.append("")

    # Pijn
    lines.append("## Pijn")
    locs = ", ".join(pijn.get("locaties", []) or [])
    kar = ", ".join(pijn.get("karakter", []) or [])
    lines.append(f"- Locaties: {locs or '-'}")
    lines.append(f"- NRS: {pijn.get('intensiteit_NRS', '') or '-'}")
    lines.append(f"- Karakter: {kar or '-'}")
    lines.append("")

    # Mechanisme
    lines.append(f"**Dominant mechanisme:** {mech.get('dominant', '') or '-'}")
    lines.append(f"**Onderbouwing:** {mech.get('onderbouwing', '') or '-'}")
    lines.append("")

    # Smart/Baron
    lines.append("## Smart/Baron")
    lines.append(f"- Noci: {', '.join(smart.get('nociceptief_kenmerken', []) or []) or '-'}")
    lines.append(f"- Neuro: {', '.join(smart.get('neuropathisch_kenmerken', []) or []) or '-'}")
    lines.append(f"- Nocipl.: {', '.join(smart.get('nociplastisch_kenmerken', []) or []) or '-'}")
    lines.append(f"- Baron cluster: {state.get('Baron_cluster', '') or '-'}")
    lines.append("")

    # Rode vlaggen
    lines.append("## Rode vlaggen")
    rv = state.get("rode_vlaggen") or []
    lines.append("- " + ("Geen" if not rv else "\n- ".join(rv)))
    lines.append("")

    # Plan
    lines.append("## Plan")
    for key, label in [
        ("diagnostiek", "Diagnostiek"),
        ("voorlichting", "Voorlichting"),
        ("niet_farmacologisch", "Niet-farmacologisch"),
        ("farmacologisch", "Farmacologisch"),
        ("interventioneel", "Interventioneel"),
    ]:
        vals = plan.get(key, []) or []
        lines.append(f"- {label}: " + (", ".join(vals) if vals else "-"))
    lines.append("")

    # Vrije notities
    if notities.strip():
        lines.append("## Notities")
        lines.append(notities.strip())
        lines.append("")

    # Transcript
    if transcript_tekst.strip():
        meta_parts = []
        if transcript_bron:
            meta_parts.append(transcript_bron)
        if transcript_bestand:
            meta_parts.append(transcript_bestand)
        meta = f"  *(bron: {', '.join(meta_parts)})*" if meta_parts else ""
        lines.append(f"## Transcript{meta}")
        lines.append("")
        lines.append(transcript_tekst.strip())

    return "\n".join(lines)
