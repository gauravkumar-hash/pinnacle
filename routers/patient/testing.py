import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import get_db
from models.payments import PaymentMethod, PaymentToken, PaymentType
from models.patient import Account
from routers.patient.utils import validate_user
from routers.payments.pgw2c2p.services import get_teleconsult_payment_token
from services.user import is_test_user
from utils.fastapi import SuccessResp

router = APIRouter(dependencies=[Depends(validate_user)])

@router.get("/enabled", response_model=SuccessResp)
def testing(user: Account = Depends(validate_user)):
    return SuccessResp(success=is_test_user(user))

class MockTeleconsultResponse(BaseModel):
    # webPaymentUrl: str
    card_brand: str
    card_last4: str
    amount: str
    payment_token: str
    customer_token: str

# Only used to mock the payment process for testing
@router.get('/mock/teleconsult/token', response_model=MockTeleconsultResponse)
def mock_teleconsult_token(teleconsult_id: Optional[str] = None, user = Depends(validate_user), db: Session = Depends(get_db)):
    if user.default_payment_method != PaymentMethod.CARD_2C2P:
        raise HTTPException(status_code=400, detail="Default payment method is not 2C2P")

    card_token = db.query(PaymentToken).filter(
        PaymentToken.account_id == user.id,
        PaymentToken.method == user.default_payment_method,
        PaymentToken.id == user.default_payment_id,
        PaymentToken.deleted == False
    ).first()
    if not card_token:
        raise HTTPException(status_code=400, detail="No default payment method found")
    
    # card_token = default_payment.payment_tokens[0]
    amount = 0.5
    try:
        payment_token, invoice_num = get_teleconsult_payment_token(db, user, amount, card_token, PaymentType.PREPAYMENT)
        return MockTeleconsultResponse(
            card_brand=card_token.details['brand'],
            card_last4=card_token.details['last4'],
            amount=f'${round(amount, 2):.2f}',
            payment_token=payment_token.paymentToken,
            customer_token=card_token.token
        )
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate payment token")
