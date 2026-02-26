
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models.patient import Account
from models.payments import Payment, PaymentMethod, PaymentProvider, PaymentStatus, PaymentToken, PaymentType
from models.teleconsult import Teleconsult
from routers.payments.pgw2c2p.services import get_teleconsult_payment_token
from services.teleconsult import PaymentTotal
from utils.stripe import fetch_payment_sheet, generate_stripe_paynow_link

def create_prepayment(
        db: Session, 
        user: Account,
        teleconsults: list[Teleconsult],
        rates: list[PaymentTotal],
        payment_method: PaymentMethod,        
        payment_method_id: Optional[str] = None,
        corporate_code: Optional[str] = None,
        existing_teleconsult_session: bool = False
    ):
    '''
    Note: For multiple teleconults, multiple payment records are created with the same payment_id.
    This is to allow when family accounts are desynced from the main account, the new account can view their own records
    '''
    payment_id = ''
    txn_amount = sum([rate.total for rate in rates]) # Total amount to be paid across all Teleconsult transactions
    payment_provider_params: dict = {}
    remarks = None

    # Stripe Credit/Debit Card Flow
    if payment_method == PaymentMethod.CARD_STRIPE:
        # Create payment with payment provider
        stripe_body = fetch_payment_sheet(db, user, txn_amount)
        if not stripe_body:
            raise Exception("Failed to initate Credit / Debit Card Payment")
        # Params required for Payment Record
        payment_id = str(stripe_body['payment_intent']['id'])
        payment_method=PaymentMethod.CARD_STRIPE
        payment_provider=PaymentProvider.APP_STRIPE
        # Params required by mobile application to launch payment
        payment_provider_params = stripe_body
    # Stripe PayNow Flow
    elif payment_method == PaymentMethod.PAYNOW_STRIPE:
        # Create payment with payment provider
        stripe_session = generate_stripe_paynow_link(db, user, txn_amount)
        # Params required for Payment Record
        payment_id = stripe_session.id
        payment_method=PaymentMethod.PAYNOW_STRIPE
        payment_provider=PaymentProvider.APP_STRIPE
        # Params required by mobile application to launch payment
        payment_provider_params = { "url": stripe_session.url }
    elif payment_method == PaymentMethod.CARD_2C2P:
        # Create payment with payment provider
        payment_method=PaymentMethod.CARD_2C2P
        payment_provider=PaymentProvider.APP_2C2P
        card_token = db.query(PaymentToken).filter(
            PaymentToken.account_id == user.id,
            PaymentToken.method == PaymentMethod.CARD_2C2P,
            PaymentToken.id == payment_method_id,
            PaymentToken.deleted == False
        ).first()
        if not card_token:
            raise Exception("Card Token not found")
        remarks = { "brand": card_token.details['brand'], "last4": card_token.details['last4'] }
        
        payment_token, payment_id = get_teleconsult_payment_token(db, user, txn_amount, card_token, PaymentType.PREPAYMENT)
        # Params required by mobile application to launch payment
        payment_provider_params = {
            "card_brand": card_token.details['brand'],
            "card_last4": card_token.details['last4'],
            "amount": f'${round(txn_amount, 2):.2f}',
            "payment_token": payment_token.paymentToken,
            "customer_token": card_token.token
        }

    elif payment_method == PaymentMethod.DEFERRED_PAYMENT:
        # Logic to check if corporate code is required
        if not corporate_code and not existing_teleconsult_session:
            raise Exception("Corporate Code is required for Deferred Payment")
        # Params required for Payment Record
        payment_id = corporate_code if corporate_code else ''
        payment_method = PaymentMethod.DEFERRED_PAYMENT
        payment_provider = None
        # Params required by mobile application to launch payment
        payment_provider_params = {}
    elif payment_method == PaymentMethod.NETS_CLICK:
        raise Exception("Payment Method not supported")
    else:
        raise Exception("Payment Method not supported")
    
    # Create Payment Record
    payments: list[Payment] = []
    for teleconsult, rate in zip(teleconsults, rates):
        # For deferred payment, payment amount is 0.0
        if payment_method == PaymentMethod.DEFERRED_PAYMENT:
            payment_amount = 0.0
            status = PaymentStatus.PAYMENT_SUCCESS
        else:
            payment_amount = rate.total
            status = PaymentStatus.PAYMENT_CREATED

        payment = Payment(
            payment_id=payment_id,
            account_id=teleconsult.account_id,
            payment_breakdown=[b.model_dump() for b in rate.breakdown],
            payment_amount=payment_amount,
            status=status,
            remarks=remarks,
            payment_type=PaymentType.PREPAYMENT,
            payment_method=payment_method,
            payment_provider=payment_provider,
            teleconsults=[teleconsult]
        )
        db.add(payment)
        payments.append(payment)
    db.commit()

    # payment_id contains the ID for that one payment record
    payment_provider_params['id'] = payment_id
    return payments, payment_provider_params

