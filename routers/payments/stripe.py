import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.payments import Payment, PaymentType
from models import get_db
from sqlalchemy.orm import Session

from repository.appointment import get_appointment_by_payment
from utils.stripe import check_payment_success

router = APIRouter()

class CheckPaymentSuccessResp(BaseModel):
    redirect_url: Literal['/teleconsult/consultation', '/appointment/consultation']
    redirect_params: dict

@router.post("/paynow/success", response_model=CheckPaymentSuccessResp)
def check_stripe_paynow_success(payment_id: str, db: Session = Depends(get_db)):
    '''
    Assumed that payment success will always be triggered by webhook thus ignoring
    payment_id is the session id from stripe
    '''
    success, payment_intent_id = check_payment_success(payment_id)
    logging.info(f"Stripe Paynow Success: {success}, {payment_intent_id}")
    if not success:
        logging.error(f"Stripe Paynow Success: Failed to check payment success for payment_id: {payment_id}, intent_id: {payment_intent_id}")
        raise HTTPException(status_code=400, detail="Failed to redirect to confirmation page")
    
    payment = db.query(Payment).filter(
        Payment.payment_id.in_([payment_id, payment_intent_id])
    ).first()
    if not payment:
        logging.error(f"Stripe Paynow Success: Payment not found for payment_id: {payment_id}, intent_id: {payment_intent_id}")
        raise HTTPException(status_code=400, detail="Payment not found")
    
    if payment.payment_type == PaymentType.APPOINTMENT:
        appt = get_appointment_by_payment(db, payment)
        if not appt:
            logging.error(f"Stripe Paynow Success: Appointment not found for payment_id: {payment_id}, intent_id: {payment_intent_id}")
            raise HTTPException(status_code=400, detail="Appointment not found")
        return CheckPaymentSuccessResp(
            redirect_url='/appointment/consultation',
            redirect_params={
                'id': appt.id,
            }
        )
    elif payment.payment_type == [PaymentType.PREPAYMENT, PaymentType.POSTPAYMENT]:
        return CheckPaymentSuccessResp(
            redirect_url='/teleconsult/consultation',
            redirect_params={}
        )
    
    logging.error(f"Stripe Paynow Success: Invalid payment type for payment_id: {payment_id}, intent_id: {payment_intent_id}")
    raise HTTPException(status_code=400, detail="Invalid payment type")
