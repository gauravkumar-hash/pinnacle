import logging
from models import SessionLocal
from models.model_enums import CollectionMethod
from models.payments import Payment, PaymentMethod, PaymentStatus, PaymentType
from routers.patient.actions.teleconsult_flow_backend import postpayment_success_webhook, prepayment_success_webhook
from routers.patient.teleconsult_family import JoinQueueReq, PrepaymentRateReq, get_rate, join_queue

# 1. Test Self
# 2. Test with Family
# 3. Test with Family and Self with code

firebase_uid = 'ERAVmyaLyBV6wEBgr1PsSXIwpPD2' # G3333333A
# family_ids = ['8a5d0651-f24e-4afc-9e6f-e6ba2820eaeb', '7e7e6be1-ec3d-4696-a16a-587583fc8399']
family_ids = ['8a5d0651-f24e-4afc-9e6f-e6ba2820eaeb']

# 1. [x] Test PCP with self + family member causes error
def get_rates():
    with SessionLocal() as db:
        req = PrepaymentRateReq(
            # code='AIA1234',
            family_ids=family_ids,
            include_user = False
        )
        rate = get_rate(req, firebase_uid, db)
        print(rate.model_dump_json(indent=4))

# get_rates()
# exit()

# Test Payment Endpoint
# 1. [x] INS Code with 2 family members
# 2. [x] INS Code with 2 family members and self
# 3. [x] INS Code with self
# 4. [x] INS Code with no one
# 5. [x] Stripe Card for self
# 6. [x] Stripe Card for self + Family Members
# 7. [x] Stripe PayNow for self + Family Members
# 8. [x] Corporate Code for self + Family Members
# MW Test
def create_prepayment():
    with SessionLocal() as db:
        req = JoinQueueReq(
            family_ids=family_ids,
            include_user=True,
            # code='INS',
            code='AIA1234',
            branch_id='749fe8f3-b2c7-4f92-ab4b-a7012216ccec',
            user_allergy='User Allergy',
            allergies={
                '8a5d0651-f24e-4afc-9e6f-e6ba2820eaeb': 'Patient 2 Allergy'
            },
            collection_method=CollectionMethod.PICKUP,
            payment_method=PaymentMethod.PAYNOW_STRIPE
        )
        resp = join_queue(req, firebase_uid, db)
        print(resp)


# Test Prepayment Webhook
# 1. [x] Stripe Card for self + Family Members
def stripe_prepayment_webhook():
    payment_method = PaymentMethod.CARD_STRIPE
    # session_id = 'cs_test_a1Lz1x7uXSRFHEcEJNnnQBiMVsry6grn8g7oVKOdOWX48Sc3RpN5SiAbXS'
    session_id = 'cs_test_a18zUjieTbYFHoeexpXOAgaDivqp2wDjSUN1RKpVC2rG7Vm8UkLGi2xHUj'
    payment_intent_id = 'pi_3Q5XAFCu0dFCVV9013PmhwAw'
    # For Card only
    brand = 'visa'
    last4 = '1234'

    # Check if payment succeeded

    with SessionLocal() as db:
        payments = []
        if payment_method == PaymentMethod.CARD_STRIPE:
            payments = db.query(Payment).where(
                    Payment.payment_id == payment_intent_id, 
                    Payment.payment_method == PaymentMethod.CARD_STRIPE
                ).all()
            
            for payment in payments:
                payment.status = PaymentStatus.PAYMENT_SUCCESS
                payment.remarks = { "brand": brand, "last4": last4 }

        elif payment_method == PaymentMethod.PAYNOW_STRIPE:
            payments = db.query(Payment).where(
                    Payment.payment_id.in_((session_id, payment_intent_id)),
                    Payment.payment_method == PaymentMethod.PAYNOW_STRIPE
                ).all()

            for payment in payments:
                payment.payment_id = payment_intent_id
                payment.status = PaymentStatus.PAYMENT_SUCCESS

        if not payments:
            logging.error(f"Stripe Webhook Record not found. Session ID: {payment_intent_id}, Pament ID: {payment_intent_id}")
            return { "success": False }
        
        db.commit()
            
        if payments[0].payment_type == PaymentType.PREPAYMENT:
            prepayment_success_webhook(db, payments)
        if payments[0].payment_type == PaymentType.POSTPAYMENT:
            postpayment_success_webhook(db, payments)

# create_prepayment()
# stripe_prepayment_webhook()

def get_teleconsult():
    with SessionLocal() as db:
        # teleconsults = get_teleconsults(db)
        # print(json.dumps([json.loads(row.model_dump_json()) for row in teleconsults], indent=4))
        
    #     # resp = get_teleconsult_with_doctor_id(db, 'd5b2266e-dc1f-42ea-8913-5ab930b00829')
    #     # print(resp)
        
    #     # resp = get_ended_teleconsults_with_doctor_id(db, 'd5b2266e-dc1f-42ea-8913-5ab930b00829', date(2024, 10, 2))
    #     # print(resp)
        
    #     # resp = get_teleconsult_with_id(db, '90b04b90-1afc-483b-8aea-5b53c9392f6b')
    #     # print(resp)
        
    #     # resp = get_teleconsult_with_id(db, 'c698a6bb-1a1a-425b-9bf3-8348ebd084e6')
    #     # print(resp)
        
    #     account_id = '9405f693-38ca-4f20-a7be-d79ac6d25e21'
    #     # teleconsult_id_with_family = '90b04b90-1afc-483b-8aea-5b53c9392f6b'
        # teleconsult_id = '5a585701-912b-492e-9421-72a49f7b44a0'
        # resp = get_details(teleconsult_id, firebase_uid, db)
        # print(resp.model_dump_json(indent=4))
        
        from routers.patient.visits import get_teleconsults
        resp = get_teleconsults(firebase_uid, db)
        for row in resp:
            print(row.model_dump_json(indent=4))
    
get_teleconsult()

# with SessionLocal() as db:
#     teleconsult_id = '5a585701-912b-492e-9421-72a49f7b44a0'
#     resp = create_postpayment(CreatePostpaymentReq(
#         id=teleconsult_id,
#         payment_method=PaymentMethod.CARD_STRIPE
#     ), firebase_uid, db)
#     print(resp)
    
    
