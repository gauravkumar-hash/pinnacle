"""
Marketing / consent notification models.

Three tables + one lazily-created preference row per patient:

- patient_notification_preferences            -> per-patient marketing opt-in flag + audit
- backend_notification_campaigns              -> one row per broadcast (consent notice / marketing blast)
- backend_notification_campaign_recipients    -> outbox queue, one row per targeted user, drained in
                                                 small chunks by the scheduler so a 200k-user blast
                                                 never hits the DB (or Expo) all at once

DB columns for the small enumerations are plain strings on purpose - this keeps the Alembic
migration portable across local / staging / production with no native PostgreSQL ENUM types to
create, alter or drop. The allowed values live in the *Enum classes below and are validated at
the API / service layer.
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from . import Base


# --------------------------------------------------------------------------------------
# Allowed values (validated in schemas / services; stored as plain strings in the DB)
# --------------------------------------------------------------------------------------
class MarketingOptOutSource(str, enum.Enum):
    MASS_NOTICE_LINK = "mass_notice_link"   # tapped the unsubscribe link in the consent notice
    APP_SETTINGS = "app_settings"           # toggled it off in the in-app settings screen
    SIGNUP_CHECKBOX = "signup_checkbox"     # ticked "do not send" during registration
    ADMIN = "admin"                         # changed by staff on the patient's behalf


class NotificationCampaignType(str, enum.Enum):
    CONSENT_NOTICE = "consent_notice"   # the one-time "you can opt out" notice -> goes to everyone
    MARKETING = "marketing"             # promotional / health-info blast -> opted-in users only
    SYSTEM = "system"                   # operational broadcast -> goes to everyone


class NotificationCampaignStatus(str, enum.Enum):
    DRAFT = "draft"           # created, audience not built yet
    BUILDING = "building"     # audience materialization in progress
    QUEUED = "queued"         # audience built, ready to send
    SENDING = "sending"       # scheduler is draining the outbox
    PAUSED = "paused"         # manually held
    COMPLETED = "completed"   # every recipient processed
    FAILED = "failed"         # aborted


class CampaignRecipientStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"                # retries exhausted
    SKIPPED = "skipped"             # opted out between materialization and send
    INVALID_TOKEN = "invalid_token"  # Expo reported DeviceNotRegistered


# --------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------
class PatientNotificationPreference(Base):
    __tablename__ = "patient_notification_preferences"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient_accounts.id"), primary_key=True
    )
    # Existing users default to opted-in; they receive the consent notice and can opt out.
    marketing_opt_in: Mapped[bool] = mapped_column(server_default="true")

    # When the one-time consent notice was delivered to this patient (audit / compliance).
    consent_notice_sent_at: Mapped[Optional[datetime]]
    # When and how the patient opted out (null while opted in).
    opted_out_at: Mapped[Optional[datetime]]
    opt_out_source: Mapped[Optional[str]]  # one of MarketingOptOutSource

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class NotificationCampaign(Base):
    __tablename__ = "backend_notification_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str]  # one of NotificationCampaignType
    title: Mapped[str]
    body: Mapped[str]
    # Deep-link payload handed to the app on notification tap, e.g.
    # {"pathname": "/profile/notification-settings"}
    data: Mapped[Optional[dict[str, Any]]]
    status: Mapped[str] = mapped_column(server_default="draft")  # NotificationCampaignStatus

    total_recipients: Mapped[int] = mapped_column(server_default="0")
    sent_count: Mapped[int] = mapped_column(server_default="0")
    failed_count: Mapped[int] = mapped_column(server_default="0")
    skipped_count: Mapped[int] = mapped_column(server_default="0")

    created_by: Mapped[Optional[str]]  # admin identifier
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[Optional[datetime]]
    completed_at: Mapped[Optional[datetime]]


class NotificationCampaignRecipient(Base):
    __tablename__ = "backend_notification_campaign_recipients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("backend_notification_campaigns.id"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient_accounts.id"), index=True
    )
    push_token: Mapped[str]  # snapshot taken when the audience was materialized
    status: Mapped[str] = mapped_column(server_default="pending")  # CampaignRecipientStatus
    attempts: Mapped[int] = mapped_column(server_default="0")
    last_error: Mapped[Optional[str]]
    sent_at: Mapped[Optional[datetime]]

    __table_args__ = (
        # Hot path for the sender worker: "next N pending rows for this campaign".
        Index("ix_campaign_recipient_campaign_status", "campaign_id", "status"),
    )
