"""Orchestration: audio in, structured referral and a metered cost out."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .costs import Cost, Usage, estimate_cost
from .extract import Extraction, Extractor, needs_review
from .schema import ExtractionResult
from .sinks import Sink
from .transcribe import Transcriber, Transcript


@dataclass(frozen=True)
class ProcessedReferral:
    transcript: Transcript
    extraction: ExtractionResult
    cost: Cost
    review_required: bool
    source: str

    def meta(self) -> dict:
        return {
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": self.source,
            "confidence": self.extraction.confidence,
            "needs_review": self.review_required,
            "unclear_fields": self.extraction.unclear_fields,
        }


class Pipeline:
    def __init__(
        self,
        transcriber: Transcriber,
        extractor: Extractor,
        sink: Sink | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._extractor = extractor
        self._sink = sink

    def process(self, audio_path: str | Path, source: str = "local") -> ProcessedReferral:
        path = Path(audio_path)
        transcript = self._transcriber.transcribe(path)
        extraction: Extraction = self._extractor.extract(transcript.text)

        cost = estimate_cost(
            Usage(
                audio_seconds=transcript.audio_seconds,
                input_tokens=extraction.input_tokens,
                output_tokens=extraction.output_tokens,
            )
        )

        processed = ProcessedReferral(
            transcript=transcript,
            extraction=extraction.result,
            cost=cost,
            review_required=needs_review(extraction.result),
            source=source,
        )

        if self._sink is not None:
            self._sink.write(processed.extraction.referral, processed.meta())

        return processed
