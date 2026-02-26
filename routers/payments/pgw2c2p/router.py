from enum import Enum
import logging
from typing import Literal, Optional
from repository.appointment import get_appointment_by_payment
from routers.patient.actions.teleconsult_flow_backend import postpayment_success_webhook, prepayment_success_webhook
from config import PAYMENT_2C2P_MERCHANT_ID, PAYMENT_2C2P_CURRENCY_CODE

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from models import get_db
from models.payments import Payment, PaymentMethod, PaymentStatus, PaymentTransaction, PaymentType
from routers.patient.utils import validate_firebase_token, validate_user
from routers.payments.pgw2c2p.pgw_models import PGWPaymentInquiryResponse, PGWWebhookResp
from routers.payments.pgw2c2p.services import get_payment_token, save_payment_token_to_db
from utils.fastapi import SuccessResp
from sqlalchemy.orm import Session
from .helpers import call_2c2p_api, jwt_decode_payload
from services.appointment import appointment_success_webhook

# Router
router = APIRouter()

class PaymentTokenResponse(BaseModel):
    webPaymentUrl: str
    paymentToken: str

@router.get("/tokenize/token", response_model=PaymentTokenResponse)
def get_tokenize_payment_token(db: Session = Depends(get_db), firebase_uid: str = Depends(validate_firebase_token)):
    '''
    https://developer.2c2p.com/docs/sdk-api-payment-ui
    https://developer.2c2p.com/docs/sdk-customer-tokenization
    '''
    user = validate_user(db, firebase_uid)

    payload: dict = {
        "description": "Tokenization",
        "amount": 0.00,
        "tokenizeOnly": True,
        
        "merchantID":PAYMENT_2C2P_MERCHANT_ID,
        "nonceStr": str(uuid.uuid4()),
        "paymentChannel": ["GCARD"],
        "request3DS" : "Y",
        "currencyCode":PAYMENT_2C2P_CURRENCY_CODE,
    }
    
    try:
        payment_token, invoice_num = get_payment_token(db, user, payload, PaymentType.TOKENIZATION)
        # raise HTTPException(status_code=500, detail="Error")
        return PaymentTokenResponse(
            webPaymentUrl=payment_token.webPaymentUrl,
            paymentToken=payment_token.paymentToken
        )
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate payment token")


# Uncomment for Payment Inquiry Endpoint
class PaymentInquiryReq(BaseModel):
    paymentToken: Optional[str] = None
    invoiceNo: Optional[str] = None

class PaymentInquiryResp(BaseModel):
    return_to_root: bool
    redirect_pathname: Literal['/profile/payment_methods', '/teleconsult/consultation', '/appointment/consultation']
    redirect_params: dict

