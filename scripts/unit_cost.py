#!/usr/bin/env python3
"""Reproduce the cost claim in the README.

    python scripts/unit_cost.py
    python scripts/unit_cost.py --seconds 90 --volume 40000

Rates come from src/config.py and can be overridden by environment variables,
so the figure can be recomputed against current API pricing rather than taken
on trust.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import RATES  # noqa: E402
from src.costs import TYPICAL_REFERRAL, Usage, estimate_cost  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=TYPICAL_REFERRAL.audio_seconds)
    parser.add_argument("--input-tokens", type=int, default=TYPICAL_REFERRAL.input_tokens)
    parser.add_argument("--output-tokens", type=int, default=TYPICAL_REFERRAL.output_tokens)
    parser.add_argument(
        "--volume",
        type=int,
        default=10_000,
        help="Referrals per month, for the programme-level figure",
    )
    args = parser.parse_args()

    usage = Usage(
        audio_seconds=args.seconds,
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
    )
    cost = estimate_cost(usage)

    print("Rates in use")
    print(f"  transcription      ${RATES.transcription_usd_per_minute:.4f} / minute")
    print(f"  extraction input   ${RATES.llm_usd_per_million_input:.2f} / 1M tokens")
    print(f"  extraction output  ${RATES.llm_usd_per_million_output:.2f} / 1M tokens")
    print(f"  exchange rate      KES {RATES.usd_to_kes:.1f} / USD")
    print()
    print(f"One referral ({usage.audio_seconds:.0f}s audio, "
          f"{usage.input_tokens} in / {usage.output_tokens} out)")
    print(f"  transcription      ${cost.transcription_usd:.6f}")
    print(f"  extraction         ${cost.extraction_usd:.6f}")
    print(f"  total              ${cost.total_usd:.6f}  =  KES {cost.total_kes():.3f}")
    print()
    monthly_usd = cost.total_usd * args.volume
    print(f"At {args.volume:,} referrals a month")
    print(f"  ${monthly_usd:,.2f} / month   KES {monthly_usd * RATES.usd_to_kes:,.0f} / month")
    print(f"  ${monthly_usd * 12:,.2f} / year")
    print()
    print("Excludes hosting. The bot runs on a single small VM; at this volume")
    print("compute is a larger line item than inference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
