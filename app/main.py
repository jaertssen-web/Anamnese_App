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
import tempfile
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
from domain.exporter import (                                                         # noqa: E402
    build_markdown, default_report_name,
    build_analysis_input_text, default_analysis_export_name,
)
from domain.coach_backend import get_coach                                           # noqa: E402
from domain.basic_coverage_coach import EXPERIMENTAL_TOPIC_IDS                       # noqa: E402
from domain.transcriber import (                                                      # noqa: E402
    whisper_available, load_whisper_model, transcribe_audio_file,
)
from domain.recorder import AudioRecorder, sounddevice_available                      # noqa: E402

DATA_ROOT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Whisper model cache (laden kost 5-30s; eenmalig per sessie)
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_whisper_model(model_name: str):
    """Laad Whisper-model en cache het voor de duur van de Streamlit-sessie."""
    return load_whisper_model(model_name)


# ---------------------------------------------------------------------------
# Live transcriptie fragment (v3.0)
# Auto-refresh elke 8s als opname actief is.
# Vereist st.fragment (Streamlit ≥ 1.37). Graceful fallback als niet beschikbaar.
# ---------------------------------------------------------------------------

def _live_transcription_fragment_fallback() -> None:
    st.caption("Live transcriptie vereist Streamlit ≥ 1.37. Upgrade: `pip install --upgrade streamlit`")


if hasattr(st, "fragment"):
    @st.fragment(run_every=8)
    def _live_transcription_fragment() -> None:
        """
        Draait elke 8s als live-opname actief is.
        - Haalt chunk op uit de recorder
        - Transcribeert via bestaande Whisper-laag
        - Appended aan state["transcript"]["tekst"] — nooit overschrijven
        - Roept st.rerun() aan zodat coach herberekent
        """
        recorder: AudioRecorder | None = st.session_state.get("_live_recorder")
        if recorder is None or not recorder.is_active:
            return

        _sk = st.session_state.get("_current_state_key")
        if not _sk:
            return
        _state = st.session_state.get(_sk)
        if _state is None:
            return

        # Timer tonen (fragment-niveau)
        elapsed = int(recorder.elapsed_seconds)
        mins, secs = divmod(elapsed, 60)
        st.caption(f"Opname: {mins:02d}:{secs:02d} — wacht op volgend blok...")

        # Chunk ophalen
        chunk_path = recorder.get_chunk()
        if chunk_path is None:
            return  # Nog niet genoeg audio — volgende auto-rerun

        # Transcriberen
        model_name = st.session_state.get("whisper_model", "base")
        t_result   = {"text": "", "language": "nl", "error": None}
        try:
            _model   = _get_whisper_model(model_name)
            t_result = transcribe_audio_file(chunk_path, _model)
        except Exception as exc:
            t_result["error"] = str(exc)
        finally:
            try:
                chunk_path.unlink()
            except OSError:
                pass

        if t_result["error"]:
            st.warning(f"Blok overgeslagen: {t_result['error']}")
            return

        chunk_text = t_result["text"].strip()
        if not chunk_text:
            return

        # Append — bestaande tekst wordt nooit vervangen
        current = (_state["transcript"].get("tekst") or "")
        sep     = " " if current and not current.endswith(("\n", " ")) else ""
        new_text = current + sep + chunk_text
        _state["transcript"]["tekst"]        = new_text
        _state["transcript"]["bron"]         = "live_whisper_chunked"
        st.session_state["transcript_paste"] = new_text

        # Volledige rerun zodat coach herberekent
        st.rerun()
