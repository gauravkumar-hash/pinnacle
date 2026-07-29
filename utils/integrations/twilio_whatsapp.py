"""
Twilio WhatsApp OTP integration.

Sends OTP codes via WhatsApp using a pre-approved Twilio Content Template
(Content SID starting with "HX"). Docs: https://www.twilio.com/docs/verify/api/whatsapp-otp
"""

import json
import logging
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_OTP_TEMPLATE_SID,
    TWILIO_WHATSAPP_FROM,
)

logger = logging.getLogger(__name__)


class TwilioWhatsAppException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise TwilioWhatsAppException("Twilio credentials (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) are not configured")
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _client


def send_whatsapp_otp(phone: str, otp_code: str) -> str:
    """
    Send an OTP code via Twilio WhatsApp using the approved OTP content template.
    `phone` must be in E.164 format, e.g. +6581611147
    Returns the Twilio message SID on success.
    """
    if not TWILIO_WHATSAPP_FROM or not TWILIO_OTP_TEMPLATE_SID:
        raise TwilioWhatsAppException("Twilio WhatsApp OTP is not configured (missing TWILIO_WHATSAPP_FROM or TWILIO_OTP_TEMPLATE_SID)")

    to_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
    masked_phone = phone[-4:]

    logger.info(f"[TwilioWhatsApp] Sending OTP to phone ending {masked_phone} via template {TWILIO_OTP_TEMPLATE_SID}")

    try:
        client = _get_client()
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number,
            content_sid=TWILIO_OTP_TEMPLATE_SID,
            content_variables=json.dumps({"1": otp_code}),
        )
    except TwilioRestException as e:
        logger.error(f"[TwilioWhatsApp] Failed to send OTP to phone ending {masked_phone}: [{e.code}] {e.msg}")
        raise TwilioWhatsAppException(f"Failed to send WhatsApp OTP: {e.msg}") from e
    except Exception as e:
        logger.error(f"[TwilioWhatsApp] Unexpected error sending OTP to phone ending {masked_phone}: {e}")
        raise TwilioWhatsAppException(f"Failed to send WhatsApp OTP: {e}") from e

    if message.status in ("failed", "undelivered"):
        logger.error(f"[TwilioWhatsApp] Message {message.sid} to phone ending {masked_phone} reported status={message.status} error={message.error_message}")
        raise TwilioWhatsAppException(f"Twilio reported message status: {message.status}")

    logger.info(f"[TwilioWhatsApp] OTP message {message.sid} accepted for phone ending {masked_phone}, status={message.status}")
    return message.sid


if __name__ == "__main__":
    send_whatsapp_otp("+6581611234", "123456")
