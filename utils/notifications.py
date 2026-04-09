import logging
from typing import Literal
import requests
from .integrations import smsdome
from config import APNS_AUTH_KEY, APNS_KEY_ID, APNS_TEAM_ID, APNS_TOPIC, APNS_USE_SANDBOX, MOCK_SMS, EXPO_PATIENT_TOKEN, EXPO_DOCTOR_TOKEN
from models.patient import Account
# https://github.com/expo/expo-server-sdk-python
from exponent_server_sdk import DeviceNotRegisteredError, PushClient, PushMessage
from models.pinnacle import PinnacleAccount
from tenacity import retry, stop_after_attempt, wait_random
from models import SessionLocal
from models.backend import NotificationLog
from firebase_admin import messaging
from models.teleconsult import Teleconsult
import asyncio
from uuid import uuid4
from aioapns import APNs, NotificationRequest, PushType

def send_sms(phone: str, text: str):
    if MOCK_SMS:
        print(f'MOCK SMS: {phone}, {text}')
        return True

    if phone.startswith('+658999'):
        print(f'MOCK SMS: {phone}, {text}')
        return True

    return smsdome.send_sms(phone, text)

async def send_ios_voip_notification(apn_token: str):
    # Generate a random UUID for the notification as using the same UUID will cause the notification to end up in weird states like ringing and call already stated as connected
    uuid = str(object=uuid4())
    # As the key is mocked, we need to set the key manually using environment variables
    apns_key_client = APNs(
        key='/dev/null', # Pass as /dev/null
        key_id=APNS_KEY_ID,
        team_id=APNS_TEAM_ID,
        topic=APNS_TOPIC,
        use_sandbox=APNS_USE_SANDBOX,
    )
    apns_key_client.pool.key = APNS_AUTH_KEY # type: ignore

    request = NotificationRequest(
        device_token=apn_token,
        message = {
            "callerName": "Your session has started",
            "aps": {
                "content-available": 1,
            },
            "handle": "PinnacleSG+ Teleconsultation",
            "type": "CALL_INITIATED",
            "uuid": uuid
        },
        notification_id=uuid,
        time_to_live=60, # 1 minute
        push_type=PushType.VOIP,
    )
    await apns_key_client.send_notification(request)

def send_voip_notification(user: Account, teleconsult: Teleconsult):
    auths = user.firebase_auths
    for auth in auths:
        if auth.fcm_token:
            messaging.send(messaging.Message(
                data={ "voip_id": str(teleconsult.id) },
                android=messaging.AndroidConfig(priority='high'),
                token=auth.fcm_token
            ))

            with SessionLocal() as db:
                record = NotificationLog(account_id=user.id, title="VoIP Notification (Android)", message=f"Teleconsult {teleconsult.id}")
                db.add(record)
                db.commit()

        elif auth.apn_token:
            asyncio.run(send_ios_voip_notification(auth.apn_token))
        
            with SessionLocal() as db:
                record = NotificationLog(account_id=user.id, title="VoIP Notification (iOS)", message=f"Teleconsult {teleconsult.id}")
                db.add(record)
                db.commit()

def send_patient_notification(user: Account, title: str, message: str, extra: dict | None = None, priority: Literal['high'] | None = 'high', critical: bool | None = None):
    '''
    Send a push notification to the user.
    '''
    auths = user.firebase_auths
    for auth in auths:
        if auth.push_token:
            try:
                _send_push_message(EXPO_PATIENT_TOKEN, auth.push_token, title, message, extra, priority, critical)
                with SessionLocal() as db:
                    record = NotificationLog(account_id=user.id, title=title, message=message)
                    db.add(record)
                    db.commit()
            except Exception as err:
                logging.error(f"Push Notifications (Patient): {err}", exc_info=True)

def send_doctor_notification(user: PinnacleAccount, title: str, message: str, extra=None):
    if not user.enable_notifications:
        logging.warning(f"User {user.id} has disabled notifications but send_doctor_notification() method was called")
        return

    for token in user.push_token:
        try:
            _send_push_message(EXPO_DOCTOR_TOKEN, token, title, message, extra)
        except Exception as err:
            logging.error(f"Push Notifications: {err}", exc_info=True)

@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
def _send_push_message(expo_token, user_token: str, title: str, message: str, extra=None, priority=None, critical=None):
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {expo_token}",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",
            "content-type": "application/json",
        }
    )

    try:
        msg = PushMessage(
            to=user_token,
            title=title,
            body=message,
            data=extra,
            priority=priority,
            sound='default' if not critical else { 'critical': True },
            # Prevent Error Message
            ttl=None,
            expiration=None,
            badge=None,
            category=None, 
            display_in_foreground=None,
            channel_id=None,
            subtitle=None,
            mutable_content=None
        )
        response = PushClient(session=session, timeout=5).publish(msg)
        response.validate_response()
    except DeviceNotRegisteredError:
        # Remove the push token if token is inactive
        logging.error(f"Push Notification: Inactive Token {user_token}")
        # handle_delete_token(token=token, user_id=user_id, db=db)

# @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
def send_notification_messages(user_tokens: list[str], title: str, message: str, extra=None, priority='high', critical=None):
    msges = [
        PushMessage(
            to=user_token,
            title=title,
            body=message,
            data=extra,
            priority=priority,
            sound='default' if not critical else { 'critical': True },
            # Prevent Error Message
            ttl=None,
            expiration=None,
            badge=None,
            category=None, 
            display_in_foreground=None,
            channel_id=None,
            subtitle=None,
            mutable_content=None
        )
        for user_token in user_tokens
    ]

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {EXPO_PATIENT_TOKEN}",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",
            "content-type": "application/json",
        }
    )

    responses = PushClient(session=session, timeout=10).publish_multiple(msges)
    for i, response in enumerate(responses):
        try:
            if response.status != 'ok':
                print(f"{i} {response.status}: {response.push_message.to}")
            response.validate_response()
        except DeviceNotRegisteredError:
            # Remove the push token if token is inactive
            logging.error(f"Push Notification: Inactive Token {response}")
            # handle_delete_token(token=token, user_id=user_id, db=db)