# Payment Flow Diagrams - Current vs Proposed

## Current Flow (Immediate Charge - All Patients)

```
┌─────────────────────────────────────────────────────────────┐
│ CURRENT: Pre-Payment System (All Patients)                  │
└─────────────────────────────────────────────────────────────┘

STEP 1: Book Teleconsult
  Patient → Select slot → Choose payment method
            ↓
  Both PayNow & Credit Card available to ALL patients
            ↓
  Payment charged IMMEDIATELY ($50)
            ✅ Charged

STEP 2: Join Queue
  Patient enters waiting queue
            ↓
  Status: Waiting for doctor

STEP 3A: Patient Cancels (PROBLEM!)
  Patient → Cancel teleconsult
            ↓
  ❌ PROBLEM: Need to refund $50
            ↓
  Manual refund process
  Operational overhead

STEP 3B: Consultation Happens
  Patient → Doctor consultation
            ↓
  Prescription issued
            ↓
  Medication cost: $30
  Delivery cost: $5
            ↓
  ❌ PROBLEM: Patient charged AGAIN ($35)
            ✅ Second charge

Total Payments: 2 separate transactions ($50 + $35 = $85)
Refund Risk: High (if patient cancels)
```

---

## Proposed Flow - Migrant Workers (Two Options)

```
┌─────────────────────────────────────────────────────────────┐
│ MIGRANT WORKER: Option 1 - PayNow (Unchanged)               │
└─────────────────────────────────────────────────────────────┘

STEP 1: Book with PayNow
  Patient → Select PayNow
            ↓
  Payment charged IMMEDIATELY ($50)
            ✅ Charged (instant bank transfer)

STEP 2: Medication (if needed)
  Medication cost: $30
  Delivery cost: $5
            ↓
  Second PayNow payment ($35)
            ✅ Charged again

Total Payments: 2 transactions ($50 + $35 = $85)
Note: PayNow cannot hold funds (bank transfer limitation)


┌─────────────────────────────────────────────────────────────┐
│ MIGRANT WORKER: Option 2 - Credit Card (NEW!)               │
└─────────────────────────────────────────────────────────────┘

STEP 1: Book with Credit Card
  Patient → Select credit card
            ↓
  HOLD $50 on card
            💳 Authorized (NOT charged yet)

STEP 2: Consultation
  Patient → Doctor consultation
            ↓
  Prescription issued
            ↓
  Calculate total:
    Consultation: $50
    Medication: $30
    Delivery: $5
    TOTAL: $85

STEP 3: Single Combined Charge
            ↓
  CHARGE $85 (all at once)
            ✅ Charged once

Total Payments: 1 transaction ($85)
If cancelled: Authorization released (no refund needed)
```

---

## Proposed Flow - Private Patients (Credit Card Only)

```
┌─────────────────────────────────────────────────────────────┐
│ PRIVATE PATIENT: Credit Card ONLY (NEW!)                    │
└─────────────────────────────────────────────────────────────┘

STEP 1: Payment Method Selection
  Patient → Opens payment methods
            ↓
  ❌ PayNow NOT shown
  ✅ Credit Card options only
            ↓
  Info message: "Credit card required for private consultations"

STEP 2: Book with Credit Card
  Patient → Select credit card
            ↓
  HOLD $50 on card (or $60 with buffer)
            💳 Authorized (NOT charged yet)
            ↓
  Message: "Payment authorized. You'll be charged after consultation."

STEP 3: Patient Can Cancel
  Patient → Cancel teleconsult
            ↓
  RELEASE authorization
            ✅ No charge, no refund needed!

STEP 3: Or Consultation Happens
  Patient → Doctor consultation
            ↓
  Prescription issued
            ↓
  Calculate total:
    Consultation: $50
    Medication: $30
    Delivery: $5
    TOTAL: $85

STEP 4: Single Combined Charge
            ↓
  CHARGE $85 from authorized card
            ✅ Charged once
            ↓
  Receipt: "Teleconsult + Medication + Delivery: $85"

Total Payments: 1 transaction ($85)
If cancelled before consult: No charge, no refund
Benefits: Better UX, less operational overhead
```

---

## Payment Method Availability Matrix