else:
    _live_transcription_fragment = _live_transcription_fragment_fallback


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
st.caption("Spreekuurtool · v2.0 · lokale Whisper · geen online AI")


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
    st.caption("v2.0 · lokale Whisper · coach (9 kern + 6 exp.)")


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
# Bewaar state-key zodat het live-fragment er via session_state bij kan
st.session_state["_current_state_key"] = _state_key


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

        # ── Transcriptie via opname of audio-upload (lokale Whisper) ────────
        _whisper_ok = whisper_available()

        st.markdown("**Transcriptie via opname of audio-upload** — lokale Whisper")

        if not _whisper_ok:
            st.caption(
                "Whisper niet geïnstalleerd. "
                "Installeer: `pip install openai-whisper` + `brew install ffmpeg`. "
                "Zie INSTALL_MAC.md."
            )

        # Model selector — gedeeld voor opname en upload
        _whisper_model_name = st.selectbox(
            "Whisper-model",
            options=["base", "small", "medium", "large-v2"],
            index=0,
            key="whisper_model",
            disabled=not _whisper_ok,
            help=(
                "base: snel (aanbevolen voor testen)\n"
                "small: beter NL\n"
                "medium: beste kwaliteit medisch NL\n"
                "large-v2: traag op CPU"
            ),
        )

        # Gedeelde transcriptie-uitvoering voor opname en upload
        def _run_transcription(
            audio_bytes: bytes,
            bron: str,
            bestandsnaam: str,
            suffix: str = ".wav",
        ) -> None:
            with st.spinner(
                f"Transcriberen met Whisper ({_whisper_model_name}) — "
                "eerste keer: model laden duurt ca. 10-30s..."
            ):
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as _tmp:
                    _tmp.write(audio_bytes)
                    _tmp_path = Path(_tmp.name)
                try:
                    _model = _get_whisper_model(_whisper_model_name)
                    _t_result = transcribe_audio_file(_tmp_path, _model)
                finally:
                    try:
                        _tmp_path.unlink()
                    except OSError:
                        pass
            if _t_result["error"]:
                st.error(f"Transcriptie mislukt: {_t_result['error']}")
            else:
                state["transcript"]["tekst"]        = _t_result["text"]
                state["transcript"]["bron"]         = bron
                state["transcript"]["bestandsnaam"] = bestandsnaam
                st.session_state["transcript_paste"] = _t_result["text"]
                _n_w = len(_t_result["text"].split())
                st.success(
                    f"Getranscribeerd: {_n_w} woorden · "
                    f"taal: {_t_result['language']} · "
                    f"model: {_whisper_model_name}"
                )

        _tab_opname, _tab_upload, _tab_live = st.tabs(
            ["Microfoonopname", "Audio uploaden", "Live transcriptie (beta)"]
        )

        # ── Tab 1: Microfoonopname ────────────────────────────────────────
        with _tab_opname:
            if not _whisper_ok:
                st.caption("Whisper niet geïnstalleerd — zie bericht hierboven.")
            elif not hasattr(st, "audio_input"):
                st.caption(
                    "Microfoonopname vereist Streamlit ≥ 1.35. "
                    "Upgrade: `pip install --upgrade streamlit`"
                )
            else:
                st.caption(
                    "Klik op de microfoonknop om te starten · klik opnieuw om te stoppen.  \n"
                    "De browser vraagt eenmalig toestemming voor de microfoon.  \n"
                    "Gebruik bij voorkeur **Chrome** op macOS — Safari kan instabiel zijn."
                )
                try:
                    _recorded = st.audio_input(
                        "Opname",
                        key="mic_input",
                        label_visibility="collapsed",
                    )
                except Exception as _exc:
                    st.warning(
                        f"Microfooninput niet beschikbaar: {_exc}  \n"
                        "Controleer microfoontoestemming: macOS Systeeminstellingen → "
                        "Privacy → Microfoon → activeer de browser."
                    )
                    _recorded = None

                if _recorded is not None:
                    _rec_bytes = _recorded.getvalue()
                    st.caption(f"Opname gereed: {len(_rec_bytes) // 1024} KB · WAV")
                    st.audio(_rec_bytes, format="audio/wav")
                    if st.button(
                        "Transcribeer opname",
                        key="transcribe_recording_btn",
                        use_container_width=True,
                    ):
                        _run_transcription(
                            _rec_bytes,
                            bron="live_recording_local",
                            bestandsnaam="microfoonopname.wav",
                            suffix=".wav",
                        )

        # ── Tab 2: Audio-upload ───────────────────────────────────────────
        with _tab_upload:
            if not _whisper_ok:
                st.caption("Whisper niet geïnstalleerd — zie bericht hierboven.")
            audio_file = st.file_uploader(
                "Audio uploaden  (.m4a .mp3 .wav .mp4 .ogg .flac)",
                type=["m4a", "mp3", "wav", "mp4", "ogg", "flac"],
                key="audio_upload",
                disabled=not _whisper_ok,
                label_visibility="collapsed",
            )
            if audio_file is not None:
                st.caption(f"`{audio_file.name}` — {audio_file.size // 1024} KB")
                if st.button(
                    "Transcribeer audio",
                    key="transcribe_btn",
                    disabled=not _whisper_ok,
                    use_container_width=True,
                ):
                    _suffix = Path(audio_file.name).suffix.lower() or ".mp3"
                    _run_transcription(
                        audio_file.getvalue(),
                        bron="local_whisper",
                        bestandsnaam=audio_file.name,
                        suffix=_suffix,
                    )

        # ── Tab 3: Live transcriptie (beta) ───────────────────────────────
        with _tab_live:
            _sd_ok       = sounddevice_available()
            _frag_ok     = hasattr(st, "fragment")
            _live_ready  = _whisper_ok and _sd_ok and _frag_ok

            # Vereistencheck — altijd zichtbaar
            if not _whisper_ok:
                st.caption("❌ Whisper niet geïnstalleerd — `pip install openai-whisper`")
            if not _sd_ok:
                st.caption(
                    "❌ sounddevice/soundfile niet geïnstalleerd — "
                    "`pip install sounddevice soundfile numpy`  \n"
                    "Na installatie: herstart de app."
                )
            if not _frag_ok:
                st.caption(
                    "❌ Streamlit ≥ 1.37 vereist — "
                    "`pip install --upgrade streamlit`"
                )

            if not _live_ready:
                st.info("Installeer de ontbrekende dependencies om live transcriptie te activeren.")
            else:
                st.caption(
                    "Neemt op via de **systeemmicrofoon** (niet de browser).  \n"
                    "Verwerkt audio in blokken van ~8s. Transcript groeit automatisch.  \n"
                    "Coach herberekent na elk blok.  \n"
                    "Bestaande transcript-tekst blijft bewaard — nieuwe tekst wordt toegevoegd."
                )

                _live_recorder: AudioRecorder | None = st.session_state.get("_live_recorder")
                _is_recording = _live_recorder is not None and _live_recorder.is_active

                _col_start, _col_stop = st.columns(2)

                with _col_start:
                    if st.button(
                        "Start live transcriptie",
                        key="live_start_btn",
                        type="primary",
                        disabled=_is_recording,
                        use_container_width=True,
                    ):
                        with st.spinner(
                            f"Whisper-model laden ({_whisper_model_name})…"
                        ):
                            _get_whisper_model(_whisper_model_name)
                        _new_rec = AudioRecorder()
                        try:
                            _new_rec.start()
                            st.session_state["_live_recorder"] = _new_rec
                            state["transcript"]["bron"] = "live_whisper_chunked"
                            if not state["transcript"].get("bestandsnaam"):
                                state["transcript"]["bestandsnaam"] = "live_opname"
                            st.rerun()
                        except Exception as _exc:
                            _err_str = str(_exc)
                            if any(k in _err_str.lower() for k in ("portaudio", "device", "input")):
                                st.error(
                                    f"Microfoon niet bereikbaar: {_err_str}  \n"
                                    "Controleer: macOS Systeeminstellingen → "
                                    "Privacy en beveiliging → Microfoon → "
                                    "activeer **Terminal** of **Python**."
                                )
                            else:
                                st.error(f"Opname starten mislukt: {_err_str}")

                with _col_stop:
                    if st.button(
                        "Stop",
                        key="live_stop_btn",
                        disabled=not _is_recording,
                        use_container_width=True,
                    ):
                        if _live_recorder is not None:
                            _live_recorder.stop()
                            # Verwerk resterende audio in buffer
                            _final_chunk = _live_recorder.get_chunk()
                            if _final_chunk is not None:
                                with st.spinner("Laatste blok transcriberen..."):
                                    _mn = st.session_state.get("whisper_model", "base")
                                    _final_result = {"text": "", "error": None}
                                    try:
                                        _fm = _get_whisper_model(_mn)
                                        _final_result = transcribe_audio_file(_final_chunk, _fm)
                                    except Exception as _exc:
                                        _final_result["error"] = str(_exc)
                                    finally:
                                        try:
                                            _final_chunk.unlink()
                                        except OSError:
                                            pass
                                if _final_result["error"]:
                                    st.warning(f"Slotblok overgeslagen: {_final_result['error']}")
                                elif _final_result["text"].strip():
                                    _cur  = state["transcript"]["tekst"] or ""
                                    _sep  = " " if _cur and not _cur.endswith(("\n", " ")) else ""
                                    _new  = _cur + _sep + _final_result["text"].strip()
                                    state["transcript"]["tekst"]        = _new
                                    st.session_state["transcript_paste"] = _new
                            st.session_state["_live_recorder"] = None
                            st.success("Opname gestopt. Transcript compleet.")
                            st.rerun()

                # Status
                if _is_recording:
                    st.info(
                        "Opname actief — spreek in.  \n"
                        "Transcript verschijnt per blok van ~8s. "
                        "Coach herberekent na elk blok."
                    )

                # Fragment — auto-refresh voor chunk-verwerking
                _live_transcription_fragment()

        st.divider()

        # ── .txt import (MacWhisper / AutoScriber) ────────────────────────
        uploaded_txt = st.file_uploader(
            "Importeer transcript (.txt — bijv. MacWhisper of AutoScriber)",
            type=["txt"],
            key="transcript_upload",
            help="Laadt de bestandsinhoud als ruwe tekst. Geen automatische parsing.",
        )
        if uploaded_txt is not None:
            content = uploaded_txt.getvalue().decode("utf-8", errors="replace")
            state["transcript"]["tekst"]        = content
            state["transcript"]["bron"]         = "upload"
            state["transcript"]["bestandsnaam"] = uploaded_txt.name
            st.session_state["transcript_paste"] = content
            st.caption(f"Geladen: `{uploaded_txt.name}` — {len(content.split())} woorden")

        # ── Bewerkbaar tekstveld — altijd zichtbaar ───────────────────────
        transcript_val = st.text_area(
            "Plak of bewerk transcript",
            value=state["transcript"]["tekst"] or "",
            height=220,
            key="transcript_paste",
            placeholder="Plak hier een transcript, of transcribeer via audio hierboven...",
            label_visibility="collapsed",
        )
        # Handmatige bewerking: bron bijwerken
        if transcript_val != state["transcript"]["tekst"]:
            state["transcript"]["bron"] = "geplakt"
            state["transcript"]["bestandsnaam"] = ""
        state["transcript"]["tekst"] = transcript_val

        if transcript_val.strip():
            _bron_label = {
                "local_whisper": "lokale Whisper",
                "upload":        "geüploade .txt",
                "geplakt":       "handmatig",
            }.get(state["transcript"].get("bron", ""), "")
            n_woorden = len(transcript_val.split())
            n_regels  = transcript_val.count("\n") + 1
            _bron_str = f" · bron: {_bron_label}" if _bron_label else ""
            st.caption(f"{n_woorden} woorden · {n_regels} regels{_bron_str}")

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

    # ── Analyse-export (voor Anamnese_Anonymizer) ─────────────────────────
    st.subheader("Voor anonimisering in Anamnese_Anonymizer")
    st.caption(
        "Platte werktekst met alle aanwezige inhoud. "
        "Plak of laad dit bestand in Anamnese_Anonymizer."
    )

    analysis_txt = build_analysis_input_text(state, pid)
    analysis_fn  = default_analysis_export_name(state, pid)

    st.download_button(
        label="Download werktekst (.txt)",
        data=analysis_txt.encode("utf-8"),
        file_name=analysis_fn,
        mime="text/plain",
        key="dl_analysis",
        use_container_width=True,
    )

    with st.expander("Voorbeeld werktekst", expanded=False):
        st.code(analysis_txt, language=None)

    st.divider()

    # ── State JSON (debug) ────────────────────────────────────────────────
    with st.expander("State (JSON)", expanded=False):
        st.json(state)
