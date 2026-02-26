# TODO: To be replaced in .env
from models.patient import Account
from config import PAYMENT_2C2P_CURRENCY_CODE, PAYMENT_2C2P_MERCHANT_ID

import logging
import uuid
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
