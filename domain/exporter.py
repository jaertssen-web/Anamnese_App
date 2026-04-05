"""
domain/exporter.py — Anamnese_App

Twee exportformaten:
  1. build_markdown()           — opgemaakt verslag (.md), voor archief / EPD
  2. build_analysis_input_text() — platte werktekst (.txt), voor Anamnese_Anonymizer

Geen LLM, geen anonimisering, geen imports uit PatientData_Preprocessing.
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


# ---------------------------------------------------------------------------
# Analyse-export — werktekst voor anonimisering
# ---------------------------------------------------------------------------

def default_analysis_export_name(state: dict, pid: str = "patient") -> str:
    datum = (state.get("context", {}) or {}).get("datum_consult", "") or _dt.date.today().isoformat()
    return f"{datum}_{pid}_analysis_input.txt"


def build_analysis_input_text(state: dict, pid: str = "") -> str:
    """
    Platte werktekst die alle aanwezige inhoud bevat, klaar voor Anamnese_Anonymizer.

    Regels:
    - Lege of niet-ingevulde secties worden weggelaten.
    - Geen opmaak-markdown zoals **, # enz. — alleen sectiescheidingslijnen.
    - Volgorde: titelregel → identificatie → klacht → HPI → pijn → functie →
      slaap → stemming → medicatie → hulpvraag → vrije notities → transcript.
    """

    def _sec(title: str, body: str) -> list[str]:
        """Voeg sectie toe alleen als body niet leeg is."""
        body = body.strip()
        if not body:
            return []
        return [f"--- {title} ---", body, ""]

    ctx   = state.get("context", {}) or {}
    p     = state.get("patient", {}) or {}
    hpi   = state.get("HPI", {}) or {}
    pijn  = state.get("pijn", {}) or {}
    psych = state.get("psychosociaal", {}) or {}
    meds  = state.get("medicatie_relevant", []) or []

    lines: list[str] = []

    # Titelregel
    lines.append("Werktekst voor anonimisering en vervolganalyse")
    lines.append("=" * 50)
    lines.append("")

    # Identificatieregel (alleen als aanwezig)
    id_parts = []
    if pid:
        id_parts.append(f"ID: {pid}")
    datum = ctx.get("datum_consult", "")
    if datum:
        id_parts.append(f"datum: {datum}")
    instelling = ctx.get("instelling", "")
    if instelling:
        id_parts.append(f"instelling: {instelling}")
    ini = p.get("initialen", "")
    leeftijd = p.get("leeftijd", "")
    geslacht = p.get("geslacht", "")
    pat_parts = []
    if ini:
        pat_parts.append(f"initialen: {ini}")
    if leeftijd:
        pat_parts.append(f"leeftijd: {leeftijd}")
    if geslacht:
        pat_parts.append(f"geslacht: {geslacht}")
    if id_parts or pat_parts:
        lines += _sec("Patiënt en consult", "  ".join(id_parts + pat_parts))

    # HPI
    hpi_parts = []
    for key, label in [
        ("begin",     "Begin"),
        ("beloop",    "Beloop"),
        ("provocatie","Provocatie"),
        ("verlichting","Verlichting"),
    ]:
        val = (hpi.get(key) or "").strip()
        if val:
            hpi_parts.append(f"{label}: {val}")
    fi = hpi.get("functionele_impact", []) or []
    if fi:
        hpi_parts.append(f"Functionele impact: {', '.join(fi)}")
    if hpi_parts:
        lines += _sec("HPI", "\n".join(hpi_parts))

    # Pijnkenmerken
    pijn_parts = []
    locs = pijn.get("locaties", []) or []
    if locs:
        pijn_parts.append(f"Locaties: {', '.join(locs)}")
    nrs = pijn.get("intensiteit_NRS", "")
    if nrs:
        pijn_parts.append(f"NRS: {nrs}")
    kar = pijn.get("karakter", []) or []
    if kar:
        pijn_parts.append(f"Karakter: {', '.join(kar)}")
    ref = pijn.get("referred_pain")
    if ref is not None:
        pijn_parts.append(f"Referred pain: {'ja' if ref else 'nee'}")
    if pijn_parts:
        lines += _sec("Pijnkenmerken", "\n".join(pijn_parts))

    # Slaap
    slaap = pijn.get("slaapverstoring")
    if slaap is not None:
        lines += _sec("Slaap", f"Slaapverstoring: {'ja' if slaap else 'nee'}")

    # Stemming / cognities
    stemming = (psych.get("notities") or "").strip()
    if stemming:
        lines += _sec("Stemming en cognities", stemming)

    # Medicatie
    if meds:
        lines += _sec("Medicatie", "\n".join(meds))

    # Vrije notities
    notities = (state.get("notities_vrij") or "").strip()
    if notities:
        lines += _sec("Vrije notities", notities)

    # Transcript (altijd als laatste — grootste blok)
    transcript_tekst = ((state.get("transcript") or {}).get("tekst") or "").strip()
    if transcript_tekst:
        lines += _sec("Transcript", transcript_tekst)

    if not any(l.startswith("---") for l in lines):
        lines.append("(Geen inhoud ingevuld.)")

    return "\n".join(lines)
