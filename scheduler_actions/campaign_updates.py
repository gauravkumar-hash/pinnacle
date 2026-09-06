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
    CampaignReceiptStatus,
    CampaignRecipientStatus,
    NotificationCampaign,
    NotificationCampaignRecipient,
    NotificationCampaignStatus,
    NotificationCampaignType,
    PatientNotificationPreference,
)

logger = logging.getLogger("campaign_updates")

EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
RECEIPT_POLL_BATCH = 1000  # ticket ids sent to Expo's getReceipts per request (Expo cap)

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
        logger.info(
            "Campaign %s (%s): materialized %s recipients -> QUEUED",
            campaign.id, campaign.type, campaign.total_recipients,
        )
        if campaign.total_recipients == 0:
            logger.warning(
                "Campaign %s: audience is EMPTY. Nothing will send. Likely no rows in "
                "patient_firebase_auths with a non-null push_token (no app build has "
                "registered a push token), or everyone is opted out.",
                campaign.id,
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
    if campaigns:
        logger.info("Draining %s campaign(s) in 'sending' state", len(campaigns))
    for campaign in campaigns:
        try:
            _process_campaign_batch(db, campaign)
        except Exception as err:  # never let one campaign kill the tick
            db.rollback()
            logger.error("Campaign %s: batch failed: %s", campaign.id, err, exc_info=True)


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
        logger.info(
            "Campaign %s: COMPLETED - sent=%s failed=%s skipped=%s of total=%s",
            campaign.id, campaign.sent_count, campaign.failed_count,
            campaign.skipped_count, campaign.total_recipients,
        )
        return

    logger.info(
        "Campaign %s: processing batch of %s pending row(s) "
        "(so far sent=%s failed=%s skipped=%s / total=%s)",
        campaign.id, len(rows), campaign.sent_count, campaign.failed_count,
        campaign.skipped_count, campaign.total_recipients,
    )

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


def _extract_expo_errors(err) -> list:
    data = getattr(err, "errors", None) or getattr(err, "response_data", None) or {}
    if isinstance(data, dict):
        return data.get("errors", []) or []
    if isinstance(data, list):
        return data
    return []


def _publish(push_client, messages: list):
    """push_client.publish_multiple, but tolerant of tokens from multiple Expo projects.

    Expo rejects a request whose messages span more than one project
    (PUSH_TOO_MANY_EXPERIENCE_IDS). When that happens we read the project -> [tokens]
    map back out of the error and re-send one request per project, then stitch the
    responses back into the original order so the caller can zip() them to recipients.
    """
    try:
        return push_client.publish_multiple(messages)
    except Exception as err:
        groups: dict = {}
        for e in _extract_expo_errors(err):
            if e.get("code") == "PUSH_TOO_MANY_EXPERIENCE_IDS":
                groups = e.get("details", {}) or {}
                break
        if not groups:
            raise  # some other failure - let the caller handle/log it

        token_to_project = {
            tok: project for project, toks in groups.items() for tok in toks
        }
        logger.warning(
            "Expo: %s message(s) span %s projects %s - splitting into per-project requests",
            len(messages), len(groups), list(groups.keys()),
        )

        by_project: dict = {}
        for idx, msg in enumerate(messages):
            proj = token_to_project.get(msg.to, "__unknown__")
            by_project.setdefault(proj, []).append(idx)

        responses: list = [None] * len(messages)
        for proj, idxs in by_project.items():
            subset = [messages[i] for i in idxs]
            try:
                sub_responses = push_client.publish_multiple(subset)
            except Exception as sub_err:
                logger.error(
                    "Expo: per-project request for %s (%s msg) failed: %s",
                    proj, len(subset), sub_err,
                )
                continue  # leave those responses as None -> caller retries them
            for i, resp in zip(idxs, sub_responses):
                responses[i] = resp
            time.sleep(1)
        return responses


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
        responses = _publish(push_client, messages)
    except Exception as err:
        # Whole request failed (network / Expo down / auth / bad payload).
        detail = f"{type(err).__name__}: {err}"
        resp = getattr(err, "response", None)
        if resp is not None:
            body = getattr(resp, "text", "")
            detail += f" | HTTP {getattr(resp, 'status_code', '?')}: {body[:800]}"
        for attr in ("errors", "response_data"):
            val = getattr(err, attr, None)
            if val:
                detail += f" | {attr}={val}"
        logger.error(
            "Campaign %s: Expo publish request failed for %s message(s): %s",
            campaign.id, len(messages), detail,
        )
        for r in recipients:
            _mark_transient_failure(campaign, r, detail)
        return

    logs = []
    ok = bad_token = transient = 0
    for r, response in zip(recipients, responses):
        if response is None:
            # per-project sub-request failed in _publish(); retry this row next tick
            _mark_transient_failure(campaign, r, "Expo per-project request failed")
            transient += 1
            continue
        try:
            response.validate_response()
            r.status = CampaignRecipientStatus.SENT.value
            r.sent_at = datetime.now()
            # Keep the Expo ticket id so the receipt-poller can confirm delivery later.
            r.expo_ticket_id = getattr(response, "id", None)
            campaign.sent_count += 1
            ok += 1
            logs.append(
                NotificationLog(
                    account_id=r.account_id, title=campaign.title, message=campaign.body
                )
            )
        except DeviceNotRegisteredError:
            r.status = CampaignRecipientStatus.INVALID_TOKEN.value
            r.last_error = "DeviceNotRegistered"
            campaign.failed_count += 1
            bad_token += 1
        except Exception as err:
            _mark_transient_failure(campaign, r, str(err))
            transient += 1

    logger.info(
        "Campaign %s: pushed chunk of %s -> accepted=%s invalid_token=%s transient_fail=%s",
        campaign.id, len(recipients), ok, bad_token, transient,
    )

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


# ==================================================================================
# 3. Delivery-receipt poller (called every few minutes by scheduler.py)
# ==================================================================================
def check_campaign_receipts(db) -> None:
    """Confirm actual delivery for rows we already pushed to Expo.

    ``sent`` only means Expo *accepted* the push. Expo then hands it to FCM / APNs and
    records the outcome in a *receipt*, retrievable for ~24h via getReceipts. This job
    polls those receipts and writes the result onto each recipient row:

      receipt_status = 'ok'    -> delivered to FCM / APNs   (campaign.delivered_count++)
      receipt_status = 'error' -> Expo could not deliver it  (campaign.undelivered_count++)

    A DeviceNotRegistered error here also flips the row to ``invalid_token`` so the stale
    push token is visible in the admin drill-down.
    """
    rows = (
        db.query(NotificationCampaignRecipient)
        .filter(
            NotificationCampaignRecipient.status == CampaignRecipientStatus.SENT.value,
            NotificationCampaignRecipient.receipt_status.is_(None),
            NotificationCampaignRecipient.expo_ticket_id.isnot(None),
        )
        .order_by(NotificationCampaignRecipient.id)
        .limit(RECEIPT_POLL_BATCH)
        .all()
    )
    if not rows:
        return

    logger.info("Receipt poller: checking %s Expo receipt(s)", len(rows))
    by_ticket = {r.expo_ticket_id: r for r in rows}

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {EXPO_PATIENT_TOKEN}",
            "accept": "application/json",
            "content-type": "application/json",
        }
    )
    try:
        resp = session.post(
            EXPO_RECEIPTS_URL, json={"ids": list(by_ticket.keys())}, timeout=15
        )
        resp.raise_for_status()
        receipts = resp.json().get("data", {}) or {}
    except Exception as err:
        logger.error("Receipt poller: Expo getReceipts request failed: %s", err)
        return

    now = datetime.now()
    delivered = undelivered = still_pending = 0
    touched_campaigns: dict = {}

    for ticket_id, receipt in receipts.items():
        r = by_ticket.get(ticket_id)
        if r is None:
            continue
        campaign = touched_campaigns.get(r.campaign_id)
        if campaign is None:
            campaign = db.get(NotificationCampaign, r.campaign_id)
            touched_campaigns[r.campaign_id] = campaign

        status = (receipt or {}).get("status")
        r.receipt_checked_at = now

        if status == "ok":
            r.receipt_status = CampaignReceiptStatus.OK.value
            if campaign:
                campaign.delivered_count += 1
            delivered += 1
        elif status == "error":
            details = (receipt or {}).get("details") or {}
            err_code = details.get("error") or "unknown"
            r.receipt_status = CampaignReceiptStatus.ERROR.value
            r.receipt_error = (receipt.get("message") or err_code)[:500]
            if err_code == "DeviceNotRegistered":
                r.status = CampaignRecipientStatus.INVALID_TOKEN.value
                r.last_error = "DeviceNotRegistered (from receipt)"
            if campaign:
                campaign.undelivered_count += 1
            undelivered += 1
        else:
            # Expo not ready yet - leave receipt_status NULL so we retry next tick.
            r.receipt_checked_at = None
            still_pending += 1

    db.commit()
    logger.info(
        "Receipt poller: delivered=%s undelivered=%s not-ready=%s",
        delivered, undelivered, still_pending,
    )
