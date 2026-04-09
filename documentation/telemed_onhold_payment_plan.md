# Telemed On-Hold Payment Implementation Plan

## Date: April 8, 2026

## Executive Summary

### Current Situation

- Telemed currently requires **pre-payment** from patients
- When patients cancel before seeing the doctor, **refunds must be processed**
- This creates operational overhead and poor user experience

### Requested Features

1. **Payment Authorization & Capture (Hold & Charge)**
   - Hold payment authorization from patient
   - Only capture/charge after teleconsultation is complete
   - Combine subsequent payments (medication, delivery) into one lumpsum charge

2. **Payment Method Restriction by Patient Type**
   - **Migrant Workers:** Can use both PayNow and Credit Card
   - **Private Patients:** Restricted to Credit Card only (no PayNow option)

---

## Technical Analysis

### Current Payment Architecture

#### Payment Methods Available

```python
class PaymentMethod(Enum):
    NETS_CLICK = 'nets_click'
    CARD_STRIPE = 'card_stripe'
    CARD_SGIMED = 'card_sgimed'
    CARD_2C2P = 'card_2c2p'
    PAYNOW_NETS = 'paynow_nets'
    PAYNOW_STRIPE = 'paynow_stripe'
    PAYNOW_2C2P = 'paynow_2c2p'
    DEFERRED_PAYMENT = 'deferred_payment'
```

#### Patient Types

```python
class PatientType(str, Enum):
    PRIVATE_PATIENT = 'private_patient'
    MIGRANT_WORKER = 'migrant_worker'
```

#### Current Payment Flow

1. **Prepayment Creation** (`/api/teleconsult/prepayment/create`)
   - Patient selects payment method
   - Payment is immediately charged
   - Teleconsult status → `PREPAYMENT`
   - On success → Patient enters queue

2. **Postpayment (if applicable)** (`/api/teleconsult/postpayment/create`)
   - After consultation, if additional charges exist
   - Medication/delivery fees charged separately
   - Creates **second payment transaction**

### Payment Gateway Capabilities

#### ✅ 2C2P (Credit/Debit Card)

- **Supports:** Authorization & Capture flow
- **How it works:**
  - Authorize: Hold funds on customer's card
  - Capture: Charge the held funds later
  - Can be implemented with existing 2C2P integration

#### ❌ Stripe PayNow

- **Does NOT support:** Authorization & Capture
- **Reason:** PayNow is instant bank transfer (like a bank wire)
- **Limitation:** No way to "hold" funds with bank transfers

---

## Implementation Requirements

### Feature 1: Payment Authorization & Capture

#### Database Changes Required

**1. Add new Payment Statuses**

```python
# File: /models/payments.py

class PaymentStatus(Enum):
    PAYMENT_CREATED = 'payment_created'
    PAYMENT_AUTHORIZED = 'payment_authorized'  # NEW - Funds held
    PAYMENT_CAPTURE_PENDING = 'payment_capture_pending'  # NEW - Ready to capture
    PAYMENT_CAPTURED = 'payment_captured'  # NEW - Funds charged
    PAYMENT_CANCELED = 'payment_canceled'
    PAYMENT_EXPIRED = 'payment_expired'
    PAYMENT_FAILED = 'payment_failed'
    PAYMENT_SUCCESS = 'payment_success'
```

**2. Add Payment Authorization Tracking**

```python
# File: /models/payments.py

class Payment(Base):
    __tablename__ = "payment_logs"

    # Existing fields...

    # NEW FIELDS for authorization & capture
    authorized_amount: Mapped[Optional[float]]  # Amount authorized
    captured_amount: Mapped[Optional[float]]  # Amount actually captured
    authorization_id: Mapped[Optional[str]]  # Payment gateway auth ID
    authorization_expires_at: Mapped[Optional[datetime]]  # When auth expires
    capture_attempted_at: Mapped[Optional[datetime]]  # When capture was attempted
```

**Alembic Migration Required:** ✅ YES

#### Code Changes Required

**1. 2C2P Authorization Flow**

