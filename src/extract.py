"""Transcript to structured MOH-100 record.

The design decision worth defending here is that the model is asked to leave
fields empty rather than infer them. A referral system that quietly invents an
age or a village produces a database that looks complete and is worse than no
database, because nobody knows which rows to distrust. So the prompt forbids
inference, and the model reports what it was unsure about in
``unclear_fields`` so those rows can be routed to a human.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import SETTINGS
from .schema import ExtractionResult, Referral

SYSTEM_PROMPT = """\
You convert spoken community health referrals into MOH-100 records.

MOH-100 is the Kenya Ministry of Health community referral form. The speaker
is a community health volunteer describing a client they are sending to a
health facility. They speak English, Swahili, or a mixture, and they do not
follow the order of the form.

Rules:

1. Record only what is said. If the speaker does not give a field, leave it
   null. Never infer, never fill from context, never use a plausible default.
   An empty field is correct. A guessed field is a defect.
2. Keep clinical content in the speaker's own terms. Do not convert a
   description into a diagnosis. "Homa kali kwa siku tatu" is recorded as
   stated, not as "suspected malaria".
3. Translate Swahili field values into English for storage, but do not
   paraphrase or summarise. Names and place names stay as spoken.
4. Ages given in months for infants become 0 completed years.
5. Never populate the receiving-officer block. That is completed at the
   facility, not by the speaker.
6. List in unclear_fields the dotted path of every field you guessed at or
   left empty because the audio was ambiguous. Set confidence below 0.6 when
   the record needs human review before use.
"""


@dataclass(frozen=True)
class Extraction:
    result: ExtractionResult
    input_tokens: int
    output_tokens: int


class Extractor:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        from openai import OpenAI

        key = api_key or SETTINGS.openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        self._client = OpenAI(api_key=key)
        self._model = model or SETTINGS.extraction_model

    def extract(self, transcript: str) -> Extraction:
        completion = self._client.beta.chat.completions.parse(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript:\n\n{transcript}"},
            ],
            response_format=ExtractionResult,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("Model returned no parseable structured output.")
        usage = completion.usage
        return Extraction(
            result=parsed,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )


class FixtureExtractor:
    """Offline stand-in that returns a stored extraction for a known transcript.

    These are golden files, not a second implementation. Each synthetic
    transcript in ``data/synthetic`` has a hand-checked ``.expected.json``
    beside it recording what a correct extraction looks like, including the
    fields that should be left empty. They serve two purposes: they let the
    schema, sinks, cost model and review routing be tested without network
    access or spend, and they are the regression baseline when the prompt or
    the model changes.

    It answers only for transcripts it has seen. It is not an extractor.
    """

    def __init__(self, fixture_dir: str | Path = "data/synthetic") -> None:
        self._dir = Path(fixture_dir)
        self._index: dict[str, Path] = {}
        for transcript_path in sorted(self._dir.glob("*.txt")):
            expected = transcript_path.with_suffix(".expected.json")
            if expected.exists():
                key = _normalise(transcript_path.read_text(encoding="utf-8"))
                self._index[key] = expected

    def extract(self, transcript: str) -> Extraction:
        expected = self._index.get(_normalise(transcript))
        if expected is None:
            raise KeyError(
                "No stored extraction for this transcript. FixtureExtractor only "
                "answers for the synthetic corpus in data/synthetic. Set "
                "OPENAI_API_KEY and drop --offline to extract for real."
            )
        result = ExtractionResult.model_validate_json(
            expected.read_text(encoding="utf-8")
        )
        # Median observed usage over the corpus, so offline runs still report a
        # cost of the right order rather than zero.
        return Extraction(result=result, input_tokens=520, output_tokens=300)


def _normalise(text: str) -> str:
    return " ".join(text.split()).lower()


def needs_review(result: ExtractionResult, threshold: float | None = None) -> bool:
    """Whether this record should reach a supervisor before it reaches a report."""
    limit = SETTINGS.review_threshold if threshold is None else threshold
    if result.confidence < limit:
        return True
    patient = result.referral.patient
    # A referral with no name and no village cannot be followed up, whatever
    # the model's confidence.
    return not (patient.patient_name and patient.village)


__all__ = [
    "Extractor",
    "FixtureExtractor",
    "Extraction",
    "needs_review",
    "Referral",
    "SYSTEM_PROMPT",
]
