from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models.patient import Account
from models.payments import PaymentMethod, PaymentToken
from models.model_enums import PatientType
from repository.payments import PaymentMethodDetail, get_default_payment
from routers.patient.utils import validate_firebase_token, validate_user
from utils.fastapi import SuccessResp
from typing import Optional

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class PaymentMethodsResp(BaseModel):
    payment_methods: list[PaymentMethodDetail]
    enable_add_2c2p: bool

@router.get("/", response_model=PaymentMethodsResp)
def get_payment_methods(
    user: Account = Depends(validate_user),
    db: Session = Depends(get_db),
    patient_type: Optional[str] = Query(
        None,
        description="Patient type for filtering payment methods (private_patient, migrant_worker)"
    )
):
    """
    Get available payment methods for the user.
    
    Filtering rules based on patient type:
    - migrant_worker (PCP): Only PayNow allowed (no credit cards)
    - private_patient: Only credit cards allowed (no PayNow)
    - None/unknown: Show all payment methods (backward compatible)
    
    Args:
        user: Authenticated user account
        db: Database session
        patient_type: Optional patient type for filtering payment methods
        
    Returns:
        List of available payment methods with default indication
    """
    payment_tokens = db.query(PaymentToken).filter(
            PaymentToken.account_id == user.id,
            PaymentToken.deleted == False
        ) \
        .order_by(PaymentToken.provider, PaymentToken.created_at.desc()) \
        .all()
    
    payment_methods = []
    
    # Determine if PayNow should be shown based on patient type
    # Migrant Workers (PCP) = PayNow ONLY
    # Private Patients = Credit Cards ONLY (no PayNow)
    # Unknown/None = Show all (backward compatible)
    show_paynow = True
    show_credit_cards = True
    
    if patient_type:
        if patient_type == PatientType.MIGRANT_WORKER.value or patient_type == 'migrant_worker':
            # Migrant workers: PayNow only, no credit cards
            show_paynow = True
            show_credit_cards = False
        elif patient_type == PatientType.PRIVATE_PATIENT.value or patient_type == 'private_patient':
            # Private patients: Credit cards only, no PayNow
            show_paynow = False
            show_credit_cards = True
    
    # Add PayNow if allowed for this patient type
    if show_paynow:
        payment_methods.append(
            PaymentMethodDetail(
                id='paynow_stripe',
                method=PaymentMethod.PAYNOW_STRIPE,
                icon='paynow',
                title='',
                is_default=user.default_payment_method == PaymentMethod.PAYNOW_STRIPE,
                can_remove=False,
            )
        )

    # Only Test Users in Production can use 2C2P Card Payments.
    # test_user = is_test_user(user)
    # enable_2c2p = test_user
    # # TODO: Enable Stripe Card Payment for test and non test users. To be disabled upon 2C2P launch
    # payment_methods.append(
    #     PaymentMethodDetail(
    #         id='card_stripe',
    #         method=PaymentMethod.CARD_STRIPE,
    #         icon='card',
    #         title='Debit / Credit Card',
    #         is_default=user.default_payment_method == PaymentMethod.CARD_STRIPE,
    #         can_remove=False,
    #     )
    # )

    # Add saved credit cards if allowed for this patient type
    if show_credit_cards:
        for payment_token in payment_tokens:
            payment_methods.append(
                PaymentMethodDetail(
                    id=str(payment_token.id),
                    method=payment_token.method,
                    icon=payment_token.details['brand'],
                    title='**** ' + payment_token.details['last4'],
                    is_default=user.default_payment_method == payment_token.method and user.default_payment_id == str(payment_token.id),
                    can_remove=True,
                )
            )
    
    return PaymentMethodsResp(
        payment_methods=payment_methods,
        enable_add_2c2p=show_credit_cards  # Only allow adding cards for private patients
    )

@router.get("/default", response_model=PaymentMethodDetail)
def get_default_payment_method(firebase_uid: str = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    default_payment = get_default_payment(db, user)
    return default_payment

class SetDefaultPaymentMethodReq(BaseModel):
    payment_method: PaymentMethod
    payment_method_id: str | None = None

@router.post("/set_default", response_model=SuccessResp)
def set_default_payment_method(req: SetDefaultPaymentMethodReq, firebase_uid: str = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    if req.payment_method == PaymentMethod.PAYNOW_STRIPE:
        user.default_payment_method = PaymentMethod.PAYNOW_STRIPE
        user.default_payment_id = None
        db.commit()
        return SuccessResp(success=True)
    
    if req.payment_method == PaymentMethod.CARD_STRIPE:
        user.default_payment_method = PaymentMethod.CARD_STRIPE
        user.default_payment_id = None
        db.commit()
        return SuccessResp(success=True)
     
    payment_token = db.query(PaymentToken).filter(
            PaymentToken.id == req.payment_method_id,
            PaymentToken.account_id == user.id,
            PaymentToken.deleted == False
        ).first()    
    if not payment_token:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    user.default_payment_method = payment_token.method
    user.default_payment_id = str(payment_token.id)
    db.commit()
    return SuccessResp(success=True)

class DeletePaymentMethodReq(BaseModel):
    payment_method_id: str

@router.delete("/delete", response_model=SuccessResp)
def delete_payment_method(req: DeletePaymentMethodReq, firebase_uid: str = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    rows = db.query(PaymentToken).filter(
            PaymentToken.id == req.payment_method_id,
            PaymentToken.account_id == user.id,
            PaymentToken.deleted == False
        ).update({
            'deleted': True
        })

    if user.default_payment_id == req.payment_method_id:
        user.default_payment_method = PaymentMethod.PAYNOW_STRIPE
        user.default_payment_id = None

    if not rows:
        raise HTTPException(status_code=404, detail="Payment method not found")
    db.commit()
    return SuccessResp(success=True)