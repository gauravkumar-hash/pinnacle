# TODO: To be replaced in .env
from models.patient import Account
from models.payments import Payment
from config import (
    PAYMENT_2C2P_CURRENCY_CODE, 
    PAYMENT_2C2P_MERCHANT_ID,
    ENABLE_PAYMENT_AUTHORIZATION,
    AUTHORIZATION_ROLLOUT_PERCENTAGE,
    AUTHORIZATION_TEST_USER_IDS,
    AUTHORIZATION_ENABLED_PATIENT_TYPES,
    AUTHORIZATION_EXPIRY_MINUTES,
    FALLBACK_TO_IMMEDIATE_CHARGE_ON_AUTH_FAILURE
)

import logging
import uuid
from typing import Optional
from datetime import timedelta
from models.payments import PaymentMethod, PaymentProvider, PaymentStatus, PaymentToken, PaymentTransaction, PaymentType
from utils import sg_datetime
from .helpers import call_2c2p_api, jwt_decode_payload
from .pgw_models import PGWPaymentTokenResponse, PGWWebhookResp
from sqlalchemy.orm import Session

def get_teleconsult_payment_token(db: Session, user: Account, amount: float, payment_card: PaymentToken, type: PaymentType):
    # For Payment
    payload: dict = {
        "description": f"Teleconsultation {type.value.title()}",
        "amount": round(amount, 2),
        "customerToken": [payment_card.token],
        # Fixed    
        "merchantID":PAYMENT_2C2P_MERCHANT_ID,
        "nonceStr": str(uuid.uuid4()),
        "paymentChannel": ["GCARD"],
        "request3DS" : "Y",
        "currencyCode":PAYMENT_2C2P_CURRENCY_CODE,
    }
        
    return get_payment_token(db, user, payload, type)

def get_payment_token(db: Session, user: Account, payload: dict, type: PaymentType):
    '''
    Generates invoice number, transaction log and return PGWPaymentTokenResponse that contains the payment token
    '''
    # Add a payment transaction to the database
    transaction = PaymentTransaction(
        account_id=user.id,
        provider=PaymentProvider.APP_2C2P,
        type=type,
        endpoint='/payment/4.3/paymentToken',
        request={},
        response={},
        webhook={}
    )
    db.add(transaction)
    db.commit()
    
    # Generate invoice number based on date and incrementing the number
    
    # Convert datetime to just start hour
    start_date = sg_datetime.now().replace(second=0, microsecond=0)
    # start_date = sg_datetime.midnight()
    min_count = db.query(PaymentTransaction.id).filter(
        PaymentTransaction.created_at >= start_date,
        PaymentTransaction.provider == PaymentProvider.APP_2C2P,
        PaymentTransaction.id <= transaction.id,
    ).count()
    invoice_num = f'{sg_datetime.now().strftime("%y%m%d%H%M")}_{min_count:03d}'
    payload["invoiceNo"] = invoice_num

    # Store the request payload to the database
    transaction.invoice_num = invoice_num
    transaction.request = payload
    db.commit()
    
    # 2C2P encrypted payload
    data = call_2c2p_api('/payment/4.3/paymentToken', payload)
    transaction.response = {"data": data}
    if 'payload' not in data:
        db.commit()
        logging.error(f"2C2P {transaction.id}: No payload in payment token response")
        raise Exception("Failed to initialise payment method")

    # 2C2P decrypted payload
    decoded_payload =  jwt_decode_payload(data['payload'])
    transaction.response = decoded_payload
    db.commit()
    
    payment_token = PGWPaymentTokenResponse(**decoded_payload)
    if payment_token.respCode != '0000':
        logging.error(f"2C2P {transaction.id}: Response code is not 0000. Received {payment_token.respCode}")
        raise Exception("Failed to initialise payment method")
    
    transaction.status = PaymentStatus.PAYMENT_CREATED
    db.commit()
    return payment_token, invoice_num

def save_payment_token_to_db(db: Session, account_id: str, payload: PGWWebhookResp):
    record = db.query(PaymentToken.id).filter(
            PaymentToken.account_id == account_id,
            PaymentToken.provider == PaymentProvider.APP_2C2P,
            PaymentToken.token == payload.customerToken,
            PaymentToken.deleted == False
        ).first()
    if record:
        logging.error(f"2C2P: Payment token already exists in db: {payload.customerToken}")
        return
    
    def get_card_brand(card_first_digit: str) -> str:
        card_brands = {
            '4': 'visa',
            '5': 'mastercard',
        }
        return card_brands.get(card_first_digit, "unknown")

    # Save token to database
    db.add(PaymentToken(
        account_id=account_id,
        provider=PaymentProvider.APP_2C2P,
        method=PaymentMethod.CARD_2C2P,
        token=payload.customerToken,
        # Format followed from Stripe
        details={
            "brand": get_card_brand(payload.accountNo[0]),
            "first1": payload.accountNo[0],
            "last4": payload.accountNo[-4:],
            "type": payload.cardType,
            "invoice_no": payload.invoiceNo,
        }
    ))
    db.commit()