```python
# File: /routers/payments/pgw2c2p/services.py

def authorize_payment_2c2p(
    db: Session,
    user: Account,
    amount: float,
    payment_card: PaymentToken,
    type: PaymentType
) -> tuple[str, str]:
    """
    Authorize payment without capturing funds
    Returns: (payment_token, payment_id)
    """
    payload = {
        "description": f"Teleconsultation {type.value.title()} - Authorization",
        "amount": round(amount, 2),
        "customerToken": [payment_card.token],
        "merchantID": PAYMENT_2C2P_MERCHANT_ID,
        "nonceStr": str(uuid.uuid4()),
        "paymentChannel": ["GCARD"],
        "request3DS": "Y",
        "currencyCode": PAYMENT_2C2P_CURRENCY_CODE,
        "paymentType": "A"  # 'A' = Authorization only
    }

    # Call 2C2P API
    # Return payment_token and payment_id
```

**2. 2C2P Capture Flow**

```python
# File: /routers/payments/pgw2c2p/services.py

def capture_payment_2c2p(
    db: Session,
    payment: Payment,
    capture_amount: Optional[float] = None
) -> bool:
    """
    Capture previously authorized payment
    capture_amount: If None, captures full authorized amount
                   If specified, can capture partial amount
    """
    if payment.status != PaymentStatus.PAYMENT_AUTHORIZED:
        raise Exception("Payment not in authorized state")

    amount_to_capture = capture_amount or payment.authorized_amount

    payload = {
        "merchantID": PAYMENT_2C2P_MERCHANT_ID,
        "invoiceNo": payment.payment_id,
        "amount": round(amount_to_capture, 2),
        "processType": "C"  # 'C' = Capture
    }

    # Call 2C2P capture API
    # Update payment status to PAYMENT_CAPTURED
    # Update captured_amount field
```

**3. Update Prepayment Logic**

```python
# File: /repository/payments.py

def create_prepayment_with_authorization(
    db: Session,
    user: Account,
    teleconsults: list[Teleconsult],
    rates: list[PaymentTotal],
    payment_method: PaymentMethod,
    payment_method_id: Optional[str] = None
):
    """
    Create prepayment with authorization (hold funds)
    Only works with 2C2P credit cards
    """

    if payment_method != PaymentMethod.CARD_2C2P:
        raise Exception("Authorization only supported for 2C2P credit cards")

    # Get total amount
    txn_amount = sum([rate.total for rate in rates])

    # Get card token
    card_token = db.query(PaymentToken).filter(
        PaymentToken.account_id == user.id,
        PaymentToken.method == PaymentMethod.CARD_2C2P,
        PaymentToken.id == payment_method_id,
        PaymentToken.deleted == False
    ).first()

    if not card_token:
        raise Exception("Card token not found")

    # Authorize payment (don't capture yet)
    payment_token, auth_id = authorize_payment_2c2p(
        db, user, txn_amount, card_token, PaymentType.PREPAYMENT
    )

    # Create payment record with AUTHORIZED status
    payment = Payment(
        payment_id=auth_id,
        account_id=user.id,
        payment_breakdown=...,
        payment_type=PaymentType.PREPAYMENT,
        payment_method=PaymentMethod.CARD_2C2P,
        payment_provider=PaymentProvider.APP_2C2P,
        payment_amount=txn_amount,
        authorized_amount=txn_amount,
        captured_amount=0.0,
        authorization_id=auth_id,
        status=PaymentStatus.PAYMENT_AUTHORIZED,  # NEW STATUS
        teleconsults=teleconsults
    )

    db.add(payment)
    db.commit()

    return payment
```

**4. Capture After Consultation**

