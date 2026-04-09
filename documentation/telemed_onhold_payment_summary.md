# Telemed On-Hold Payment - Executive Summary

## Date: April 8, 2026

---

## ✅ What You Requested

### 1. Hold Payment & Charge After Consultation

- **Problem:** Currently pre-payment means refunds when patients cancel
- **Solution:** Hold funds on card → Only charge after doctor consultation complete
- **Bonus:** Combine all charges (consultation + medication + delivery) into ONE payment

### 2. Restrict PayNow by Patient Type

- **Migrant Workers:** Can use PayNow OR Credit Card
- **Private Patients:** Credit Card ONLY (no PayNow option)

---

## ✅ Our Analysis - Key Findings

### Payment Gateway Support

| Gateway              | Hold & Charge Support | Current Usage         |
| -------------------- | --------------------- | --------------------- |
| **Stripe PayNow**    | ❌ NOT SUPPORTED      | Active (All patients) |
| **2C2P Credit Card** | ✅ FULLY SUPPORTED    | Active (Test users)   |

### Why PayNow Can't Do Hold & Charge

- PayNow = Instant bank transfer (like a wire)
- Money moves immediately from bank account
- No way to "hold" bank transfers
- This is a limitation of the payment method itself, not the gateway

### Why 2C2P Can Do Hold & Charge

- Credit cards support "Authorization & Capture"
- Authorization = Hold funds on card (no charge yet)
- Capture = Actually charge the held funds
- 2C2P API already supports this

---

## ✅ Recommended Solution

### Approach

1. **Enable hold & charge for 2C2P credit cards**
2. **Keep immediate charge for PayNow** (no other option)
3. **Restrict PayNow to Migrant Workers only**

### Payment Flow by Patient Type

```
MIGRANT WORKER:
├─ Option 1: PayNow → Immediate charge (as today)
└─ Option 2: Credit Card → Hold → Charge after consult ✨NEW

PRIVATE PATIENT:
└─ Credit Card ONLY → Hold → Charge after consult ✨NEW
    (No PayNow option shown)
```

---

## ✅ Implementation Details

### What Changes

**Backend (Python API):**

- Add authorization & capture payment functions
- Add patient type validation for payment methods
- Combine consultation + medication + delivery into one charge
- Auto-release funds if patient cancels

**Frontend (React Mobile App):**

- Show/hide PayNow based on patient type
- Display "Payment held, will be charged after consultation" message
- Update payment confirmation screens

**Database:**

- Add fields to track authorization status
- Store authorization expiry dates
- Track captured amounts

### What Stays the Same

- Existing payment methods (Stripe, 2C2P)
- Existing refund processes (for immediate charges)
- No changes to PayNow flow itself

---

## ✅ Effort & Timeline

| Phase       | Tasks                       | Duration | Dependencies  |
| ----------- | --------------------------- | -------- | ------------- |
| **Phase 1** | Database + 2C2P Integration | 5-7 days | 2C2P API docs |
| **Phase 2** | Patient Type Restrictions   | 2-3 days | Phase 1       |
| **Phase 3** | Testing + Edge Cases        | 2-3 days | Phase 2       |

**Total:** 9-13 working days (~2-2.5 weeks)

**Man-hours:** 70-100 hours

---

## ✅ Important Considerations

### 1. Authorization Expires

- Credit card authorizations typically expire in 7-30 days
- If patient doesn't complete consultation in time, authorization released
- **Question:** Should we auto-notify patients and ask them to re-authorize?

### 2. Medication Cost Exceeds Authorization

- Example: Authorized $50 for consultation, medication costs $40 extra
- Can we authorize MORE than consultation fee upfront?
- **Question:** Should we add 20-30% buffer when authorizing?

### 3. What If Capture Fails?

- Card declined when trying to charge (after consultation complete)
- **Question:** Should we:
  - Send payment link via email?
  - Block future bookings until paid?
  - Contact patient manually?

### 4. How to Identify Private Patients?

- **Question:** Is it based on:
  - No corporate code = Private patient?
  - Explicit flag in user profile?
  - Selected during booking?

---

## ✅ Costs & Benefits

### Benefits

✅ No more refunds for pre-cancelled teleconsults  
✅ Better user experience (charge only if service delivered)  
✅ Single payment instead of multiple charges  
✅ Reduced operational overhead  
✅ Clear payment method based on patient type

### Costs

💰 Development: 70-100 man-hours  
💰 Testing: Additional QA effort  
💰 2C2P transaction fees (unchanged)

### Risks

⚠️ Authorization can expire if consultation delayed  
⚠️ Failed capture after consultation (need recovery process)  
⚠️ More complex payment flow logic

---

## ✅ What We Need From You

### Decision Points

1. [ ] **Approve** restricting PayNow to Migrant Workers only
2. [ ] **Approve** timeline (9-13 days) and effort estimate
3. [ ] **Decide** on authorization buffer amount (e.g., authorize 20% extra for medication)
4. [ ] **Decide** on failed capture recovery process
5. [ ] **Clarify** how to identify private vs migrant worker patients

### Questions to Answer

1. What happens if authorization expires before consultation?
2. How much buffer should we add to authorization amount?
3. What's the process if payment capture fails after consultation?
4. How do we determine if a patient is "private" vs "migrant worker"?
5. Any existing teleconsult bookings - keep old flow or migrate?

---

## ✅ Next Steps

### Once Approved

1. ✅ Create detailed technical specification
2. ✅ Create development tasks in project management
3. ✅ Coordinate with 2C2P for API access verification
4. ✅ Set up staging environment for testing
5. ✅ Begin Phase 1 development
6. ✅ Weekly progress updates

### Rollout Plan

1. **Week 1-2:** Development + Internal testing
2. **Week 3:** UAT (User Acceptance Testing) with test patients
3. **Week 4:** Gradual rollout (10% of users → 50% → 100%)
4. **Week 5:** Monitor + Optimize

---

## ✅ Recommendation

**We recommend proceeding with this implementation because:**

1. ✅ **Technically Feasible** - 2C2P supports everything needed
2. ✅ **Solves Core Problem** - No more refund overhead for cancellations
3. ✅ **Better UX** - Single payment instead of multiple charges
4. ✅ **Clear Scope** - Well-defined requirements, manageable timeline
5. ✅ **Low Risk** - Can rollback to immediate charge if needed

**However, please note:**

- PayNow cannot support hold & charge (fundamental limitation)
- Private patients will be required to use credit/debit cards
- Need decisions on authorization buffer and failed capture handling

---

## 📞 Contact

For questions or to discuss this proposal:

- **Development Team:** [Contact details]
- **Project Manager:** [Contact details]
- **Technical Lead:** [Contact details]

---

**Document Version:** 1.0  
**Status:** Awaiting Client Approval  
**Date:** April 8, 2026
