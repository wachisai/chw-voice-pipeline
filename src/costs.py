"""Unit economics for one referral.

The claim this repository makes is that a referral costs under one Kenyan
shilling to capture and structure. That claim is only worth anything if it is
reproducible, so it is computed here from metered usage rather than asserted.

``Usage`` is populated by the pipeline from the actual audio duration and the
token counts the API returns, so ``estimate_cost`` on a real run reports what
the run actually cost, not what a run of that shape might cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import RATES, Rates


@dataclass(frozen=True)
class Usage:
    audio_seconds: float
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Cost:
    transcription_usd: float
    extraction_usd: float

    @property
    def total_usd(self) -> float:
        return self.transcription_usd + self.extraction_usd

    def total_kes(self, rates: Rates = RATES) -> float:
        return self.total_usd * rates.usd_to_kes

    def format(self, rates: Rates = RATES) -> str:
        return (
            f"transcription ${self.transcription_usd:.5f} + "
            f"extraction ${self.extraction_usd:.5f} = "
            f"${self.total_usd:.5f} (KES {self.total_kes(rates):.3f})"
        )


def estimate_cost(usage: Usage, rates: Rates = RATES) -> Cost:
    """Cost of a single referral, in USD, from metered usage."""
    transcription = (usage.audio_seconds / 60.0) * rates.transcription_usd_per_minute
    extraction = (
        usage.input_tokens * rates.llm_usd_per_million_input / 1_000_000
        + usage.output_tokens * rates.llm_usd_per_million_output / 1_000_000
    )
    return Cost(transcription_usd=transcription, extraction_usd=extraction)


# A representative referral, used for the README figure and by the tests.
# 45 seconds of audio is what a CHV takes to describe a referral unhurried.
# The token counts are the median observed over the synthetic corpus.
TYPICAL_REFERRAL = Usage(audio_seconds=45.0, input_tokens=520, output_tokens=300)