```python
# File: /routers/patient/teleconsult.py or new endpoint

@router.post('/payment/capture')
def capture_teleconsult_payment(
    teleconsult_id: str,
    db: Session = Depends(get_db)
):
    """
    Called after teleconsultation is complete
    Captures the authorized payment + any additional charges
    """

    teleconsult = db.query(Teleconsult).filter(
        Teleconsult.id == teleconsult_id
    ).first()

    if not teleconsult:
        raise HTTPException(404, "Teleconsult not found")

    # Get the authorized prepayment
    prepayment = teleconsult.get_authorized_payment()

    if not prepayment:
        raise HTTPException(400, "No authorized payment found")

    # Calculate total amount to capture
    # = Original consultation fee + medication + delivery
    total_capture_amount = teleconsult.total + teleconsult.balance

    # Check if additional amount exceeds authorization
    if total_capture_amount > prepayment.authorized_amount:
        # Need to authorize additional amount first
        additional_amount = total_capture_amount - prepayment.authorized_amount
        # Implement additional authorization logic here

    # Capture the payment
    success = capture_payment_2c2p(db, prepayment, total_capture_amount)

    if success:
        prepayment.status = PaymentStatus.PAYMENT_CAPTURED
        prepayment.captured_amount = total_capture_amount
        prepayment.capture_attempted_at = datetime.utcnow()
        teleconsult.status = TeleconsultStatus.CHECKED_OUT
        db.commit()

        return {"success": True, "captured_amount": total_capture_amount}

    raise HTTPException(500, "Failed to capture payment")
```

**5. Cancel Authorization on Teleconsult Cancel**

```python
# File: /routers/patient/teleconsult.py

def cancel_teleconsult_authorization(
    db: Session,
    teleconsult: Teleconsult
):
    """
    Release held funds when teleconsult is cancelled
    """

    prepayment = teleconsult.get_authorized_payment()

    if not prepayment:
        return

    if prepayment.status != PaymentStatus.PAYMENT_AUTHORIZED:
        return

    # Call 2C2P void/cancel authorization API
    payload = {
        "merchantID": PAYMENT_2C2P_MERCHANT_ID,
        "invoiceNo": prepayment.payment_id,
        "processType": "V"  # 'V' = Void authorization
    }

    # Call API and update status
    prepayment.status = PaymentStatus.PAYMENT_CANCELED
    db.commit()
```

### Feature 2: Payment Method Restriction by Patient Type

#### Code Changes Required

**1. Update Payment Method Filtering**

```python
# File: /routers/payments/payment_methods.py

@router.get("/", response_model=PaymentMethodsResp)
def get_payment_methods(
    teleconsult_id: Optional[str] = None,  # NEW PARAMETER
    user: Account = Depends(validate_user),
    db: Session = Depends(get_db)
):
    """
    Get available payment methods for user
    Filtered by patient type if teleconsult_id provided
    """

    # Determine patient type
    patient_type = PatientType.PRIVATE_PATIENT  # Default

    if teleconsult_id:
        teleconsult = db.query(Teleconsult).filter(
            Teleconsult.id == teleconsult_id,
            Teleconsult.account_id == user.id
        ).first()

        if teleconsult:
            patient_type = teleconsult.patient_type

    # Get saved payment tokens (credit cards)
    payment_tokens = db.query(PaymentToken).filter(
        PaymentToken.account_id == user.id,
        PaymentToken.deleted == False
    ).order_by(
        PaymentToken.provider,
        PaymentToken.created_at.desc()
    ).all()

    payment_methods = []

    # Add saved cards
    for token in payment_tokens:
        payment_methods.append(
            PaymentMethodDetail(
                id=str(token.id),
                method=token.method,
                icon=get_card_icon(token.details['brand']),
                title=f"{token.details['brand']} •••• {token.details['last4']}",
                is_default=user.default_payment_method == token.method and \
                           user.default_payment_method_id == str(token.id),
                can_remove=True
            )
        )

    # Add PayNow option ONLY for Migrant Workers
    if patient_type == PatientType.MIGRANT_WORKER:
        payment_methods.append(
            PaymentMethodDetail(
                id='paynow_stripe',
                method=PaymentMethod.PAYNOW_STRIPE,
                icon='paynow',
                title='PayNow',
                is_default=user.default_payment_method == PaymentMethod.PAYNOW_STRIPE,
                can_remove=False
            )
        )

    # Add option to add new card (always available)
    payment_methods.append(
        PaymentMethodDetail(
            id='add_card_2c2p',
            method=PaymentMethod.CARD_2C2P,
            icon='credit_card',
            title='Add New Credit/Debit Card',
            is_default=False,
            can_remove=False
        )
    )

    return PaymentMethodsResp(payment_methods=payment_methods)
```

