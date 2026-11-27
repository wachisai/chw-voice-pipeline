"""Where a completed referral goes.

Two sinks. CSV is the default and needs nothing. The Google Apps Script sink
posts to a web app bound to a spreadsheet, which is how this runs in practice:
a county team already has Google Workspace, already knows how to read a sheet,
and does not need a database to be provisioned or maintained for them.

Choosing Sheets is a deployment decision, not a technical preference. The
constraint that matters at sub-county level is who administers the thing after
the project ends.
"""

from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .schema import SHEET_COLUMNS, Referral, to_row

META_COLUMNS = ["captured_at", "source", "confidence", "needs_review", "unclear_fields"]


class Sink(Protocol):
    def write(self, referral: Referral, meta: dict) -> None: ...


class CsvSink:
    """Append to a local CSV, writing the header on first use."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, referral: Referral, meta: dict) -> None:
        new_file = not self._path.exists()
        with self._path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new_file:
                writer.writerow(META_COLUMNS + SHEET_COLUMNS)
            writer.writerow(_meta_row(meta) + to_row(referral))


class SheetsSink:
    """POST to a Google Apps Script web app deployed against a spreadsheet.

    The Apps Script side is in ``apps_script/Code.gs``. It is nine lines and
    appends the posted row. Keeping the logic here rather than in Apps Script
    means the schema has one owner.
    """

    def __init__(self, webhook_url: str, timeout: int = 15) -> None:
        if not webhook_url:
            raise ValueError("SHEETS_WEBHOOK_URL is not set.")
        self._url = webhook_url
        self._timeout = timeout

    def write(self, referral: Referral, meta: dict) -> None:
        payload = {
            "header": META_COLUMNS + SHEET_COLUMNS,
            "row": _meta_row(meta) + to_row(referral),
        }
        request = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            if response.status >= 300:
                raise RuntimeError(f"Sheets webhook returned {response.status}")


def _meta_row(meta: dict) -> list[str]:
    return [
        meta.get("captured_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        str(meta.get("source", "")),
        f"{meta.get('confidence', 0.0):.2f}",
        "yes" if meta.get("needs_review") else "no",
        "; ".join(meta.get("unclear_fields", [])),
    ]
