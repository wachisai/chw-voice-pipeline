"""Tests that run without an API key or network access.

They exercise the parts that carry the risk: the schema contract with the
spreadsheet, the cost model behind the headline claim, and the rule that
decides whether a record reaches a supervisor before it reaches a report.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.costs import TYPICAL_REFERRAL, Usage, estimate_cost  # noqa: E402
from src.extract import FixtureExtractor, needs_review  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.schema import SHEET_COLUMNS, ExtractionResult  # noqa: E402
from src.sinks import META_COLUMNS, CsvSink  # noqa: E402
from src.transcribe import EchoTranscriber  # noqa: E402

CORPUS = sorted(Path("data/synthetic").glob("*.txt"))


@pytest.fixture
def pipeline(tmp_path: Path) -> Pipeline:
    return Pipeline(
        EchoTranscriber(), FixtureExtractor(), CsvSink(tmp_path / "out.csv")
    )


def test_corpus_is_present():
    assert len(CORPUS) >= 5, "synthetic corpus is missing"


@pytest.mark.parametrize("transcript", CORPUS, ids=lambda p: p.stem)
def test_every_transcript_produces_a_valid_record(transcript, pipeline):
    processed = pipeline.process(transcript, source="test")
    assert isinstance(processed.extraction, ExtractionResult)
    assert 0.0 <= processed.extraction.confidence <= 1.0


@pytest.mark.parametrize("transcript", CORPUS, ids=lambda p: p.stem)
def test_receiving_block_is_never_populated(transcript, pipeline):
    """The facility completes block 4. The pipeline must not fill it in."""
    receiving = pipeline.process(transcript, source="test").extraction.referral.receiving
    assert receiving.model_dump(exclude_none=True) == {}


def test_row_width_matches_header(tmp_path):
    """A schema change that reorders the sheet is the failure mode to catch."""
    out = tmp_path / "out.csv"
    pipe = Pipeline(EchoTranscriber(), FixtureExtractor(), CsvSink(out))
    for transcript in CORPUS:
        pipe.process(transcript, source="test")

    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0] == META_COLUMNS + SHEET_COLUMNS
    expected_width = len(META_COLUMNS) + len(SHEET_COLUMNS)
    assert all(len(row) == expected_width for row in rows[1:])
    assert len(rows) == len(CORPUS) + 1


def test_sparse_referral_is_routed_to_review(pipeline):
    """003 is the recording where the CHV does not know the client's name.

    It must not pass silently into the dataset.
    """
    processed = pipeline.process(Path("data/synthetic/003.txt"), source="test")
    assert processed.review_required is True
    assert processed.extraction.confidence < 0.6
    assert "patient.patient_name" in processed.extraction.unclear_fields


def test_complete_referral_is_not_routed_to_review(pipeline):
    processed = pipeline.process(Path("data/synthetic/004.txt"), source="test")
    assert processed.review_required is False


def test_infant_age_in_months_becomes_zero_years(pipeline):
    """Eight months is 0 completed years, not 8."""
    processed = pipeline.process(Path("data/synthetic/001.txt"), source="test")
    assert processed.extraction.referral.patient.age_years == 0


def test_unstated_date_is_left_empty(pipeline):
    """001 says 'the fifteenth' with no month or year. Guessing is a defect."""
    processed = pipeline.process(Path("data/synthetic/001.txt"), source="test")
    assert processed.extraction.referral.patient.referral_date is None
    assert "patient.referral_date" in processed.extraction.unclear_fields


def test_high_confidence_record_still_flags_missing_identifiers():
    """Confidence alone must not clear a record that cannot be followed up."""
    result = ExtractionResult.model_validate_json(
        Path("data/synthetic/002.expected.json").read_text(encoding="utf-8")
    )
    assert result.confidence > 0.6
    result.referral.patient.village = None
    assert needs_review(result) is True


def test_typical_referral_costs_under_one_shilling():
    """The claim the repository makes, as an assertion."""
    cost = estimate_cost(TYPICAL_REFERRAL)
    assert cost.total_kes() < 1.0


def test_cost_scales_with_audio_length():
    short = estimate_cost(Usage(audio_seconds=20, input_tokens=400, output_tokens=250))
    long = estimate_cost(Usage(audio_seconds=120, input_tokens=900, output_tokens=400))
    assert long.total_usd > short.total_usd
    # Transcription dominates, which is why keeping recordings short matters.
    assert long.transcription_usd > long.extraction_usd


def test_fixture_extractor_refuses_unknown_transcripts():
    with pytest.raises(KeyError):
        FixtureExtractor().extract("a referral it has never seen")
