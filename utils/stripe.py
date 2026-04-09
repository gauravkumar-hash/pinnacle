import logging
from models import Account
from config import stripe, STRIPE_PUBLISHABLE_KEY, BACKEND_API_URL
from sqlalchemy.orm import Session

def fetch_stripe_customer(db: Session, user: Account):    
    if not user.stripe_id:
        customer = stripe.Customer.create()
        user.stripe_id = customer["id"]
        db.commit()
    else:
        customer = stripe.Customer.retrieve(user.stripe_id)

    return customer

def fetch_customer_sheet(db: Session, user: Account):
    try:
        customer = fetch_stripe_customer(db, user)
        ephemeral_key = stripe.EphemeralKey.create(
            customer=customer["id"],
            stripe_version='2024-04-10',
        )

        setup_intent = stripe.SetupIntent.create(
                customer=customer["id"], 
                payment_method_types=["card"]
            )
        
        return {
            "ephemeral_key": ephemeral_key.get('secret'),
            "setup_intent": setup_intent.client_secret,
            "customer_id": customer["id"]
        }
    except Exception as e:
        logging.error(f"Stripe Exception: {e}")
        print(f"Error occurred: {e}")

def fetch_payment_sheet(db: Session, user: Account, amount: float):
    try:
        # Use an existing Customer ID if this is a returning customer
        customer = fetch_stripe_customer(db, user)
        stripeAmount = round(amount * 100)
        ephemeral_key = stripe.EphemeralKey.create(
            customer=customer["id"],
            stripe_version='2024-04-10',
        )
        payment_intent = stripe.PaymentIntent.create(
            amount=stripeAmount,
            currency='sgd',
            customer=customer["id"],
            payment_method_types=["card"],
            setup_future_usage="off_session"
        )

        # # Use payment intent id as identifier for sse session
        # await handle_sse_session_creation(session_id=paymentIntent.id, db=db)
        return {
            "payment_intent": {
                "client_secret": payment_intent.client_secret,
                "id": payment_intent.id,
            },
            "ephemeral_key": ephemeral_key.get('secret'),
            "customer": customer["id"],
            "publishable_key": STRIPE_PUBLISHABLE_KEY
        }
    except Exception as e:
        logging.error(f"Stripe Exception: {e}")
        print(f"Error occurred: {e}")

def generate_stripe_paynow_link(db: Session, user: Account, amount: float, name: str = 'Telemedicine Consultation Fees'):
    stripeAmount = round(amount * 100)
    customer = fetch_stripe_customer(db, user)

    # Create a new Checkout Session for the order
    session = stripe.checkout.Session.create(
        payment_method_types=['paynow'],
        line_items=[{
            'price_data': {
                'currency': "sgd",
                'product_data': {
                    'name': name,
                },
                'unit_amount': stripeAmount,
            },
            'quantity': 1,
        }],
        mode='payment',
        customer=customer.id,
        success_url=BACKEND_API_URL + '/api/teleconsult/payment/success?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=BACKEND_API_URL + '/api/teleconsult/payment/cancel',
    )

    return session

def check_payment_success(payment_session_id: str):    
    # https://docs.stripe.com/api/checkout/sessions/retrieve?api-version=2025-04-30.basil
    session = stripe.checkout.Session.retrieve(payment_session_id)
    success = False
    payment_intent_id = None
    
    if session.payment_status == 'paid':
        success = True
        if session.payment_intent:
            payment_intent_id = str(session.payment_intent)
            
    return success, payment_intent_id