def create_postpayment_record(
        db: Session,
        user: Account,
        teleconsults: list[Teleconsult],
        payment_method: PaymentMethod,
        payment_method_id: Optional[str] = None,
    ):
    
    payment_id = ''
    txn_amount = round(sum([t.balance for t in teleconsults]), 2) # Total amount to be paid across all Teleconsult transactions
    payment_provider_params: dict = {}
    remarks = None
    # Stripe Credit/Debit Card Flow
    if payment_method == PaymentMethod.CARD_STRIPE:
        # Create payment with payment provider
        stripe_body = fetch_payment_sheet(db, user, txn_amount)
        if not stripe_body:
            raise Exception("Failed to initate Credit / Debit Card Payment")
        # Params required for Payment Record
        payment_id = str(stripe_body['payment_intent']['id'])
        payment_method=PaymentMethod.CARD_STRIPE
        payment_provider=PaymentProvider.APP_STRIPE
        # Params required by mobile application to launch payment
        payment_provider_params = stripe_body
    # Stripe PayNow Flow
    elif payment_method == PaymentMethod.PAYNOW_STRIPE:
        # Create payment with payment provider
        stripe_session = generate_stripe_paynow_link(db, user, txn_amount)
        # Params required for Payment Record
        payment_id = stripe_session.id
        payment_method=PaymentMethod.PAYNOW_STRIPE
        payment_provider=PaymentProvider.APP_STRIPE
        # Params required by mobile application to launch payment
        payment_provider_params = { "url": stripe_session.url }

    elif payment_method == PaymentMethod.CARD_2C2P:
        # Create payment with payment provider
        payment_method=PaymentMethod.CARD_2C2P
        payment_provider=PaymentProvider.APP_2C2P
        card_token = db.query(PaymentToken).filter(
            PaymentToken.account_id == user.id,
            PaymentToken.method == PaymentMethod.CARD_2C2P,
            PaymentToken.id == payment_method_id,
            PaymentToken.deleted == False
        ).first()
        if not card_token:
            raise Exception("Card Token not found")
        remarks = { "brand": card_token.details['brand'], "last4": card_token.details['last4'] }
        
        payment_token, payment_id = get_teleconsult_payment_token(db, user, txn_amount, card_token, PaymentType.POSTPAYMENT)
        # Params required by mobile application to launch payment
        payment_provider_params = {
            "card_brand": card_token.details['brand'],
            "card_last4": card_token.details['last4'],
            "amount": f'${round(txn_amount, 2):.2f}',
            "payment_token": payment_token.paymentToken,
            "customer_token": card_token.token
        }
    
    elif payment_method == PaymentMethod.NETS_CLICK:
        raise Exception("Payment Method not supported")
    else:
        raise Exception("Payment Method not supported")

    # Create Payment Record
    payments: list[Payment] = []
    for teleconsult in teleconsults:
        if teleconsult.balance == 0.0:
            continue

        payment_amount = teleconsult.balance
        status = PaymentStatus.PAYMENT_CREATED

        payment = Payment(
            payment_id=payment_id,
            account_id=teleconsult.account_id,
            payment_breakdown=teleconsult.payment_breakdown,
            payment_amount=payment_amount,
            status=status,
            remarks=remarks,
            payment_type=PaymentType.POSTPAYMENT,
            payment_method=payment_method,
            payment_provider=payment_provider,
            teleconsults=[teleconsult]
        )
        db.add(payment)
        payments.append(payment)
    db.commit()

    # payment_id contains the ID for that one payment record
    payment_provider_params['id'] = payment_id
    return payments, payment_provider_params