# ============================================================================
# PAYMENT AUTHORIZATION FUNCTIONS (Hold & Charge Flow)
# ============================================================================
# CRITICAL: These functions implement the authorization/capture flow
# See documentation/telemed_onhold_payment_plan.md for full specification
# See documentation/CRITICAL_PRODUCTION_WARNING.md for deployment safety


def should_use_authorization_flow(user: Account, patient_type: str) -> bool:
    """
    Determine if this user should get authorization/capture flow or immediate charge.
    
    Uses feature flags to control rollout:
    - ENABLE_PAYMENT_AUTHORIZATION: Master switch
    - AUTHORIZATION_TEST_USER_IDS: Always enable for these users
    - AUTHORIZATION_ENABLED_PATIENT_TYPES: Which patient types are eligible
    - AUTHORIZATION_ROLLOUT_PERCENTAGE: Gradual rollout percentage
    
    Args:
        user: Account object for the patient
        patient_type: Patient type (e.g., 'private_patient', 'migrant_worker')
        
    Returns:
        True if should use authorization/capture, False if should use immediate charge
    """
    # Feature disabled globally
    if not ENABLE_PAYMENT_AUTHORIZATION:
        logging.info(f"Payment auth disabled globally for user {user.id}")
        return False
    
    # Test user bypass (always enable for testing)
    if user.id in AUTHORIZATION_TEST_USER_IDS:
        logging.info(f"Payment auth enabled for test user {user.id}")
        return True
    
    # Check if patient type is eligible
    if patient_type not in AUTHORIZATION_ENABLED_PATIENT_TYPES:
        logging.info(f"Payment auth not enabled for patient type {patient_type} (user {user.id})")
        return False
    
    # Rollout percentage check (deterministic based on user ID for consistency)
    if AUTHORIZATION_ROLLOUT_PERCENTAGE == 0:
        return False
    elif AUTHORIZATION_ROLLOUT_PERCENTAGE >= 100:
        return True
    else:
        # Use hash of user ID to deterministically assign to rollout group
        # This ensures same user always gets same experience
        user_hash = hash(user.id)
        user_bucket = abs(user_hash) % 100
        enabled = user_bucket < AUTHORIZATION_ROLLOUT_PERCENTAGE
        
        if enabled:
            logging.info(f"User {user.id} in rollout bucket (rollout={AUTHORIZATION_ROLLOUT_PERCENTAGE}%)")
        else:
            logging.debug(f"User {user.id} not in rollout bucket (rollout={AUTHORIZATION_ROLLOUT_PERCENTAGE}%)")
        
        return enabled


