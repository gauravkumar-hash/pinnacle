"""
Notification-campaign background work.

Two operations:

1. materialize_campaign_audience(campaign_id)
   Fills backend_notification_campaign_recipients with one row per targeted device, using a
   single set-based ``INSERT ... SELECT`` so it is one cheap statement regardless of user count.
   For MARKETING campaigns the select excludes opted-out patients.

2. process_sending_campaigns(db)
   Called on a short interval by the APScheduler process. For every campaign in state
   ``sending`` it drains a small, bounded batch of the outbox: locks up to BATCH_SIZE pending
   rows with ``FOR UPDATE SKIP LOCKED``, pushes them to Expo in sub-chunks of EXPO_CHUNK_SIZE,
   records per-row results, updates the campaign counters, and sleeps between sub-chunks. When
   no pending rows remain the campaign is marked ``completed``.

   Throughput is BATCH_SIZE per scheduler tick. With the defaults below and a 60s interval that
   is ~30k notifications/hour, i.e. a 200k-user blast finishes in ~7h without ever holding more
   than EXPO_CHUNK_SIZE rows in a transaction. Tune BATCH_SIZE / the interval to go faster.
"""

import logging
import time
from datetime import datetime

import requests
from exponent_server_sdk import DeviceNotRegisteredError, PushClient, PushMessage
from sqlalchemy import text

from config import EXPO_PATIENT_TOKEN
from models import SessionLocal
from models.backend import NotificationLog
from models.marketing_notifications import (
    CampaignRecipientStatus,
    NotificationCampaign,
    NotificationCampaignRecipient,
    NotificationCampaignStatus,
    NotificationCampaignType,
    PatientNotificationPreference,
)

# --- tuning knobs -------------------------------------------------------------------
BATCH_SIZE = 500          # rows pulled from the outbox per scheduler tick
EXPO_CHUNK_SIZE = 100     # Expo accepts up to 100 messages per push request
CHUNK_DELAY_SECONDS = 2   # pause between Expo sub-chunks (throttles Expo + DB)
MAX_ATTEMPTS = 3          # transient-failure retries before a row is marked failed
# ----------------------------------------------------------------------------------


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


# ==================================================================================
# 1. Audience materialization
# ==================================================================================
def materialize_campaign_audience(campaign_id: str) -> None:
    """Populate the outbox for ``campaign_id`` then move it DRAFT/BUILDING -> QUEUED.

    Safe to call from a FastAPI BackgroundTask - it opens its own session.
    """
    with SessionLocal() as db:
        campaign = db.get(NotificationCampaign, campaign_id)
        if campaign is None:
            logging.error(f"materialize_campaign_audience: campaign {campaign_id} not found")
            return

        campaign.status = NotificationCampaignStatus.BUILDING.value
        db.commit()

        # One device row per patient that has a push token. For marketing blasts, drop anyone
        # whose preference row explicitly says opted-out (a missing row counts as opted-in).
        opt_out_clause = ""
        if campaign.type == NotificationCampaignType.MARKETING.value:
            opt_out_clause = """
                AND NOT EXISTS (
                    SELECT 1 FROM patient_notification_preferences p
                    WHERE p.account_id = fb.account_id
                      AND p.marketing_opt_in = false
                )
            """

        insert_sql = text(
            f"""
            INSERT INTO backend_notification_campaign_recipients
                (campaign_id, account_id, push_token, status, attempts)
            SELECT :campaign_id, fb.account_id, fb.push_token, 'pending', 0
            FROM patient_firebase_auths fb
            WHERE fb.push_token IS NOT NULL
            {opt_out_clause}
            """
        )
        result = db.execute(insert_sql, {"campaign_id": str(campaign.id)})

        campaign.total_recipients = result.rowcount or 0
        campaign.status = NotificationCampaignStatus.QUEUED.value
        db.commit()
        logging.info(
            f"Campaign {campaign.id}: materialized {campaign.total_recipients} recipients"
        )


