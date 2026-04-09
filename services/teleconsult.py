from collections import OrderedDict
import logging
from datetime import datetime
from typing import Optional, List
from cachetools import TTLCache, LRUCache, cached
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import SessionLocal, Account, AccountYuuLink, CorporateUser, CorporateCode, DynamicPricing, SGiMedInventory
from models.pinnacle import PublicHoliday
from services.user import user_is_pcp
from config import SGIMED_GST_RATE
from utils import  sg_datetime

class PaymentBreakdown(BaseModel):
    id: str | None = None
    code: str | None = None
    title: str
    amount: float

class PaymentTotal(BaseModel):
    breakdown: list[PaymentBreakdown]
    subtotal: float = 0.0
    total: float = 0.0

class Membership(BaseModel):
    id: str
    code: str
    inventory_ids: List[str]

class DynamicRate(BaseModel):
    corporate_codes: dict[str, List[str]]
    sgimed_consultation_inventory_ids: List[str]

def fetch_prepayment_rate(db: Session, nric: str, user_code: Optional[str] = None):
    """
    Calculate prepayment rate based on priority system with timing overrides
    
    1. Get timing row from payment_dynamic_rates based on current datetime
    2. Set base sgimed_consultation_inventory_ids from timing row
    3. Detect corporate memberships for the account
    4. Select highest priority corporate code if memberships exist
    5. Check for timing-based corporate code overrides in JSON field
    6. Use override inventory IDs or fallback to corporate code default IDs
    7. Convert inventory IDs to breakdown items with price lookup
    8. Group similar line items and compute subtotal (without GST)
    9. Return PCP status, corporate code, and payment breakdown
    """
    account = db.query(Account).filter(Account.nric == nric).first()
    if not account:
        raise Exception("Account not found")

    current_datetime = sg_datetime.now()

    # Step 1: Get timing row from payment_dynamic_rates based on current datetime
    timing_row = get_dynamic_pricing_row(current_datetime.replace(second=0, microsecond=0))
    membership = get_corporate_membership(str(account.id), user_code)
    inventory_ids = timing_row.sgimed_consultation_inventory_ids

    if membership:
        if membership.id in timing_row.corporate_codes:
            inventory_ids = timing_row.corporate_codes[membership.id]
        else:
            inventory_ids = membership.inventory_ids
    
    subtotal = get_payment_breakdown(tuple(inventory_ids))

    is_pcp = bool(membership and membership.code == 'PCP')
    return_code = membership.code if membership else None
    return is_pcp, return_code, subtotal


@cached(cache=LRUCache(maxsize=32))
def get_dynamic_pricing_row(current_datetime: datetime) -> DynamicRate:
    """
    Get current timing row from payment_dynamic_rates based on datetime
    
    1. Determine rate_key priority (PH > specific date > SAT/SUN > MON-FRI)
    2. Check for public holidays and set rate_key to 'PH'
    3. Handle weekend rates (SAT/SUN) and weekday rates (MON-FRI)
    4. Get all timing rows for the determined rate_key
    5. Find timing row that matches current time range (e.g., 0800-1800)
    6. Return matching timing row or fallback to first available row
    """
    current_day = ['MON','TUE','WED','THU','FRI','SAT','SUN'][current_datetime.weekday()]
    current_time = current_datetime.time().hour * 100 + current_datetime.time().minute

    # Step 1: Determine rate_key priority MON-FRI, SAT, SUN, PH
    rate_key = 'MON-FRI' if current_day in ['MON','TUE','WED','THU','FRI'] else current_day
    
    with SessionLocal() as db:
        holiday = db.query(PublicHoliday.date).filter(PublicHoliday.date == current_datetime.date()).first()
        if holiday:
            rate_key = 'PH'

        # Step 2: Get all timing rows for the determined rate_key
        timing_rows = db.query(DynamicPricing).filter(DynamicPricing.date == rate_key).all()
        
        # Step 3: Find the matching timing range
        for timing_row in timing_rows:
            # Parse timing range (e.g., "0800-1800")
            if timing_row.timing and '-' in timing_row.timing:
                time_parts = timing_row.timing.split('-')
                if len(time_parts) == 2:
                    start_time = int(time_parts[0])
                    end_time = int(time_parts[1])
                    
                    # Check if current time falls within this range
                    if start_time <= current_time < end_time:
                        return DynamicRate(
                            corporate_codes=timing_row.corporate_codes,
                            sgimed_consultation_inventory_ids=timing_row.sgimed_consultation_inventory_ids
                        )

        # Step 4: Fallback - return first timing row for the rate_key if no range matches
        if timing_rows:
            logging.error(f"No timing row found for datetime {current_datetime.strftime('%Y-%m-%d %H:%M')}. "
                        f"Expected timing rows for rate_key '{rate_key}' but none exist in payment_dynamic_rates table. "
                        f"Using first timing row: {timing_rows[0].date} {timing_rows[0].timing}")
            return DynamicRate(
                corporate_codes=timing_rows[0].corporate_codes,
                sgimed_consultation_inventory_ids=timing_rows[0].sgimed_consultation_inventory_ids
            )

    # No timing rows found for any rate key
    raise ValueError(
        f"No dynamic pricing configuration found for datetime {current_datetime.strftime('%Y-%m-%d %H:%M')}. "
        f"Expected timing rows for rate_key '{rate_key}' but none exist in payment_dynamic_rates table. "
        f"Please ensure dynamic pricing is properly configured for this time period."
    )

