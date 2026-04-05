"""
domain/recorder.py — Anamnese_App

Lokale audio-opname voor live transcriptie (v3.0).

AudioRecorder neemt continu op via sounddevice in een achtergrondthread.
De callback buffert ruwe samples; get_chunk() extraheert en schrijft WAV.

ONTWERP
- Callback-thread (sounddevice): alleen append naar buffer, geen I/O
- Hoofdthread (Streamlit fragment): roept get_chunk() aan, verwerkt WAV
- threading.Lock beschermt de buffer tegen race conditions

AFHANKELIJKHEDEN (niet verplicht bij import — lazy checks)
  pip install sounddevice soundfile numpy

GEBRUIK
  recorder = AudioRecorder()
  recorder.start()                 # start achtergrondthread + stream
  wav_path = recorder.get_chunk()  # elk stuk audio → Path naar temp WAV
  recorder.stop()                  # flush + afsluiten
"""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Beschikbaarheidscheck
# ---------------------------------------------------------------------------

def sounddevice_available() -> bool:
    """Retourneer True als sounddevice én soundfile geïnstalleerd zijn."""
    try:
        import sounddevice  # noqa: F401
        import soundfile    # noqa: F401
        import numpy        # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# AudioRecorder
# ---------------------------------------------------------------------------

_SAMPLERATE     = 16_000   # Hz — Whisper verwacht 16 kHz
_CHANNELS       = 1        # mono
_MIN_DURATION_S = 2        # minimale chunklengte in seconden


class AudioRecorder:
    """
    Neemt continu op via sounddevice.InputStream.

    Thread-safe:
    - Callback (audio-thread):  append frames naar self._frames
    - Hoofdthread:              get_chunk() vergrendelt _lock, leegt buffer
    """

    def __init__(
        self,
        samplerate: int = _SAMPLERATE,
        channels: int   = _CHANNELS,
    ) -> None:
        self.samplerate = samplerate
        self.channels   = channels

        self._frames: list = []          # list[np.ndarray]
        self._lock          = threading.Lock()
        self._stream        = None
        self._active        = False
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Publieke API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start de InputStream en de callback-thread.
        Raises PortAudioError als microfoon niet beschikbaar is.
        """
        import sounddevice as sd

        def _callback(indata, frames, time_info, status):
            # Draait in sounddevice's real-time thread — alleen lichte operaties
            with self._lock:
                if self._active:
                    self._frames.append(indata.copy())

        self._frames.clear()
        self._active     = True
        self._start_time = time.time()

        self._stream = sd.InputStream(
            samplerate = self.samplerate,
            channels   = self.channels,
            dtype      = "float32",
            callback   = _callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop de stream en sluit af. Bufferinhoud blijft beschikbaar voor get_chunk()."""
        self._active = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_chunk(self) -> Path | None:
        """
        Extraheer alle gebufferde audio, schrijf als WAV-tempbestand.

        - Vergrendelt de buffer atomair en leegt die
        - Retourneert None als er te weinig audio is (< MIN_DURATION_S)
        - Caller is verantwoordelijk voor het verwijderen van het bestand

        Kan zowel tijdens als na opname worden aangeroepen.
        """
        import numpy as np
        import soundfile as sf

        with self._lock:
            if not self._frames:
                return None
            frames     = list(self._frames)
            self._frames.clear()

        audio = np.concatenate(frames, axis=0)

        # Mono: pak eerste kanaal als input meerkanaals is
        if audio.ndim > 1:
            audio = audio[:, 0]

        duration_s = len(audio) / self.samplerate
        if duration_s < _MIN_DURATION_S:
            return None

        tmp = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, prefix="anamnese_chunk_"
        )
        tmp.close()
        sf.write(tmp.name, audio, self.samplerate, subtype="FLOAT")
        return Path(tmp.name)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def elapsed_seconds(self) -> float:
        if not self._active:
            return 0.0
        return time.time() - self._start_time