# ==================================================================================
# 2. Sending worker (called every tick by scheduler.py)
# ==================================================================================
def process_sending_campaigns(db) -> None:
    campaigns = (
        db.query(NotificationCampaign)
        .filter(NotificationCampaign.status == NotificationCampaignStatus.SENDING.value)
        .all()
    )
    for campaign in campaigns:
        try:
            _process_campaign_batch(db, campaign)
        except Exception as err:  # never let one campaign kill the tick
            db.rollback()
            logging.error(f"Campaign {campaign.id}: batch failed: {err}", exc_info=True)


def _process_campaign_batch(db, campaign: NotificationCampaign) -> None:
    rows = (
        db.query(NotificationCampaignRecipient)
        .filter(
            NotificationCampaignRecipient.campaign_id == campaign.id,
            NotificationCampaignRecipient.status == CampaignRecipientStatus.PENDING.value,
        )
        .order_by(NotificationCampaignRecipient.id)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
        .all()
    )

    if not rows:
        campaign.status = NotificationCampaignStatus.COMPLETED.value
        campaign.completed_at = datetime.now()
        db.commit()
        logging.info(f"Campaign {campaign.id}: completed")
        return

    # Late opt-out check for marketing blasts: honour anyone who opted out after materialization.
    opted_out_ids: set = set()
    if campaign.type == NotificationCampaignType.MARKETING.value:
        account_ids = [r.account_id for r in rows]
        opted_out_ids = {
            aid
            for (aid,) in db.query(PatientNotificationPreference.account_id)
            .filter(
                PatientNotificationPreference.account_id.in_(account_ids),
                PatientNotificationPreference.marketing_opt_in.is_(False),
            )
            .all()
        }

    push_client = _build_push_client()

    for chunk in _chunks(rows, EXPO_CHUNK_SIZE):
        to_send = []
        for r in chunk:
            if r.account_id in opted_out_ids:
                r.status = CampaignRecipientStatus.SKIPPED.value
                campaign.skipped_count += 1
            else:
                to_send.append(r)

        if to_send:
            _send_chunk(db, campaign, push_client, to_send)

        db.commit()
        time.sleep(CHUNK_DELAY_SECONDS)


def _send_chunk(db, campaign, push_client, recipients) -> None:
    messages = [
        PushMessage(
            to=r.push_token,
            title=campaign.title,
            body=campaign.body,
            data=campaign.data or None,
            priority="high",
            sound="default",
            ttl=None,
            expiration=None,
            badge=None,
            category=None,
            display_in_foreground=None,
            channel_id=None,
            subtitle=None,
            mutable_content=None,
        )
        for r in recipients
    ]

    try:
        responses = push_client.publish_multiple(messages)
    except Exception as err:
        # Whole request failed (network / Expo down): bump attempts, leave retryable.
        logging.error(f"Campaign {campaign.id}: Expo request failed: {err}")
        for r in recipients:
            _mark_transient_failure(campaign, r, str(err))
        return

    logs = []
    for r, response in zip(recipients, responses):
        try:
            response.validate_response()
            r.status = CampaignRecipientStatus.SENT.value
            r.sent_at = datetime.now()
            campaign.sent_count += 1
            logs.append(
                NotificationLog(
                    account_id=r.account_id, title=campaign.title, message=campaign.body
                )
            )
        except DeviceNotRegisteredError:
            r.status = CampaignRecipientStatus.INVALID_TOKEN.value
            r.last_error = "DeviceNotRegistered"
            campaign.failed_count += 1
        except Exception as err:
            _mark_transient_failure(campaign, r, str(err))

    if logs:
        db.add_all(logs)


def _mark_transient_failure(campaign, recipient, error: str) -> None:
    recipient.attempts += 1
    recipient.last_error = error[:500]
    if recipient.attempts >= MAX_ATTEMPTS:
        recipient.status = CampaignRecipientStatus.FAILED.value
        campaign.failed_count += 1
    else:
        recipient.status = CampaignRecipientStatus.PENDING.value  # retried next tick


def _build_push_client() -> PushClient:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {EXPO_PATIENT_TOKEN}",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",
            "content-type": "application/json",
        }
    )
    return PushClient(session=session, timeout=10)