def create_appointment_payment(
        db: Session,
        user: Account,
        txn_amount: float,
        payment_method: PaymentMethod,
        payment_method_id: Optional[str] = None,
    ):
    '''
    Create payment record for Appointment
    '''
    payment_id = ''
    payment_provider_params: dict = {}
    remarks = None

    # Stripe PayNow Flow
    if payment_method == PaymentMethod.PAYNOW_STRIPE:
        # Create payment with payment provider
        stripe_session = generate_stripe_paynow_link(db, user, txn_amount, name='Appointment Fees')
        # Params required for Payment Record
        payment_id = stripe_session.id
        payment_method=PaymentMethod.PAYNOW_STRIPE
        payment_provider=PaymentProvider.APP_STRIPE
        # Params required by mobile application to launch payment
        payment_provider_params = { "url": stripe_session.url }
    # 2C2P Credit/Debit Card Flow
    elif payment_method == PaymentMethod.CARD_2C2P:
        # Create payment with payment provider
        payment_method=PaymentMethod.CARD_2C2P
        payment_provider=PaymentProvider.APP_2C2P
        card_token = db.query(PaymentToken).filter(
            PaymentToken.account_id == user.id,
            PaymentToken.method == PaymentMethod.CARD_2C2P,
            PaymentToken.id == payment_method_id,
            PaymentToken.deleted == False
        ).first()
        if not card_token:
            raise Exception("Card Token not found")
        remarks = { "brand": card_token.details['brand'], "last4": card_token.details['last4'] }
        
        payment_token, payment_id = get_teleconsult_payment_token(db, user, txn_amount, card_token, PaymentType.PREPAYMENT)
        # Params required by mobile application to launch payment
        payment_provider_params = {
            "card_brand": card_token.details['brand'],
            "card_last4": card_token.details['last4'],
            "amount": f'${round(txn_amount, 2):.2f}',
            "payment_token": payment_token.paymentToken,
            "customer_token": card_token.token
        }
    # TODO: elif payment_method == PaymentMethod.NETS_CLICK:
    else:
        raise Exception("Payment Method not supported")
    
    # Create Payment Record
    payment = Payment(
        payment_id=payment_id,
        account_id=user.id,
        payment_breakdown=[], # No longer used, attached to Appointment
        payment_amount=txn_amount,
        status=PaymentStatus.PAYMENT_CREATED,
        remarks=remarks,
        payment_type=PaymentType.APPOINTMENT,
        payment_method=payment_method,
        payment_provider=payment_provider
    )
    db.add(payment)
    db.commit()

    # payment_id contains the ID for that one payment record
    payment_provider_params['id'] = payment_id
    return payment, payment_provider_params

class PaymentMethodDetail(BaseModel):
    id: str
    method: PaymentMethod
    icon: str
    title: str
    subtitle: str | None = None
    is_default: bool
    can_remove: bool

def get_default_payment(db: Session, user: Account):
    # Return default payment for PayNow
    if user.default_payment_method == PaymentMethod.PAYNOW_STRIPE:
        return PaymentMethodDetail(
                id='paynow_stripe',
                method=PaymentMethod.PAYNOW_STRIPE,
                icon='paynow',
                title='',
                is_default=user.default_payment_method == PaymentMethod.PAYNOW_STRIPE,
                can_remove=False,
            )

    
    # # For v1.4.0, for non-test users, only Card Stripe is supported
    # test_user = is_test_user(user)
    # if not test_user or user.default_payment_method == PaymentMethod.CARD_STRIPE:
    #     return PaymentMethodDetail(
    #         id='card_stripe',
    #         method=PaymentMethod.CARD_STRIPE,
    #         icon='card',
    #         title='Debit / Credit Card',
    #         is_default=user.default_payment_method == PaymentMethod.CARD_STRIPE,
    #         can_remove=False,
    #     )

    # Get the default payment method
    if user.default_payment_method:
        payment_token = db.query(PaymentToken).filter(
            PaymentToken.account_id == user.id,
            PaymentToken.method == user.default_payment_method,
            PaymentToken.id == user.default_payment_id,
            PaymentToken.deleted == False
        ).first()
        if payment_token:
            return PaymentMethodDetail(
                id=str(payment_token.id),
                method=payment_token.method,
                icon=payment_token.details['brand'],
                title='**** ' + payment_token.details['last4'],
                is_default=user.default_payment_method == payment_token.method and user.default_payment_id == str(payment_token.id),
                can_remove=True,
            )

    # Default to PayNow if no other default payment method is found
    return PaymentMethodDetail(
        id='paynow_stripe',
        method=PaymentMethod.PAYNOW_STRIPE,
        icon='paynow',
        title='',
        is_default=user.default_payment_method == PaymentMethod.PAYNOW_STRIPE,
        can_remove=False,
    )