**2. Update Default Payment Method Logic**

```python
# File: /repository/payments.py

def get_default_payment(
    db: Session,
    user: Account,
    patient_type: PatientType
) -> PaymentMethodDetail:
    """
    Get default payment method based on patient type
    """

    # Private patients cannot use PayNow
    if patient_type == PatientType.PRIVATE_PATIENT:
        if user.default_payment_method == PaymentMethod.PAYNOW_STRIPE:
            # Override to use saved card or prompt for new card
            saved_cards = db.query(PaymentToken).filter(
                PaymentToken.account_id == user.id,
                PaymentToken.method == PaymentMethod.CARD_2C2P,
                PaymentToken.deleted == False
            ).order_by(PaymentToken.created_at.desc()).all()

            if saved_cards:
                return PaymentMethodDetail(
                    id=str(saved_cards[0].id),
                    method=PaymentMethod.CARD_2C2P,
                    ...
                )
            else:
                # Force user to add a card
                return PaymentMethodDetail(
                    id='add_card_2c2p',
                    method=PaymentMethod.CARD_2C2P,
                    ...
                )

    # Migrant workers can use any payment method
    return get_user_default_payment(db, user)
```

**3. Update Prepayment Creation Flow**

```python
# File: /routers/patient/teleconsult.py

@router.post('/prepayment/create', response_model=dict)
async def create_prepayment(
    params: CreatePrepaymentReq,
    user: Account = Depends(validate_user),
    db: Session = Depends(get_db)
):
    # ... existing code to determine patient_type ...

    # VALIDATION: Private patients cannot use PayNow
    if patient_type == PatientType.PRIVATE_PATIENT and \
       params.payment_method == PaymentMethod.PAYNOW_STRIPE:
        raise HTTPException(
            status_code=400,
            detail="PayNow is not available for private patients. Please use credit/debit card."
        )

    # ... rest of existing code ...
```

**4. Frontend Changes Required**

```typescript
// File: pinnacle_Admin_frontend-main/src/...

// When loading payment methods, pass teleconsult_id
async function getPaymentMethods(teleconsultId?: string) {
  const params = teleconsultId ? { teleconsult_id: teleconsultId } : {};
  const methods = await api.getPaymentMethods(params);

  // Filter out PayNow for private patients on frontend too
  return methods.payment_methods;
}

// Show appropriate message when PayNow not available
function PaymentMethodSelector({ patientType, teleconsultId }) {
  const methods = usePaymentMethods(teleconsultId);

  return (
    <div>
      {patientType === 'private_patient' && (
        <InfoBanner>
          PayNow is not available for private patient consultations.
          Please use credit/debit card.
        </InfoBanner>
      )}

      {methods.map(method => (
        <PaymentMethodCard key={method.id} method={method} />
      ))}
    </div>
  );
}
```

---

## Database Migration

### Alembic Migration Script

```python
# File: /alembic/versions/XXXXXX_add_payment_authorization.py

"""Add payment authorization and capture fields

Revision ID: XXXXXX
Revises: YYYYYYY
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'XXXXXX'
down_revision = 'YYYYYYY'
branch_labels = None
depends_on = None

def upgrade():
    # Add new payment status values
    op.execute("""
        ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'payment_authorized';
        ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'payment_capture_pending';
        ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'payment_captured';
    """)

    # Add new columns to payment_logs table
    op.add_column('payment_logs',
        sa.Column('authorized_amount', sa.Float(), nullable=True)
    )
    op.add_column('payment_logs',
        sa.Column('captured_amount', sa.Float(), nullable=True)
    )
    op.add_column('payment_logs',
        sa.Column('authorization_id', sa.String(), nullable=True)
    )
    op.add_column('payment_logs',
        sa.Column('authorization_expires_at', sa.DateTime(), nullable=True)
    )
    op.add_column('payment_logs',
        sa.Column('capture_attempted_at', sa.DateTime(), nullable=True)
    )

def downgrade():
    # Remove columns
    op.drop_column('payment_logs', 'capture_attempted_at')
    op.drop_column('payment_logs', 'authorization_expires_at')
    op.drop_column('payment_logs', 'authorization_id')
    op.drop_column('payment_logs', 'captured_amount')
    op.drop_column('payment_logs', 'authorized_amount')

    # Note: Cannot remove enum values in PostgreSQL
```