@router.post("/payment_inquiry", response_model=PaymentInquiryResp)
def get_payment_inquiry(req: PaymentInquiryReq, firebase_uid: str = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    payload = {
        "merchantID": PAYMENT_2C2P_MERCHANT_ID
    }
    if req.invoiceNo:
        payload['invoiceNo'] = req.invoiceNo
    if req.paymentToken:
        payload['paymentToken'] = req.paymentToken
    
    data = call_2c2p_api('/payment/4.3/paymentInquiry', payload)
    payload = jwt_decode_payload(data['payload'])
    payload = PGWPaymentInquiryResponse(**payload)
    
    # Assumed that when this is successful, webhook already setup the database correctly and can navigate to Teleconsult screen
    # https://developer.2c2p.com/docs/response-code-payment
    # 
    if payload.respCode == PGWPaymentRespCodes.TOKENIZATION_SUCCESS:
        # # In the event that webhook has not been correctly setup, token will still be saved to databaase
        # save_payment_token_to_db(db, str(user.id), payload)
        
        return PaymentInquiryResp(
            return_to_root=False,
            redirect_pathname='/profile/payment_methods',
            redirect_params={}
        )

    elif payload.respCode == PGWPaymentRespCodes.SUCCESS:
        teleconsult = None
        payment = db.query(Payment).filter(Payment.payment_id == payload.invoiceNo).first()
        if payment and payment.payment_type in [PaymentType.PREPAYMENT, PaymentType.POSTPAYMENT]:
            teleconsult = payment.teleconsults[0]
            return PaymentInquiryResp(
                return_to_root=True,
                redirect_pathname='/teleconsult/consultation',
                redirect_params={
                    'id': str(teleconsult.id) if payment.payment_type == PaymentType.POSTPAYMENT else None
                }
            )
        elif payment and payment.payment_type == PaymentType.APPOINTMENT:
            appt = get_appointment_by_payment(db, payment)
            if not appt:
                logging.error(f"2C2P Payment Inquiry: Appointment not found for id: {payment.id}")
                raise HTTPException(status_code=400, detail="Appointment not found")
            return PaymentInquiryResp(
                return_to_root=True,
                redirect_pathname='/appointment/consultation',
                redirect_params={ 'id': str(appt.id) }
            )

    logging.error(f"2C2P Payment Inquiry Failed: {payload}")
    raise HTTPException(status_code=400, detail="Payment Inquiry Failed")

class Payment2C2PWebhookPayload(BaseModel):
    payload: str

class PGWPaymentRespCodes(str, Enum):
    # https://developer.2c2p.com/docs/response-code-payment
    SUCCESS = '0000'
    TOKENIZATION_SUCCESS = '4200'

@router.post("/webhook", response_model=SuccessResp)
async def handle_2c2p_webhook(req: Payment2C2PWebhookPayload, key: str = Query(...), db: Session = Depends(get_db)):
    '''
    2C2P Admin Panel: Redirect API - Backend return URL
    '''
    payload = jwt_decode_payload(req.payload)
    payload = PGWWebhookResp(**payload)
    
    record = db.query(PaymentTransaction).filter(PaymentTransaction.invoice_num == payload.invoiceNo).first()
    if not record:
        logging.error(f"2C2P Webhook: Payment transaction not found in db: {payload}")
    else:
        record.webhook = payload.model_dump()
        if payload.respCode in [PGWPaymentRespCodes.SUCCESS, PGWPaymentRespCodes.TOKENIZATION_SUCCESS]:
            record.status = PaymentStatus.PAYMENT_SUCCESS
        else:
            # logging.error(f"2C2P Webhook: Payment failed. Invoice No: {payload.invoiceNo}")
            record.status = PaymentStatus.PAYMENT_FAILED
        db.commit()

    # Save Payment Token to DB
    if record and payload.respCode == PGWPaymentRespCodes.TOKENIZATION_SUCCESS:
        save_payment_token_to_db(db, str(record.account_id), payload)
        # Trigger Webhooks for payment success. Similar to Stripe Webhook.
    
    # Navigate User to Teleconsult Screen
    if record and payload.respCode == PGWPaymentRespCodes.SUCCESS:
        payments = db.query(Payment).where(
                Payment.payment_id == payload.invoiceNo,
                Payment.payment_method == PaymentMethod.CARD_2C2P
            ).all()
        if not payments:
            logging.error(f"2C2P Webhook Record not found. Invoice No: {payload.invoiceNo}")
            return SuccessResp(success=False)

        for payment in payments:
            payment.status = PaymentStatus.PAYMENT_SUCCESS
        db.commit()
        
        if payments[0].payment_type == PaymentType.PREPAYMENT:
            prepayment_success_webhook(db, payments)
        elif payments[0].payment_type == PaymentType.POSTPAYMENT:
            postpayment_success_webhook(db, payments)
        elif payments[0].payment_type == PaymentType.APPOINTMENT:
            appointment_success_webhook(db, payments)

    return SuccessResp(success=True)

# class PaymentTransactionPayload(BaseModel):
#     paymentToken: str
#     clientID: str
#     locale: str = "en"
#     additionalInfo: bool = True

# @router.get("/transaction", response_model=SuccessResp)
# def get_transaction_result(token: str, client_id: str):
#     payload_dict = PaymentTransactionPayload(paymentToken=token, clientID=client_id).model_dump()
#     data = call_2c2p_api('/payment/4.3/transactionStatus', payload_dict)
#     payload = jwt_decode_payload(data['payload'])

#     return PaymentTransactionResponse(success=payload['respCode'] == '2000')
