"""MOH-100 referral schema.

MOH-100 is the Kenya Ministry of Health community health referral form. A
community health volunteer (CHV) fills it when referring a client from the
household to a link health facility.

The paper form carries 22 fields across four blocks. This module is the single
source of truth for those fields: the extraction prompt, the JSON schema sent
to the model, the sheet header row and the tests all derive from it, so the
form definition never drifts between components.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Dates and times are carried as strings rather than date/time objects. The
# strict JSON schema mode used for structured extraction does not support the
# "format" keyword, so a typed date field would be rejected by the API. They
# are validated here instead, which keeps the constraint without the
# incompatibility.


def _validate_iso_date(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _validate_iso_time(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None


class Sex(str, Enum):
    male = "M"
    female = "F"
    unknown = "unknown"


class PatientBlock(BaseModel):
    """Block 1 of the paper form: patient / client data."""

    referral_date: Optional[str] = Field(
        None, description="Date of referral as YYYY-MM-DD. Null if not stated."
    )
    referral_time: Optional[str] = Field(
        None, description="Time of referral as 24-hour HH:MM. Null if not stated."
    )

    _v_date = field_validator("referral_date")(_validate_iso_date)
    _v_time = field_validator("referral_time")(_validate_iso_time)
    patient_name: Optional[str] = Field(
        None, description="Full name of the person being referred."
    )
    sex: Sex = Field(
        Sex.unknown,
        description="M or F. Use 'unknown' when the recording does not say.",
    )
    age_years: Optional[int] = Field(
        None,
        ge=0,
        le=120,
        description=(
            "Age in completed years. If the speaker gives months for an infant, "
            "convert to years and round down, so 'eight months' becomes 0."
        ),
    )
    village: Optional[str] = Field(None, description="Village of residence.")


class ReferralBlock(BaseModel):
    """Block 2: why the client is being sent."""

    reasons: Optional[str] = Field(
        None, description="Reason or reasons for referral, as stated."
    )
    main_problems: Optional[str] = Field(
        None, description="Main presenting problem or problems."
    )
    treatment_given: Optional[str] = Field(
        None, description="Any treatment the CHV gave before referring."
    )
    comments: Optional[str] = Field(None, description="Free-text comments.")


class ChvBlock(BaseModel):
    """Block 3: who is making the referral and from where."""

    chv_name: Optional[str] = None
    chv_mobile: Optional[str] = Field(
        None, description="Mobile number, digits only, no country code prefix."
    )
    chv_village: Optional[str] = None
    sub_location: Optional[str] = None
    location: Optional[str] = None
    ward: Optional[str] = None
    community_unit: Optional[str] = None
    link_health_facility: Optional[str] = None


class ReceivingBlock(BaseModel):
    """Block 4: completed at the facility, not by the CHV.

    Kept in the schema because the row has to match the paper form, but the
    voice pipeline never populates it. It exists so the facility can complete
    the record without a second data structure.
    """

    officer_name: Optional[str] = None
    received_date: Optional[str] = None
    received_time: Optional[str] = None
    profession: Optional[str] = None
    receiving_facility: Optional[str] = None

    _v_date = field_validator("received_date")(_validate_iso_date)
    _v_time = field_validator("received_time")(_validate_iso_time)


class Referral(BaseModel):
    """A complete MOH-100 record."""

    patient: PatientBlock = Field(default_factory=PatientBlock)
    referral: ReferralBlock = Field(default_factory=ReferralBlock)
    chv: ChvBlock = Field(default_factory=ChvBlock)
    receiving: ReceivingBlock = Field(default_factory=ReceivingBlock)


class ExtractionResult(BaseModel):
    """What the extraction step returns.

    ``confidence`` and ``unclear_fields`` exist so a supervisor can triage.
    A referral the model was unsure about should reach a human before it
    reaches a report, and that is only possible if the model is asked to say
    so at extraction time rather than being asked to guess.
    """

    referral: Referral
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "How well the audio supported the extraction. Below 0.6 means the "
            "record should be reviewed by a human before it is used."
        ),
    )
    unclear_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Dotted field paths that were guessed or left empty because the "
            "recording was ambiguous, e.g. ['patient.age_years']."
        ),
    )
    detected_language: Optional[str] = Field(
        None, description="ISO 639-1 code of the dominant language in the audio."
    )


# Column order for the flat sheet row. Kept explicit rather than derived so
# that reordering the model cannot silently reorder a live spreadsheet.
SHEET_COLUMNS: list[str] = [
    "patient.referral_date",
    "patient.referral_time",
    "patient.patient_name",
    "patient.sex",
    "patient.age_years",
    "patient.village",
    "referral.reasons",
    "referral.main_problems",
    "referral.treatment_given",
    "referral.comments",
    "chv.chv_name",
    "chv.chv_mobile",
    "chv.chv_village",
    "chv.sub_location",
    "chv.location",
    "chv.ward",
    "chv.community_unit",
    "chv.link_health_facility",
    "receiving.officer_name",
    "receiving.received_date",
    "receiving.received_time",
    "receiving.profession",
    "receiving.receiving_facility",
]


def to_row(referral: Referral) -> list[str]:
    """Flatten a Referral into SHEET_COLUMNS order, as strings."""
    payload = referral.model_dump(mode="json")
    row: list[str] = []
    for path in SHEET_COLUMNS:
        block, field = path.split(".")
        value = payload.get(block, {}).get(field)
        row.append("" if value is None else str(value))
    return row
