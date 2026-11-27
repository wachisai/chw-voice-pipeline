"""Runtime configuration and unit-cost rates.

Every price in this file is a published API rate, not an estimate. They are
kept here rather than hard-coded so that the cost claim in the README can be
recomputed by anyone who clones the repository, against whatever the rates are
on the day they run it.

Verify against https://platform.openai.com/docs/pricing before quoting the
figure anywhere it matters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


# --------------------------------------------------------------------------
# Rates. Measured 1 September 2026. Lifecycle re-checked 25 November 2026.
#
# Both default models are deprecated. whisper-1 shuts down 26 Feb 2027
# (replacement: gpt-transcribe or gpt-live-transcribe). gpt-4o-mini-2024-07-18
# shuts down 14 Jan 2027 (replacement: gpt-6-luna, published at $0.05 / $0.25
# per million tokens). See the Model lifecycle section of the README.
#
# Change the models with TRANSCRIPTION_MODEL and EXTRACTION_MODEL in .env, and
# the rates below with the RATE_* variables. Transcription is about 95 percent
# of the unit cost, so the headline figure is only as current as that one rate.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Rates:
    transcription_usd_per_minute: float = 0.006   # whisper-1, deprecated
    llm_usd_per_million_input: float = 0.15       # gpt-4o-mini, deprecated
    llm_usd_per_million_output: float = 0.60      # gpt-4o-mini, deprecated
    usd_to_kes: float = 129.0                     # indicative, update before quoting

    @classmethod
    def from_env(cls) -> "Rates":
        return cls(
            transcription_usd_per_minute=float(
                os.getenv("RATE_TRANSCRIPTION_USD_PER_MIN", cls.transcription_usd_per_minute)
            ),
            llm_usd_per_million_input=float(
                os.getenv("RATE_LLM_USD_PER_M_INPUT", cls.llm_usd_per_million_input)
            ),
            llm_usd_per_million_output=float(
                os.getenv("RATE_LLM_USD_PER_M_OUTPUT", cls.llm_usd_per_million_output)
            ),
            usd_to_kes=float(os.getenv("RATE_USD_TO_KES", cls.usd_to_kes)),
        )


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    telegram_bot_token: str | None
    sheets_webhook_url: str | None
    transcription_model: str
    extraction_model: str
    output_csv: str
    review_threshold: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            sheets_webhook_url=os.getenv("SHEETS_WEBHOOK_URL"),
            transcription_model=os.getenv("TRANSCRIPTION_MODEL", "whisper-1"),
            extraction_model=os.getenv("EXTRACTION_MODEL", "gpt-4o-mini"),
            output_csv=os.getenv("OUTPUT_CSV", "data/referrals.csv"),
            review_threshold=float(os.getenv("REVIEW_THRESHOLD", "0.6")),
        )


RATES = Rates.from_env()
SETTINGS = Settings.from_env()
