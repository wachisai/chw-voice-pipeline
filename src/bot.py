"""Telegram entry point.

Telegram rather than a purpose-built app for three reasons that hold in the
field: it is already installed, voice notes work on a feature-grade Android at
low bandwidth, and messages queue and send when signal returns rather than
failing. None of those are true of a custom app that has to be sideloaded,
updated and supported.

Run with:  python -m src.bot
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from .config import SETTINGS
from .extract import Extractor
from .pipeline import Pipeline, ProcessedReferral
from .sinks import CsvSink, SheetsSink
from .transcribe import ApiTranscriber

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("chw")


def build_pipeline() -> Pipeline:
    sink = (
        SheetsSink(SETTINGS.sheets_webhook_url)
        if SETTINGS.sheets_webhook_url
        else CsvSink(SETTINGS.output_csv)
    )
    return Pipeline(ApiTranscriber(), Extractor(), sink)


PIPELINE = None  # built on first use so import stays cheap


def _confirmation(processed: ProcessedReferral) -> str:
    patient = processed.extraction.referral.patient
    name = patient.patient_name or "name not captured"
    age = f"{patient.age_years}y" if patient.age_years is not None else "age not captured"
    village = patient.village or "village not captured"

    lines = [
        "Referral recorded.",
        f"{name}, {age}, {village}",
        f"Cost: KES {processed.cost.total_kes():.2f}",
    ]
    if processed.review_required:
        missing = ", ".join(processed.extraction.unclear_fields) or "key fields"
        lines.append(f"Flagged for supervisor review: {missing}")
    return "\n".join(lines)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global PIPELINE
    if PIPELINE is None:
        PIPELINE = build_pipeline()

    message = update.message
    if message is None:
        return
    voice = message.voice or message.audio
    if voice is None:
        return

    await message.chat.send_action("typing")
    telegram_file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.ogg"
        await telegram_file.download_to_drive(custom_path=str(path))
        try:
            processed = PIPELINE.process(path, source=f"telegram:{message.chat_id}")
        except Exception:
            log.exception("pipeline failed")
            await message.reply_text(
                "Could not process that recording. Please send it again, or "
                "type the referral instead."
            )
            return

    log.info("processed referral %s", processed.cost.format())
    await message.reply_text(_confirmation(processed))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Send a voice note describing the referral. Say the client's name, "
            "age, village, and why you are referring them."
        )


def main() -> None:
    if not SETTINGS.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set. See .env.example.")
    app = Application.builder().token(SETTINGS.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    log.info("listening for voice notes")
    app.run_polling()


if __name__ == "__main__":
    main()
