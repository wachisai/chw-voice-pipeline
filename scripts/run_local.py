#!/usr/bin/env python3
"""Run one referral through the pipeline from the command line.

Offline, no API key, using the synthetic corpus:

    python scripts/run_local.py --offline data/synthetic/001.txt

Against the real APIs, with an audio file:

    python scripts/run_local.py path/to/voice-note.ogg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import SETTINGS  # noqa: E402
from src.extract import Extractor, FixtureExtractor  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.sinks import CsvSink  # noqa: E402
from src.transcribe import ApiTranscriber, EchoTranscriber  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Audio file, or a .txt transcript with --offline")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the synthetic corpus and stored extractions. No API key, no spend.",
    )
    parser.add_argument("--csv", default=SETTINGS.output_csv, help="Where to append the row")
    parser.add_argument("--json", action="store_true", help="Print the full record as JSON")
    args = parser.parse_args()

    if args.offline:
        pipeline = Pipeline(EchoTranscriber(), FixtureExtractor(), CsvSink(args.csv))
    else:
        pipeline = Pipeline(ApiTranscriber(), Extractor(), CsvSink(args.csv))

    processed = pipeline.process(args.input, source="cli")
    patient = processed.extraction.referral.patient

    print(f"Transcript      {processed.transcript.text[:88]}...")
    print(f"Audio           {processed.transcript.audio_seconds:.0f}s")
    print(f"Client          {patient.patient_name or '(not captured)'}")
    print(f"Age / sex       {patient.age_years if patient.age_years is not None else '?'} / {patient.sex.value}")
    print(f"Village         {patient.village or '(not captured)'}")
    print(f"Facility        {processed.extraction.referral.chv.link_health_facility or '(not captured)'}")
    print(f"Confidence      {processed.extraction.confidence:.2f}")
    print(f"Unclear fields  {', '.join(processed.extraction.unclear_fields) or 'none'}")
    print(f"Review needed   {'YES' if processed.review_required else 'no'}")
    print(f"Cost            {processed.cost.format()}")
    print(f"Appended to     {args.csv}")

    if args.json:
        print()
        print(json.dumps(processed.extraction.model_dump(mode="json"), indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
