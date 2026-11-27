"""Speech to text.

Two implementations behind one interface. ``ApiTranscriber`` calls the hosted
Whisper endpoint. ``EchoTranscriber`` reads a plain-text file and returns it
unchanged, which is what lets the whole pipeline be exercised, tested and
demonstrated without an API key or a bill.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import SETTINGS


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    audio_seconds: float


def audio_duration_seconds(path: Path) -> float:
    """Duration of an audio file.

    Uses the wave module for PCM WAV, which needs no dependency, and falls
    back to a bitrate estimate for compressed formats. The estimate only
    affects the reported cost, never the extraction, and Telegram voice notes
    are OGG Opus at a predictable bitrate.
    """
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    # Telegram voice notes are OGG Opus, typically 16 kbps mono.
    assumed_bits_per_second = 16_000
    return (path.stat().st_size * 8) / assumed_bits_per_second


class Transcriber(Protocol):
    def transcribe(self, path: Path) -> Transcript: ...


class EchoTranscriber:
    """Offline stand-in. Reads a .txt file as if it had been spoken.

    Used by the tests and by ``scripts/run_local.py --offline`` so that the
    extraction logic can be developed and reviewed without network access.
    """

    def transcribe(self, path: Path) -> Transcript:
        text = Path(path).read_text(encoding="utf-8").strip()
        # 150 words per minute is an unhurried speaking pace.
        seconds = len(text.split()) / 150.0 * 60.0
        return Transcript(text=text, language=None, audio_seconds=round(seconds, 1))


class ApiTranscriber:
    """Hosted Whisper.

    The prompt is a vocabulary hint, not an instruction. Whisper uses it to
    bias decoding, which matters here because Kenyan place names, facility
    names and the Swahili and Sheng that CHVs actually speak are all outside
    its strongest training distribution.
    """

    VOCABULARY_HINT = (
        "MOH-100 referral. Kenya community health. CHV, CHP, community unit, "
        "sub-location, link health facility, dispensary, Level 4 hospital, "
        "ANC, immunization, malaria, mtoto, mgonjwa, homa, kuharisha, kupima."
    )

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        from openai import OpenAI  # imported lazily so offline use needs no SDK

        key = api_key or SETTINGS.openai_api_key
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env, or run "
                "with --offline to use the synthetic transcripts."
            )
        self._client = OpenAI(api_key=key)
        self._model = model or SETTINGS.transcription_model

    def transcribe(self, path: Path) -> Transcript:
        path = Path(path)
        with path.open("rb") as handle:
            response = self._client.audio.transcriptions.create(
                model=self._model,
                file=handle,
                prompt=self.VOCABULARY_HINT,
                response_format="verbose_json",
            )
        return Transcript(
            text=response.text.strip(),
            language=getattr(response, "language", None),
            audio_seconds=float(
                getattr(response, "duration", None) or audio_duration_seconds(path)
            ),
        )


def get_transcriber(offline: bool = False) -> Transcriber:
    return EchoTranscriber() if offline else ApiTranscriber()
