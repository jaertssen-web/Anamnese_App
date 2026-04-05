"""
Anamnese_App v1 — Streamlit spreekuurtool.

Workflow:
  1. Patiënt-ID + datum kiezen (sidebar)
  2. Kernvelden invullen (HPI, pijn, plan)
  3. Dekkingsmeter checken (alle required fields groen?)
  4. Exporteren als Markdown

Geen LLM, geen Ollama, geen coach-panel in v1.
Geparkeerd materiaal voor v2: zie future/PARKEER_NOTITIE.md

Start:
    bash scripts/bootstrap_and_run.sh
"""

import json
import os
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Paden
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent        # .../Anamnese_App/app/
REPO_ROOT = APP_DIR.parent                       # .../Anamnese_App/
DATA_ROOT = REPO_ROOT / "data" / "patienten"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from domain.state import (                       # noqa: E402
    default_state, load_state_from, save_state_to,
    sanitize_pid_and_date, init_consult_dir,
)
from domain.coverage import missing_table, coverage_score, compute_open_fields_hint  # noqa: E402
from domain.exporter import build_markdown, default_report_name                      # noqa: E402
from domain.coach_backend import get_coach                                           # noqa: E402
from domain.basic_coverage_coach import EXPERIMENTAL_TOPIC_IDS                       # noqa: E402

DATA_ROOT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Required fields laden
# ---------------------------------------------------------------------------

@st.cache_data
def load_required_fields() -> list[str]:
    p = KNOWLEDGE_DIR / "required_fields.json"
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("required_fields", [])
    except Exception:
        return []


REQUIRED = load_required_fields()


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Anamnese App",
    page_icon="🩺",
    layout="wide",
)

st.title("Anamnese App")
st.caption("Spreekuurtool · versie 1.2 · geen LLM")


# ---------------------------------------------------------------------------
# Sidebar — patiënt + consult
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Consult")

    pid_raw = st.text_input(
        "Patiënt-ID (mapnaam)",
        value="demo_patient",
        key="pid",
        help="Wordt gebruikt als mapnaam. Geen spaties nodig; speciale tekens worden vervangen.",
    )
    date_raw = st.text_input(
        "Datum consult (JJJJ-MM-DD)",
        value="",
        key="datum",
        placeholder="bijv. 2026-04-05",
    )
    instelling = st.text_input("Instelling (optioneel)", key="instelling")

    pid, datum = sanitize_pid_and_date(pid_raw, date_raw)
    consult_dir = init_consult_dir(str(DATA_ROOT), pid, datum)

    if pid_raw.strip() and pid != pid_raw.strip():
        st.caption(f"Mapnaam: `{pid}` (speciale tekens vervangen)")
    st.caption(f"Opslag: `data/patienten/{pid}/{datum}/`")
    st.divider()
    st.caption("v1.2 · geen LLM · coach (9 kern + 6 experimenteel)")


# ---------------------------------------------------------------------------
# State laden
# ---------------------------------------------------------------------------

# Gebruik session_state om state door reruns heen te bewaren
_state_key = f"state_{pid}_{datum}"
if _state_key not in st.session_state:
    st.session_state[_state_key] = load_state_from(consult_dir, REQUIRED)

state = st.session_state[_state_key]
state["context"]["datum_consult"] = datum
state["context"]["instelling"] = instelling


# ---------------------------------------------------------------------------
# Helpers voor formuliervelden
# ---------------------------------------------------------------------------

def _list_to_str(val) -> str:
    if isinstance(val, list):
        return ", ".join(val)
    return str(val) if val else ""


def _str_to_list(val: str) -> list[str]:
    return [v.strip() for v in val.split(",") if v.strip()]


# ---------------------------------------------------------------------------
# Hoofdlayout: twee kolommen
# ---------------------------------------------------------------------------

col_invul, col_dek = st.columns([2, 1])