# @cached(cache=TTLCache(maxsize=1024, ttl=60))
def get_corporate_membership(account_id: str, user_code: Optional[str] = None) -> Optional[Membership]:
    """
    Detect all corporate memberships for a user
    Returns Membership object with highest priority code
    
    1. Check PCP membership from pinnacle_sa_records table
    2. Check Yuu membership from patient_account_yuu_links (primary user only)
    3. Get all corporate memberships from corporate_users table
    4. Validate user input codes (INS, etc.) with access restrictions
    5. Return highest priority membership or None
    """
    memberships = []
    
    with SessionLocal() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            logging.error(f"Account with ID '{account_id}' not found in patient_accounts table")
            return None
        
        # Check PCP membership
        if user_is_pcp(db, account.nric):
            memberships.append('PCP')
        
        # Check Yuu membership (primary user only)
        if account.mobile_number:  # Primary user, not a dependent
            yuu_link = db.query(AccountYuuLink).filter(
                AccountYuuLink.account_id == account.id,
                AccountYuuLink.deleted == False
            ).first()
            if yuu_link:
                memberships.append('YUU')
        
        # Check Corporate User membership
        corporate_memberships = db.query(CorporateUser.code).filter(
            CorporateUser.nric == account.nric
        ).all()
        memberships += [r[0] for r in corporate_memberships]
        
        # Check for user_code (user input codes like INS, etc.)
        if user_code:
            # Check if user_code exists in payment_corporate_codes and is valid for user input
            corporate_code_record = db.query(CorporateCode).filter(
                CorporateCode.code == user_code.upper(),
                CorporateCode.deleted == False,
                CorporateCode.allow_user_input == True
            ).first()
            
            if corporate_code_record:
                # Check if this corporate code is restricted to specific NRICs
                has_restricted_user = db.query(CorporateUser.code).filter(
                    CorporateUser.code == user_code.upper()
                ).first()
                
                if has_restricted_user:
                    # Code is restricted - check if user NRIC is in the allowed list
                    user_authorized = db.query(CorporateUser).filter(
                        CorporateUser.code == user_code.upper(),
                        CorporateUser.nric == account.nric
                    ).first()
                    
                    if user_authorized:
                        # User is authorized for this restricted code
                        memberships.append(user_code.upper())
                    # If not authorized, code is not added to memberships
                else:
                    # No restrictions - code has open access, add to memberships
                    memberships.append(user_code.upper())

        if memberships:
            # Get highest priority corporate code
            corporate_code = db.query(CorporateCode).filter(
                CorporateCode.deleted == False,
                CorporateCode.code.in_(memberships)
            ).order_by(CorporateCode.priority_index).first()
            
            if not corporate_code:
                logging.error(
                    f"No active corporate code found for memberships {memberships}. "
                    f"Corporate codes may be deleted or missing from payment_corporate_codes table."
                )
                return None

            return Membership(
                id=str(corporate_code.id), 
                code=corporate_code.code, 
                inventory_ids=corporate_code.sgimed_consultation_inventory_ids
            )

    return None

