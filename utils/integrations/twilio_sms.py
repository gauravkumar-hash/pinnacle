"""
Twilio SMS integration.

Docs: https://www.twilio.com/docs/sms/send-messages
"""

import logging
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_FROM

logger = logging.getLogger(__name__)


class TwilioSMSException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise TwilioSMSException("Twilio credentials (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) are not configured")
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _client


def send_sms(phone: str, text: str) -> str:
    """
    Send an SMS via Twilio. `phone` must be in E.164 format, e.g. +6581611147
    Returns the Twilio message SID on success.
    """
    if not TWILIO_SMS_FROM:
        raise TwilioSMSException("Twilio SMS is not configured (missing TWILIO_SMS_FROM)")

    masked_phone = phone[-4:]

    try:
        client = _get_client()
        message = client.messages.create(from_=TWILIO_SMS_FROM, to=phone, body=text)
    except TwilioRestException as e:
        logger.error(f"[TwilioSMS] Failed to send SMS to phone ending {masked_phone}: [{e.code}] {e.msg}")
        raise TwilioSMSException(f"Failed to send SMS: {e.msg}") from e
    except Exception as e:
        logger.error(f"[TwilioSMS] Unexpected error sending SMS to phone ending {masked_phone}: {e}")
        raise TwilioSMSException(f"Failed to send SMS: {e}") from e

    if message.status in ("failed", "undelivered"):
        logger.error(f"[TwilioSMS] Message {message.sid} to phone ending {masked_phone} reported status={message.status} error={message.error_message}")
        raise TwilioSMSException(f"Twilio reported message status: {message.status}")

    logger.info(f"[TwilioSMS] Message {message.sid} accepted for phone ending {masked_phone}, status={message.status}")
    return message.sid


if __name__ == "__main__":
    send_sms("+6581611234", "This is a test message.")