```
┌──────────────────┬─────────────┬──────────────┬───────────────┐
│ Patient Type     │ PayNow      │ Credit Card  │ Default       │
├──────────────────┼─────────────┼──────────────┼───────────────┤
│ Migrant Worker   │ ✅ Available │ ✅ Available  │ User choice   │
│                  │ (Immediate) │ (Hold+Charge)│               │
├──────────────────┼─────────────┼──────────────┼───────────────┤
│ Private Patient  │ ❌ Hidden    │ ✅ Required   │ Credit card   │
│                  │             │ (Hold+Charge)│               │
└──────────────────┴─────────────┴──────────────┴───────────────┘
```

---

## Authorization & Capture Timeline

```
TIME: t=0 (Booking)
  ┌─────────────────────────────────────────┐
  │ Patient books teleconsult               │
  │ Credit card selected                    │
  │                                         │
  │ Action: AUTHORIZE $60                   │
  │ (Consultation $50 + Buffer $10)         │
  │                                         │
  │ Result: Funds HELD on card              │
  │         NOT charged yet                 │
  │         Available credit reduced by $60 │
  └─────────────────────────────────────────┘
                    ↓

TIME: t=30min (Queue waiting)
  ┌─────────────────────────────────────────┐
  │ Patient in queue                        │
  │ Authorization status: ACTIVE            │
  │                                         │
  │ If patient cancels here:                │
  │   → VOID authorization                  │
  │   → Funds released immediately          │
  │   → No refund needed                    │
  └─────────────────────────────────────────┘
                    ↓

TIME: t=1hr (Consultation)
  ┌─────────────────────────────────────────┐
  │ Doctor consultation happening           │
  │ Authorization status: ACTIVE            │
  │ Prescription written                    │
  │                                         │
  │ Medication cost calculated: $30         │
  │ Delivery cost: $5                       │
  │ Total needed: $85                       │
  └─────────────────────────────────────────┘
                    ↓

TIME: t=1hr 30min (Checkout)
  ┌─────────────────────────────────────────┐
  │ Doctor marks checkout                   │
  │                                         │
  │ Action: CAPTURE $85                     │
  │ (More than authorized $60)              │
  │                                         │
  │ Option A: Authorize extra $25 first     │
  │ Option B: Capture $60 + charge $25      │
  │ Option C: Fail & notify patient         │
  │                                         │
  │ Result: Card charged $85                │
  │         Teleconsult completed           │
  └─────────────────────────────────────────┘
                    ↓

TIME: t=2hr (Complete)
  ┌─────────────────────────────────────────┐
  │ Payment captured successfully           │
  │ Patient receives receipt                │
  │ Medication prepared for delivery        │
  │                                         │
  │ Status: CHECKED_OUT                     │
  └─────────────────────────────────────────┘
```

---

## Error Scenarios & Handling

### Scenario 1: Authorization Expires (No Consultation)

```
t=0: Authorize $50
t=7 days: Authorization expires (patient never joined queue)
  ↓
System: Auto-void authorization
        Send notification to patient
        Update teleconsult status: EXPIRED
Result: No charge, no refund needed
```

### Scenario 2: Capture Fails (Insufficient Funds)

```
t=0: Authorize $50
t=1hr: Consultation complete, try to capture $85
  ↓
Bank: ❌ Declined (insufficient funds)
  ↓
System: Mark payment as CAPTURE_FAILED
        Send payment link to patient
        Doctor notified
        Medication on hold until payment
Result: Patient must pay manually
```

### Scenario 3: Additional Charges Exceed Authorization

```
t=0: Authorize $50
t=1hr: Consultation complete, total is $120 (expensive medication)
  ↓
Option A: Request additional authorization for $70
          Then capture full $120

Option B: Capture authorized $50
          Create separate charge for $70

Option C: Authorize 50% buffer upfront ($75)
          Capture up to $75 automatically
          If exceeds, use Option A or B
```

---

## User Interface Changes

### Payment Method Selection - BEFORE