@cached(cache=TTLCache(maxsize=1024, ttl=60))
def get_payment_breakdown(inventory_ids: tuple[str, ...]) -> PaymentTotal:
    """
    Get payment breakdown from SGiMed inventory IDs
    
    1. Query SGiMed inventory items by IDs
    2. Maintain order based on input inventory_ids
    3. Create PaymentBreakdown objects with price lookup
    4. Calculate subtotal and return PaymentTotal
    """
    with SessionLocal() as db:
        items = db.query(SGiMedInventory).filter(
            SGiMedInventory.id.in_(inventory_ids)
        ).all()

        # Maintain order based on input inventory_ids
        id_order = {inv_id: index for index, inv_id in enumerate(inventory_ids)}
        items.sort(key=lambda item: id_order.get(item.id, float('inf')))

        breakdown = []
        for item in items:
            if item.price is None:
                logging.error(f"SGiMed inventory item '{item.id}' ({item.name}) has no price configured")

            breakdown.append(PaymentBreakdown(
                id=item.id,
                code=item.code,
                title=item.name,
                amount=float(item.price) if item.price else 0.0
            ))

        subtotal = sum([row.amount for row in breakdown])
        return PaymentTotal(
            breakdown=breakdown,
            subtotal=round(subtotal, 2)
        )

def combine_breakdown_with_gst(subtotals: list[PaymentTotal]) -> PaymentTotal:
    """
    Add GST to breakdown and calculate total
    Note: GST is calculated in the frontend/external call, not in get_prepayment_rate
    
    1. Group similar line items together using group_breakdown_items()
    2. Get GST rate percentage from config and convert to decimal
    3. Calculate GST amount based on subtotal
    4. Add GST line item to grouped breakdown
    5. Calculate final total (subtotal + GST) and return PaymentTotal
    """
    try:
        # Group similar line items together
        breakdown_list = [item for sublist in subtotals for item in sublist.breakdown if 'GST' not in item.title]
        gst_list = [item for sublist in subtotals for item in sublist.breakdown if 'GST' in item.title]

        grouped_breakdown = group_breakdown_items(breakdown_list)
        subtotal = sum([item.amount for item in grouped_breakdown])

        # If GST is already in the breakdown, use it
        if gst_list:
            gst_amount = sum([item.amount for item in gst_list])
            grouped_breakdown.append(PaymentBreakdown(
                title=gst_list[0].title, 
                amount=gst_amount
            ))
        # Calculate GST from config
        else:
            gst_amount = round(subtotal * SGIMED_GST_RATE, 2)       
            grouped_breakdown.append(PaymentBreakdown(
                title=f"GST ({SGIMED_GST_RATE * 100:.0f}%)", 
                amount=gst_amount
            ))
        
        total = round(subtotal + gst_amount, 2)
        return PaymentTotal(breakdown=grouped_breakdown, subtotal=subtotal, total=total)
    except Exception as e:
        raise ValueError(f"Failed to calculate GST breakdown: {str(e)}")

def group_breakdown_items(breakdown: List[PaymentBreakdown]) -> List[PaymentBreakdown]:
    """
    Group similar line items together with title like '<Title> (x2)' while maintaining order
    
    1. Create ordered dictionary to track item counts, amounts, and first occurrence
    2. Iterate through breakdown items and group by title
    3. Sum amounts for identical items and track count
    4. Generate display titles with count notation (x2, x3, etc.)
    5. Return new breakdown list with grouped items in original order
    """
    if not breakdown:
        logging.error("Empty 'breakdown' list passed to group_breakdown_items.")
        return []
    
    grouped = OrderedDict()
    for item in breakdown:
        if item.title in grouped:
            grouped[item.title]['count'] += 1
            grouped[item.title]['amount'] += item.amount
        else:
            grouped[item.title] = {
                'count': 1, 
                'id': item.id,
                'code': item.code,
                'amount': item.amount,
            }

    result = []
    for title, data in grouped.items():
        display_title = f"{title} (x{data['count']})" if data['count'] > 1 else title
        result.append(PaymentBreakdown(
            id=data['id'], 
            code=data['code'], 
            title=display_title, 
            amount=round(data['amount'], 2)
        ))
    
    return result