---

## Implementation Timeline & Effort Estimation

### Phase 1: Payment Authorization & Capture (Core Feature)

**Estimated Time: 5-7 days**

| Task                                     | Effort   | Details                                      |
| ---------------------------------------- | -------- | -------------------------------------------- |
| Database schema changes + migration      | 0.5 days | Add new fields and payment statuses          |
| 2C2P authorization API integration       | 1.5 days | Implement authorize, capture, void endpoints |
| Update prepayment flow for authorization | 1 day    | Modify create_prepayment logic               |
| Implement capture on consult completion  | 1 day    | Auto-capture after doctor checkout           |
| Implement void on cancellation           | 0.5 days | Release funds on cancel                      |
| Combined payment logic (pre + post)      | 1 day    | Combine consultation + medication fees       |
| Testing & debugging                      | 1.5 days | Test various scenarios                       |

### Phase 2: Payment Method Restriction by Patient Type

**Estimated Time: 2-3 days**

| Task                                            | Effort   | Details                            |
| ----------------------------------------------- | -------- | ---------------------------------- |
| Backend: Filter payment methods by patient type | 0.5 days | Update payment_methods endpoint    |
| Backend: Validation in prepayment/postpayment   | 0.5 days | Reject PayNow for private patients |
| Frontend: Update payment method UI              | 1 day    | Show/hide PayNow conditionally     |
| Frontend: Add info messages                     | 0.5 days | Explain restrictions to users      |
| Testing                                         | 0.5 days | Test both patient types            |

### Phase 3: Edge Cases & Error Handling

**Estimated Time: 2-3 days**

| Task                              | Effort   | Details                              |
| --------------------------------- | -------- | ------------------------------------ |
| Handle authorization expiration   | 0.5 days | Auto-void expired authorizations     |
| Handle partial captures           | 0.5 days | Medication cost more than authorized |
| Handle failed captures            | 0.5 days | Retry logic and notifications        |
| Refund flow for captured payments | 0.5 days | Admin refund functionality           |
| Documentation                     | 0.5 days | API docs, flow diagrams              |
| Code review & refinements         | 0.5 days | -                                    |

### Total Estimated Effort: **9-13 days** (1.8 - 2.6 weeks)

**Man-hours:** Approximately 70-100 hours

---

## Technical Risks & Considerations

### 1. **2C2P Authorization Timeout**

- **Risk:** Authorizations typically expire after 7-30 days
- **Impact:** If patient doesn't complete consult, authorization expires
- **Mitigation:**
  - Set up automated job to void expired authorizations
  - Notify patients if authorization near expiry
  - Allow re-authorization if needed

### 2. **Additional Charges Exceed Authorization**

- **Risk:** Medication cost higher than initial authorization
- **Impact:** Cannot capture more than authorized
- **Mitigation:**
  - Option 1: Request additional authorization before capture
  - Option 2: Capture authorized amount + create separate charge for difference
  - Option 3: Set authorization buffer (e.g., authorize 20% more)

### 3. **Payment Failure During Capture**

- **Risk:** Card declined during capture (insufficient funds, card cancelled)
- **Impact:** Consultation completed but payment failed
- **Mitigation:**
  - Implement retry mechanism
  - Send payment failure notification to patient
  - Admin dashboard to track failed captures
  - Allow manual payment collection

### 4. **Dual Payment State Management**