```
┌────────────────────────────────────────┐
│ Select Payment Method                  │
├────────────────────────────────────────┤
│                                        │
│ ◉ PayNow                               │
│   Quick bank transfer                  │
│                                        │
│ ○ Visa •••• 1234                       │
│   Credit card                          │
│                                        │
│ ○ Add new card                         │
│                                        │
└────────────────────────────────────────┘

Available to: ALL patients
```

### Payment Method Selection - AFTER (Migrant Worker)

```
┌────────────────────────────────────────┐
│ Select Payment Method                  │
├────────────────────────────────────────┤
│                                        │
│ ◉ PayNow                               │
│   Instant payment                      │
│   You will be charged immediately      │
│                                        │
│ ○ Visa •••• 1234                       │
│   Hold payment                         │
│   Charged after consultation          │
│                                        │
│ ○ Add new card                         │
│                                        │
└────────────────────────────────────────┘

Available to: Migrant Workers
Shows clear difference in payment timing
```

### Payment Method Selection - AFTER (Private Patient)

```
┌────────────────────────────────────────┐
│ Select Payment Method                  │
├────────────────────────────────────────┤
│                                        │
│ ℹ️  PayNow is not available for        │
│    private patient consultations.      │
│    Please use credit/debit card.       │
│                                        │
│ ◉ Visa •••• 1234                       │
│   Hold payment                         │
│   Charged after consultation          │
│                                        │
│ ○ Add new card                         │
│                                        │
└────────────────────────────────────────┘

Available to: Private Patients
PayNow option completely hidden
```

### Confirmation Screen - Authorization

```
┌────────────────────────────────────────┐
│ ✅ Payment Authorized                   │
├────────────────────────────────────────┤
│                                        │
│ A hold of $50.00 has been placed       │
│ on your card ending in 1234.           │
│                                        │
│ You will be charged after your         │
│ consultation is complete.              │
│                                        │
│ Final amount may include medication    │
│ and delivery charges.                  │
│                                        │
│ If you cancel, the hold will be        │
│ released and you won't be charged.     │
│                                        │
│ [Continue to Queue]                    │
└────────────────────────────────────────┘
```

---

## Database Schema Changes

### Payment Table - NEW FIELDS

```sql
ALTER TABLE payment_logs ADD COLUMN authorized_amount FLOAT;
ALTER TABLE payment_logs ADD COLUMN captured_amount FLOAT;
ALTER TABLE payment_logs ADD COLUMN authorization_id VARCHAR;
ALTER TABLE payment_logs ADD COLUMN authorization_expires_at TIMESTAMP;
ALTER TABLE payment_logs ADD COLUMN capture_attempted_at TIMESTAMP;

-- Example record for authorized payment
{
  "payment_id": "auth_ABC123",
  "account_id": "user_789",
  "payment_method": "card_2c2p",
  "payment_amount": 85.00,
  "authorized_amount": 60.00,      -- NEW
  "captured_amount": 85.00,        -- NEW (after capture)
  "authorization_id": "2c2p_xyz",  -- NEW
  "authorization_expires_at": "2026-04-15T10:00:00Z",  -- NEW
  "capture_attempted_at": "2026-04-08T11:30:00Z",      -- NEW
  "status": "payment_captured",
  "created_at": "2026-04-08T10:00:00Z",
  "updated_at": "2026-04-08T11:30:00Z"
}
```

---

## Summary Comparison

| Feature                  | Current      | Proposed (MW PayNow) | Proposed (MW Card) | Proposed (PP Card)   |
| ------------------------ | ------------ | -------------------- | ------------------ | -------------------- |
| **Payment Timing**       | Immediate    | Immediate            | After consult      | After consult        |
| **Refund on Cancel**     | Yes (manual) | Yes (manual)         | No (auto-release)  | No (auto-release)    |
| **Number of Charges**    | 2 separate   | 2 separate           | 1 combined         | 1 combined           |
| **PayNow Available**     | Yes          | Yes                  | Yes                | ❌ No                |
| **Credit Card Required** | No           | No                   | No                 | ✅ Yes               |
| **Authorization Hold**   | No           | No                   | ✅ Yes             | ✅ Yes               |
| **Best For**             | -            | Quick payments       | Flexible option    | All private patients |

---

**Document Version:** 1.0  
**Date:** April 8, 2026