# ── LINKERKOLOM: invulvelden ──────────────────────────────────────────────
with col_invul:

    # ── Patiëntgegevens ──────────────────────────────────────────────────
    with st.expander("Patiëntgegevens", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            state["patient"]["initialen"] = st.text_input(
                "Initialen", value=state["patient"]["initialen"] or "", key="initialen"
            )
        with c2:
            state["patient"]["leeftijd"] = st.text_input(
                "Leeftijd", value=str(state["patient"]["leeftijd"] or ""), key="leeftijd"
            )
        with c3:
            state["patient"]["geslacht"] = st.selectbox(
                "Geslacht",
                options=["", "man", "vrouw", "anders"],
                index=["", "man", "vrouw", "anders"].index(state["patient"]["geslacht"] or "") if state["patient"]["geslacht"] in ["", "man", "vrouw", "anders"] else 0,
                key="geslacht",
            )

    # ── HPI ──────────────────────────────────────────────────────────────
    with st.expander("HPI — Huidige Pijnklacht", expanded=True):
        state["HPI"]["begin"] = st.text_area(
            "Begin  *(wanneer / hoe begonnen)*",
            value=state["HPI"]["begin"] or "",
            height=80,
            key="hpi_begin",
        )
        state["HPI"]["beloop"] = st.text_area(
            "Beloop  *(verloop in de tijd)*",
            value=state["HPI"]["beloop"] or "",
            height=80,
            key="hpi_beloop",
        )
        c_prov, c_verl = st.columns(2)
        with c_prov:
            state["HPI"]["provocatie"] = st.text_area(
                "Provocatie  *(wat verergert?)*",
                value=state["HPI"]["provocatie"] or "",
                height=80,
                key="hpi_prov",
            )
        with c_verl:
            state["HPI"]["verlichting"] = st.text_area(
                "Verlichting  *(wat helpt?)*",
                value=state["HPI"]["verlichting"] or "",
                height=80,
                key="hpi_verl",
            )
        fi_raw = st.text_input(
            "Functionele impact  *(komma-gescheiden)*",
            value=_list_to_str(state["HPI"]["functionele_impact"]),
            key="hpi_fi",
            help="Bijv: lopen, traplopen, slapen",
        )
        state["HPI"]["functionele_impact"] = _str_to_list(fi_raw)

    # ── Pijn ─────────────────────────────────────────────────────────────
    with st.expander("Pijnkenmerken", expanded=True):
        c_loc, c_nrs = st.columns([2, 1])
        with c_loc:
            loc_raw = st.text_input(
                "Locaties  *(komma-gescheiden)*",
                value=_list_to_str(state["pijn"]["locaties"]),
                key="pijn_loc",
                help="Bijv: linker voet, rechter knie",
            )
            state["pijn"]["locaties"] = _str_to_list(loc_raw)
        with c_nrs:
            nrs_val = st.text_input(
                "NRS  *(0-10)*",
                value=str(state["pijn"]["intensiteit_NRS"] or ""),
                key="pijn_nrs",
            )
            state["pijn"]["intensiteit_NRS"] = nrs_val
            if nrs_val.strip():
                try:
                    nrs_int = int(float(nrs_val.strip()))
                    if not (0 <= nrs_int <= 10):
                        st.caption("Waarde buiten 0-10.")
                except ValueError:
                    st.caption("Verwacht getal 0-10.")
        kar_raw = st.text_input(
            "Karakter  *(komma-gescheiden)*",
            value=_list_to_str(state["pijn"]["karakter"]),
            key="pijn_kar",
            help="Bijv: brandend, stekend, doofheid",
        )
        state["pijn"]["karakter"] = _str_to_list(kar_raw)

        c_ref, c_slaap = st.columns(2)
        with c_ref:
            state["pijn"]["referred_pain"] = st.selectbox(
                "Referred pain",
                options=[None, True, False],
                format_func=lambda x: "onbekend" if x is None else ("ja" if x else "nee"),
                index=[None, True, False].index(state["pijn"]["referred_pain"]),
                key="pijn_ref",
            )
        with c_slaap:
            state["pijn"]["slaapverstoring"] = st.selectbox(
                "Slaapverstoring",
                options=[None, True, False],
                format_func=lambda x: "onbekend" if x is None else ("ja" if x else "nee"),
                index=[None, True, False].index(state["pijn"]["slaapverstoring"]),
                key="pijn_slaap",
            )

    # ── Mechanisme (tussenstand — handmatig in v1) ────────────────────────
    with st.expander("Mechanisme-inschatting (handmatig)", expanded=False):
        st.caption("In v2 wordt dit aangevuld door LLM-analyse. Vul hier je klinische inschatting in.")
        state["mechanisme_suspect"]["dominant"] = st.text_input(
            "Dominant mechanisme",
            value=state["mechanisme_suspect"]["dominant"] or "",
            key="mech_dom",
            help="Bijv: neuropathisch, nociceptief, nociplastisch",
        )
        state["mechanisme_suspect"]["onderbouwing"] = st.text_area(
            "Onderbouwing",
            value=state["mechanisme_suspect"]["onderbouwing"] or "",
            height=80,
            key="mech_ond",
        )

    # ── Medicatie ─────────────────────────────────────────────────────────
    with st.expander("Medicatie (relevant)", expanded=False):
        med_raw = st.text_area(
            "Medicatie — één per regel  *(naam · dosering · startdatum)*",
            value="\n".join(state["medicatie_relevant"]) if state["medicatie_relevant"] else "",
            height=100,
            key="medicatie",
            placeholder="Pregabalin 75mg 2dd · 2025-01\nTramadol 50mg prn · 2024-06",
        )
        state["medicatie_relevant"] = [l.strip() for l in med_raw.splitlines() if l.strip()]

    # ── Plan ─────────────────────────────────────────────────────────────
    with st.expander("Plan", expanded=False):
        for plan_key, plan_label in [
            ("diagnostiek",        "Diagnostiek"),
            ("voorlichting",       "Voorlichting"),
            ("niet_farmacologisch","Niet-farmacologisch"),
            ("farmacologisch",     "Farmacologisch"),
            ("interventioneel",    "Interventioneel"),
        ]:
            raw = st.text_input(
                plan_label,
                value=_list_to_str(state["plan"][plan_key]),
                key=f"plan_{plan_key}",
                help="Komma-gescheiden",
            )
            state["plan"][plan_key] = _str_to_list(raw)

    # ── Transcript ────────────────────────────────────────────────────────
    with st.expander("Transcript", expanded=True):
        # Zorg dat transcript-sleutel altijd aanwezig is (backward compat)
        if "transcript" not in state or not isinstance(state["transcript"], dict):
            state["transcript"] = {"tekst": "", "bron": "", "bestandsnaam": ""}

        # .txt upload (MacWhisper / AutoScriber) — verwerkt vóór text_area
        uploaded_txt = st.file_uploader(
            "Importeer transcript (.txt — bijv. MacWhisper of AutoScriber)",
            type=["txt"],
            key="transcript_upload",
            help="Laadt de bestandsinhoud als ruwe tekst. Geen automatische parsing.",
        )
        if uploaded_txt is not None:
            content = uploaded_txt.getvalue().decode("utf-8", errors="replace")
            state["transcript"]["tekst"] = content
            state["transcript"]["bron"] = "upload"
            state["transcript"]["bestandsnaam"] = uploaded_txt.name
            st.caption(f"Geladen: `{uploaded_txt.name}` — {len(content.split())} woorden")

        # Bewerkbaar tekstveld — altijd zichtbaar, ook na upload
        transcript_val = st.text_area(
            "Plak of bewerk transcript",
            value=state["transcript"]["tekst"] or "",
            height=220,
            key="transcript_paste",
            placeholder="Plak hier het ruwe transcript uit MacWhisper, AutoScriber of een ander hulpmiddel...",
            label_visibility="collapsed",
        )
        # Sla wijzigingen op in state; bij handmatig plakken: bron = "geplakt"
        if transcript_val != state["transcript"]["tekst"]:
            state["transcript"]["bron"] = "geplakt"
            state["transcript"]["bestandsnaam"] = ""
        state["transcript"]["tekst"] = transcript_val

        if transcript_val.strip():
            n_woorden = len(transcript_val.split())
            n_regels = transcript_val.count("\n") + 1
            st.caption(f"{n_woorden} woorden · {n_regels} regels")

    # ── Vrije notities ────────────────────────────────────────────────────
    with st.expander("Vrije notities", expanded=False):
        state["notities_vrij"] = st.text_area(
            "Notities — eigen observaties en aanvullingen",
            value=state.get("notities_vrij", "") or "",
            height=150,
            key="notities",
            label_visibility="collapsed",
            placeholder="Klinische observaties, contextuele aanvullingen, eigen notities...",
        )


# ── RECHTERKOLOM: basisdekking + velddekking + opslaan + export ───────────
with col_dek:

    # ── Basisdekking gesprek (primair, standaard open) ────────────────────
    _COACH_ICON = {"voldoende": "✅", "deels": "⚠️", "onvoldoende": "❌"}

    def _render_coach_row(result) -> None:
        icon = _COACH_ICON[result.status]
        if result.status == "voldoende":
            st.markdown(f"{icon} {result.label}")
        elif result.status == "deels":
            st.markdown(f"{icon} **{result.label}** — {result.reden}")
        else:
            st.markdown(f"{icon} **{result.label}**")
            if result.vervolgvraag:
                st.markdown(
                    f"<div style='margin-left:1.2em;color:#555;font-size:0.9em'>"
                    f"❓ {result.vervolgvraag}</div>",
                    unsafe_allow_html=True,
                )

    coach = get_coach()
    all_results = coach.evaluate(state)

    kern_results = [r for r in all_results if r.onderwerp not in EXPERIMENTAL_TOPIC_IDS]
    exp_results  = [r for r in all_results if r.onderwerp in EXPERIMENTAL_TOPIC_IDS]

    with st.expander("Basisdekking gesprek — wat inhoudelijk al aan bod kwam", expanded=True):
        st.caption(
            "Heuristische gesprekslaag op basis van aanwezige tekst — "
            "geen klinische interpretatie."
        )

        n_voldoende = sum(1 for r in kern_results if r.status == "voldoende")
        n_kern = len(kern_results)
        coach_pct = n_voldoende / n_kern if n_kern else 0.0
        st.progress(coach_pct, text=f"{n_voldoende}/{n_kern} kernonderwerpen voldoende")

        for result in kern_results:
            _render_coach_row(result)

        # — Experimentele topics (collapsed) —
        with st.expander("Experimentele topics (ruis-gevoelig)", expanded=False):
            st.caption(
                "Deze topics hebben bekende beperkingen: negaties worden niet herkend, "
                "keywords zijn te breed, of er is geen veldbacking. "
                "Gebruik als losse hint, niet als dekkingoordeel."
            )
            for result in exp_results:
                _render_coach_row(result)

    # ── Velddekking (secundair, standaard ingeklapt) ──────────────────────
    with st.expander("Velddekking — welke vaste velden al zijn ingevuld", expanded=False):
        filled, total = coverage_score(state, REQUIRED)
        pct = filled / total if total else 0.0
        st.progress(pct, text=f"{filled}/{total} kernvelden bruikbaar")

        rows = missing_table(state, REQUIRED)
        for icon, veld, kwaliteit in rows:
            if kwaliteit == "twijfelachtig":
                st.markdown(f"{icon} `{veld}` — te kort of nietszeggend")
            else:
                st.markdown(f"{icon} `{veld}`")

        n_twijfel = sum(1 for _, _, q in rows if q == "twijfelachtig")
        if n_twijfel:
            st.caption("⚠️ = ingevuld maar twijfelachtig  ·  ❌ = leeg")

    st.divider()

    # ── Opslaan ──────────────────────────────────────────────────────────
    if st.button("Opslaan", type="primary", key="save_btn", use_container_width=True):
        try:
            save_state_to(consult_dir, state)
            st.success("Opgeslagen.")
        except Exception as e:
            st.error(f"Opslaan mislukt: {e}")

    st.divider()

    # ── Export ───────────────────────────────────────────────────────────
    st.subheader("Export")

    open_fields, hint = compute_open_fields_hint(state, REQUIRED)
    if open_fields:
        st.warning(f"Niet alle kernvelden ingevuld: {', '.join(open_fields)}")

    fn = default_report_name(state, pid)
    md = build_markdown(state)

    st.download_button(
        label="Download verslag (.md)",
        data=md.encode("utf-8"),
        file_name=fn,
        mime="text/markdown",
        key="dl_md",
        use_container_width=True,
    )

    if st.button("Opslaan in consultmap", key="save_report_btn", use_container_width=True):
        try:
            save_state_to(consult_dir, state)
            exports_dir = Path(consult_dir) / "exports"
            exports_dir.mkdir(exist_ok=True)
            out = exports_dir / fn
            out.write_text(md, encoding="utf-8")
            st.success(f"Verslag opgeslagen.")
            st.caption(f"`{out}`")
        except Exception as e:
            st.error(f"Opslaan mislukt: {e}")

    with st.expander("Voorbeeld verslag", expanded=False):
        st.code(md, language="markdown")

    st.divider()

    # ── State JSON (debug) ────────────────────────────────────────────────
    with st.expander("State (JSON)", expanded=False):
        st.json(state)
