"""
domain/transcriber.py — Anamnese_App

Lokale Whisper-transcriptie van audiobestanden.

Geen LLM, geen netwerk, geen anonimisering.
Whisper draait volledig lokaal via CPU of Apple Silicon MPS.

Publieke API:
    whisper_available()                       -> bool
    load_whisper_model(model_name)            -> whisper.Whisper
    transcribe_audio_file(path, model)        -> dict

Dependencies:
    pip install openai-whisper
    brew install ffmpeg          # vereist door whisper voor audio-decodering
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Beschikbaarheidscheck
# ---------------------------------------------------------------------------

def whisper_available() -> bool:
    """Retourneer True als openai-whisper geïnstalleerd is."""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Model laden
# ---------------------------------------------------------------------------

def load_whisper_model(model_name: str):
    """
    Laad een Whisper-model op schijf (of download het de eerste keer).

    Modellen en hun afweging:
        tiny    —  39 MB  — snel, lagere nauwkeurigheid NL
        base    —  74 MB  — goed startpunt, snel (aanbevolen v1)
        small   — 244 MB  — beter NL, redelijke snelheid
        medium  — 769 MB  — beste kwaliteit voor medisch NL
        large-v2 / large-v3 — 1.5 GB — traag op CPU, beste kwaliteit

    Op Apple Silicon (M1/M2/M3) wordt automatisch Metal (MPS) gebruikt
    als torch met MPS-support geïnstalleerd is — geen configuratie nodig.
    """
    import whisper
    return whisper.load_model(model_name)


# ---------------------------------------------------------------------------
# Transcriptie
# ---------------------------------------------------------------------------

def transcribe_audio_file(audio_path: Path, model) -> dict:
    """
    Transcribeer een lokaal audiobestand met een al geladen Whisper-model.

    Parameters:
        audio_path  : pad naar het audiobestand (.m4a, .mp3, .wav, .mp4, ...)
        model       : geladen Whisper-model (uit load_whisper_model)

    Retourneert:
        {
            "text":     str,        # volledige transcriptietekst
            "language": str,        # gedetecteerde taalcode ("nl", "en", ...)
            "error":    str | None  # foutmelding bij mislukking
        }

    fp16=False: voorkomt waarschuwingen op CPU; op GPU wordt automatisch fp16 gebruikt.
    """
    try:
        result = model.transcribe(
            str(audio_path),
            language="nl",
            fp16=False,
        )
        return {
            "text":     result["text"].strip(),
            "language": result.get("language", "nl"),
            "error":    None,
        }
    except Exception as exc:
        return {
            "text":     "",
            "language": "",
            "error":    str(exc),
        }