- **Risk:** Some patients use authorization (2C2P), others use immediate charge (PayNow for MW)
- **Impact:** Complex payment flow logic
- **Mitigation:**
  - Clear separation in code between auth and immediate flows
  - Comprehensive testing of both paths
  - Feature flags to enable/disable authorization flow

### 5. **Migrant Worker vs Private Patient Detection**

- **Risk:** Incorrect patient type detection
- **Impact:** Wrong payment methods offered
- **Mitigation:**
  - Patient type determined early in teleconsult creation
  - Stored in teleconsult record
  - Validated at multiple checkpoints

---

## API Changes Summary

### New Endpoints

```
POST /api/teleconsult/payment/authorize
POST /api/teleconsult/payment/capture
POST /api/teleconsult/payment/void
GET  /api/payments/methods?teleconsult_id={id}  (modified)
```

### Modified Endpoints

```
POST /api/teleconsult/prepayment/create
  - Add use_authorization flag
  - Validate payment method by patient type

POST /api/teleconsult/postpayment/create
  - Can be skipped if using combined payment
```

---

## Testing Checklist

### Authorization Flow

- [ ] Authorize payment on prepayment
- [ ] Funds held but not charged
- [ ] Capture after consultation complete
- [ ] Combined charge (consultation + medication + delivery)
- [ ] Void authorization on cancellation
- [ ] Handle authorization expiration
- [ ] Handle capture failure

### Patient Type Restrictions

- [ ] Private patients see only credit card options
- [ ] Migrant workers see PayNow + credit card
- [ ] PayNow selection rejected for private patients
- [ ] Default payment method respects restrictions
- [ ] Frontend UI hides/shows PayNow correctly

### Edge Cases

- [ ] Medication cost exceeds authorization
- [ ] Multiple family members in one session
- [ ] Network failure during capture
- [ ] Card declined during capture
- [ ] User changes payment method mid-flow

---

## Rollout Strategy

### Phase 1: Enable for 2C2P Only

1. Deploy authorization/capture flow
2. Enable ONLY for 2C2P credit cards
3. Keep existing immediate charge flow for PayNow
4. Monitor for 2 weeks

### Phase 2: Restrict PayNow by Patient Type

1. Deploy patient type restrictions
2. Show informational messages to users
3. Monitor customer support tickets
4. Gather user feedback

### Phase 3: Make Authorization Default

1. If successful, make authorization the default for all 2C2P payments
2. Keep immediate charge as fallback

---

## Rollback Plan

If issues arise:

1. **Quick Rollback:** Feature flag to disable authorization flow
2. **Gradual Rollback:** Revert to immediate charge for all new transactions
3. **Database:** Existing payments unaffected; new columns can remain empty

---

## Next Steps

**Client Confirmation Needed:**

1. ✅ Confirm restricting PayNow to Migrant Workers only
2. ✅ Confirm using 2C2P for authorization/capture
3. ⏳ Approve estimated timeline (9-13 days)
4. ⏳ Approve estimated cost based on man-hours
5. ⏳ Confirm authorization expiry handling approach
6. ⏳ Confirm approach for charges exceeding authorization

**Upon Approval:**

1. Create detailed technical specification
2. Create Jira tickets for all tasks
3. Set up development environment
4. Begin Phase 1 implementation
5. Schedule regular progress reviews

---

## Questions for Client

1. **Authorization Buffer:** Should we authorize a buffer amount (e.g., 20% more than consultation fee) to account for potential medication costs?

2. **Expiry Handling:** What should happen if authorization expires before consultation?
   - Auto-void and notify patient to re-authorize?
   - Set maximum consultation scheduling window?

3. **Failed Captures:** If payment capture fails after consultation:
   - Send email invoice with payment link?
   - Block future bookings until paid?
   - What's the escalation process?

4. **Private Patient Definition:** How is a private patient determined?
   - Based on corporate code absence?
   - Explicit flag in user profile?
   - Per-consultation selection?

5. **Migration Plan:** For existing queued teleconsults:
   - Keep existing immediate charge flow?
   - Or migrate to authorization flow?

---

**Document Version:** 1.0  
**Status:** Pending Client Approval  
**Contact:** Development Team