def authorize_payment_2c2p(
    db: Session,
    user: Account,
    amount: float,
    payment_card: PaymentToken,
    type: PaymentType,
    description: str = "Teleconsultation Payment"
) -> tuple[PGWPaymentTokenResponse, str, Payment]:
    """
    Authorize (hold) funds on a credit card without charging.
    
    This creates a payment authorization that holds funds for later capture.
    The authorization will expire after AUTHORIZATION_EXPIRY_MINUTES.
    
    Args:
        db: Database session
        user: Patient account
        amount: Amount to authorize (in SGD)
        payment_card: Saved payment token
        type: Payment type (PREPAYMENT, POSTPAYMENT, etc.)
        description: Payment description for customer
        
    Returns:
        Tuple of (payment_token_response, invoice_number, payment_record)
        
    Raises:
        Exception: If authorization fails (caller should handle fallback)
    """
    try:
        logging.info(f"Starting payment authorization for user {user.id}, amount ${amount:.2f}")
        
        # 2C2P Authorization payload
        # NOTE: 2C2P uses "paymentType": "A" for authorization
        # Standard charge is "paymentType": "N"
        payload: dict = {
            "description": description,
            "amount": round(amount, 2),
            "customerToken": [payment_card.token],
            "paymentType": "A",  # CRITICAL: "A" = Authorization only (hold funds)
            # Fixed fields
            "merchantID": PAYMENT_2C2P_MERCHANT_ID,
            "nonceStr": str(uuid.uuid4()),
            "paymentChannel": ["GCARD"],  # Global credit cards
            "request3DS": "Y",  # Require 3D Secure for security
            "currencyCode": PAYMENT_2C2P_CURRENCY_CODE,
        }
        
        # Get payment token from 2C2P
        payment_token, invoice_num = get_payment_token(db, user, payload, type)
        
        # Create Payment record with authorization details
        authorization_expiry = sg_datetime.now() + timedelta(minutes=AUTHORIZATION_EXPIRY_MINUTES)
        
        payment = Payment(
            payment_id=payment_token.transactionId,
            account_id=user.id,
            payment_breakdown=[],
            payment_type=type,
            payment_method=PaymentMethod.CARD_2C2P,
            payment_amount=amount,
            payment_provider=PaymentProvider.APP_2C2P,
            status=PaymentStatus.PAYMENT_AUTHORIZED,
            remarks={"authorization_mode": True, "invoice_num": invoice_num},
            # Authorization fields
            authorized_amount=amount,
            captured_amount=0.0,
            authorization_id=payment_token.transactionId,
            authorization_expires_at=authorization_expiry,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        logging.info(
            f"Payment authorization successful: "
            f"payment_id={payment.id}, "
            f"auth_id={payment.authorization_id}, "
            f"amount=${amount:.2f}, "
            f"expires_at={authorization_expiry}"
        )
        
        return payment_token, invoice_num, payment
        
    except Exception as e:
        logging.error(
            f"Payment authorization failed for user {user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        
        # If fallback is enabled, re-raise to let caller try immediate charge
        if FALLBACK_TO_IMMEDIATE_CHARGE_ON_AUTH_FAILURE:
            logging.warning(f"Will fallback to immediate charge for user {user.id}")
        
        raise


def capture_payment_2c2p(
    db: Session,
    payment: Payment,
    amount: Optional[float] = None
) -> dict:
    """
    Capture (charge) previously authorized funds.
    
    This completes the payment by actually charging the held funds.
    Can capture partial amount (less than authorized) if needed.
    
    Args:
        db: Database session
        payment: Payment record with authorization
        amount: Amount to capture (defaults to full authorized amount)
        
    Returns:
        2C2P API response dict
        
    Raises:
        ValueError: If payment is not in valid state for capture
        Exception: If capture API call fails
    """
    try:
        # Validation
        if payment.status != PaymentStatus.PAYMENT_AUTHORIZED and payment.status != PaymentStatus.PAYMENT_CAPTURE_PENDING:
            raise ValueError(
                f"Cannot capture payment {payment.id} in status {payment.status}. "
                f"Must be PAYMENT_AUTHORIZED or PAYMENT_CAPTURE_PENDING"
            )
        
        if not payment.authorization_id:
            raise ValueError(f"Payment {payment.id} has no authorization_id")
        
        if payment.authorization_expires_at and sg_datetime.now() > payment.authorization_expires_at:
            raise ValueError(
                f"Payment authorization {payment.id} expired at {payment.authorization_expires_at}"
            )
        
        # Default to capturing full authorized amount
        capture_amount = amount if amount is not None else payment.authorized_amount
        
        if capture_amount > payment.authorized_amount:
            raise ValueError(
                f"Cannot capture ${capture_amount:.2f} - exceeds authorized amount ${payment.authorized_amount:.2f}"
            )
        
        logging.info(
            f"Starting payment capture: "
            f"payment_id={payment.id}, "
            f"auth_id={payment.authorization_id}, "
            f"capture_amount=${capture_amount:.2f}, "
            f"authorized_amount=${payment.authorized_amount:.2f}"
        )
        
        # Update status to capture pending
        payment.status = PaymentStatus.PAYMENT_CAPTURE_PENDING
        payment.capture_attempted_at = sg_datetime.now()
        db.commit()
        
        # 2C2P Capture payload
        # NOTE: Use "paymentType": "C" for capture
        payload = {
            "merchantID": PAYMENT_2C2P_MERCHANT_ID,
            "nonceStr": str(uuid.uuid4()),
            "transactionId": payment.authorization_id,  # Original authorization transaction ID
            "amount": round(capture_amount, 2),
            "paymentType": "C",  # CRITICAL: "C" = Capture authorized funds
            "currencyCode": PAYMENT_2C2P_CURRENCY_CODE,
        }
        
        # Call 2C2P capture API
        # Note: 2C2P might use a different endpoint for capture
        # Adjust endpoint based on 2C2P documentation
        response = call_2c2p_api('/payment/4.3/paymentCapture', payload)
        
        # Decode response
        if 'payload' in response:
            decoded = jwt_decode_payload(response['payload'])
        else:
            decoded = response
        
        # Check capture success
        resp_code = decoded.get('respCode', '')
        if resp_code == '0000':
            # Capture successful
            payment.status = PaymentStatus.PAYMENT_CAPTURED
            payment.captured_amount = capture_amount
            
            # Update remarks
            remarks = payment.remarks or {}
            remarks['capture_response'] = decoded
            remarks['captured_at'] = sg_datetime.now().isoformat()
            payment.remarks = remarks
            
            db.commit()
            
            logging.info(
                f"Payment capture successful: "
                f"payment_id={payment.id}, "
                f"captured_amount=${capture_amount:.2f}, "
                f"transaction_id={decoded.get('transactionId', 'N/A')}"
            )
        else:
            # Capture failed
            payment.status = PaymentStatus.PAYMENT_FAILED
            
            # Update remarks with error
            remarks = payment.remarks or {}
            remarks['capture_error'] = decoded
            payment.remarks = remarks
            
            db.commit()
            
            logging.error(
                f"Payment capture failed: "
                f"payment_id={payment.id}, "
                f"resp_code={resp_code}, "
                f"resp_desc={decoded.get('respDesc', 'N/A')}"
            )
            
            raise Exception(f"Capture failed: {decoded.get('respDesc', 'Unknown error')}")
        
        return decoded
        
    except Exception as e:
        # Log error and re-raise
        logging.error(
            f"Payment capture exception for payment {payment.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        
        # Update payment status to failed if not already
        if payment.status != PaymentStatus.PAYMENT_FAILED:
            payment.status = PaymentStatus.PAYMENT_FAILED
            remarks = payment.remarks or {}
            remarks['capture_exception'] = str(e)
            payment.remarks = remarks
            db.commit()
        
        raise


def void_payment_2c2p(
    db: Session,
    payment: Payment,
    reason: str = "Appointment cancelled"
) -> dict:
    """
    Void (release) an authorized payment without capturing.
    
    This releases the held funds back to the customer's card.
    Use this when cancelling appointments before consultation.
    
    Args:
        db: Database session
        payment: Payment record with authorization
        reason: Reason for voiding (for logging)
        
    Returns:
        2C2P API response dict
        
    Raises:
        ValueError: If payment is not in valid state for voiding
        Exception: If void API call fails
    """
    try:
        # Validation
        if payment.status not in [PaymentStatus.PAYMENT_AUTHORIZED, PaymentStatus.PAYMENT_CAPTURE_PENDING]:
            raise ValueError(
                f"Cannot void payment {payment.id} in status {payment.status}. "
                f"Must be PAYMENT_AUTHORIZED or PAYMENT_CAPTURE_PENDING"
            )
        
        if not payment.authorization_id:
            raise ValueError(f"Payment {payment.id} has no authorization_id")
        
        logging.info(
            f"Starting payment void: "
            f"payment_id={payment.id}, "
            f"auth_id={payment.authorization_id}, "
            f"reason={reason}"
        )
        
        # 2C2P Void payload
        # NOTE: Use "paymentType": "V" for void
        payload = {
            "merchantID": PAYMENT_2C2P_MERCHANT_ID,
            "nonceStr": str(uuid.uuid4()),
            "transactionId": payment.authorization_id,
            "paymentType": "V",  # CRITICAL: "V" = Void authorization (release funds)
            "currencyCode": PAYMENT_2C2P_CURRENCY_CODE,
        }
        
        # Call 2C2P void API
        # Note: 2C2P might use a different endpoint for void
        # Adjust endpoint based on 2C2P documentation
        response = call_2c2p_api('/payment/4.3/paymentVoid', payload)
        
        # Decode response
        if 'payload' in response:
            decoded = jwt_decode_payload(response['payload'])
        else:
            decoded = response
        
        # Check void success
        resp_code = decoded.get('respCode', '')
        if resp_code == '0000':
            # Void successful
            payment.status = PaymentStatus.PAYMENT_CANCELED
            
            # Update remarks
            remarks = payment.remarks or {}
            remarks['void_response'] = decoded
            remarks['voided_at'] = sg_datetime.now().isoformat()
            remarks['void_reason'] = reason
            payment.remarks = remarks
            
            db.commit()
            
            logging.info(
                f"Payment void successful: "
                f"payment_id={payment.id}, "
                f"transaction_id={decoded.get('transactionId', 'N/A')}"
            )
        else:
            # Void failed - this is serious, authorization still holds funds
            logging.error(
                f"Payment void FAILED: "
                f"payment_id={payment.id}, "
                f"resp_code={resp_code}, "
                f"resp_desc={decoded.get('respDesc', 'N/A')}. "
                f"CRITICAL: Funds may still be held!"
            )
            
            # Update remarks with error but don't change status
            # Manual intervention may be needed
            remarks = payment.remarks or {}
            remarks['void_error'] = decoded
            remarks['void_error_requires_manual_review'] = True
            payment.remarks = remarks
            db.commit()
            
            raise Exception(f"Void failed: {decoded.get('respDesc', 'Unknown error')}")
        
        return decoded
        
    except Exception as e:
        # Log error and re-raise
        logging.error(
            f"Payment void exception for payment {payment.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        
        # Update remarks but don't change status - needs manual review
        remarks = payment.remarks or {}
        remarks['void_exception'] = str(e)
        remarks['void_exception_requires_manual_review'] = True
        payment.remarks = remarks
        db.commit()
        
        raise
