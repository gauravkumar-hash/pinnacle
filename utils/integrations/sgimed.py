from datetime import date, datetime
import logging
from typing import Callable, Optional
from pydantic import BaseModel, field_validator
import requests
from models import Account, Payment, Teleconsult
from models.model_enums import PhoneCountryCode, SGiMedGender, SGiMedICType, SGiMedLanguage, SGiMedNationality, WalkinQueueStatus
from models.patient import FamilyNok
from models.payments import PaymentMethod
from models.pinnacle import Branch
from utils import sg_datetime
import json
from config import SGIMED_API_URL, SGIMED_API_KEY, SGIMED_DEFAULT_BRANCH_ID
from tenacity import retry, stop_after_attempt, wait_random, retry_if_exception_type
from sqlalchemy.orm import Session
import jwt

class Pager(BaseModel):
    p: int
    n: int
    pages: int
    rows: int

class SGiMedId(BaseModel):
    id: str

class SGiMedIdName(BaseModel):
    id: str
    name: str

class InvoiceDetails(BaseModel):
    invoice_id: str
    visit_id: str
    invoice_html: str
    mc_html: Optional[str] = None
    items: list
    prescriptions: list
    invoice_dict: dict

def fetch_invoice_details(invoice_id: str) -> Optional[InvoiceDetails]:
    invoice_dict = get_invoice(invoice_id)
    if not invoice_dict:
        logging.error(f'SGiMed Invoice Webhook: Failed to get invoice from SGiMed. Invoice ID: {invoice_id}')
        return None

    visit_id = invoice_dict['visit']['id']
    # Get details from SGiMed once Invoice is cleared
    # Update Invoice and MC IDs instead of HTML
    invoice_html = invoice_id
    mc_html = get_mc_order_item_id(visit_id)
    items = get_items(visit_id)
    prescriptions = get_prescription(visit_id)

    # This converts the SGiMed data to a format that can be saved in Supabase
    def sgimed_to_dict(item):
        route = item['route'] if item['route'] else ""
        dosage = item['dosage'] if item['dosage'] else ""
        instruction_uom = item['instruction_uom'] if item['instruction_uom'] else ""
        frequency = item['frequency'] if item['frequency'] else ""
        duration = item['duration'] if item['duration'] else ""
        duration_unit = item['duration_unit'] if item['duration_unit'] else ""

        return {
            "item_name": item['item_name'] if 'item_name' in item else '',
            "item_type": item['item_type'] if 'item_type' in item else '',
            "instructions": f"{route} {dosage} {instruction_uom} {frequency} for {duration} {duration_unit}",
            "precautions": "\n".join([item[precaution_str] for precaution_str in ["precaution1", "precaution2", "precaution3"] if item[precaution_str]]).strip()
        }
    items = list(map(sgimed_to_dict, items))    
    prescriptions = list(map(sgimed_to_dict, prescriptions))

    return InvoiceDetails(
            invoice_id=invoice_id,
            visit_id=visit_id,
            invoice_html=invoice_html,
            mc_html=mc_html,
            items=items,
            prescriptions=prescriptions,
            invoice_dict=invoice_dict,
        )

class EmployeeInfo(BaseModel):
    employee_id: str
    employee_company: str

def upsert_patient_nok(user: Account):
    nok = user.parent_nok
    if not nok:
        logging.error("Inserting NOK record but no parent account found. User ID: {user.id}")
        return
    # If user already has sgimed_nok_id, then no need to insert
    if nok.sgimed_nok_id:
        return

    parent_account = nok.account
    
    user_data = {
        "name": parent_account.name,
        "mobile": parent_account.mobile_code.value + parent_account.mobile_number,
        "relation": nok.relation.value,
        "ref_patient_id": parent_account.sgimed_patient_id
    }
    try:
        resp = post(f'/patient/{user.sgimed_patient_id}/nok', user_data)
        nok.sgimed_nok_id = resp['id']
    except Exception as e:
        logging.error(f"Failed to insert NOK record for user on SGiMed: {user.id}. Error: {str(e)}")

def delete_patient_nok(nok: FamilyNok):
    # BUG: Only SGiMed Family Member NOK is removed from SGiMed and not the Parent Account
    try:
        resp = delete(f'/patient/{nok.nok_account.sgimed_patient_id}/nok/{nok.sgimed_nok_id}')
    except Exception as e:
        logging.error(f"Failed to delete NOK record id: {nok.id}, sgimed_patient_id: {nok.nok_account.sgimed_patient_id}, nok_id: {nok.sgimed_nok_id}. Error: {str(e)}")

def user_exists_in_sgimed(sgimed_patient_id: str) -> bool:
    if not sgimed_patient_id:
        return False
    try:
        get_patient_data(sgimed_patient_id)
        return True
    except Exception as e:
        if '404' in str(e):
            return False
        raise Exception(str(e))

def retrieve_sgimed_patient_id(db: Session, user: Account):
    '''
    Updates user record sgimed_patient_id, sgimed_diff, sgimed_auth_code
    '''
    # If user already has sgimed_patient_id, then no need to retrieve
    if user.sgimed_patient_id:
        return None
    # If NRIC doesn't exist in SGiMed, ignore user
    patient = get_patient_by_sg_id(user.nric)
    if not patient:
        return None

    user.sgimed_patient_id = patient['id']
    diff_dict = compare_patient(user)
    if diff_dict:
        user.sgimed_diff = json.loads(json.dumps(diff_dict, default=str))

    # Update sgimed_auth_code for eDocs
    dob: date = diff_dict['date_of_birth'] if 'date_of_birth' in diff_dict else user.date_of_birth
    user.update_auth_code(dob)
    db.commit()

    return patient

def upsert_patient_in_sgimed(db: Session, user: Account, employee: Optional[EmployeeInfo] = None, branch: Optional[Branch] = None):
    '''
    1. If sgimed_patient_id does not exist on user record, run `patient = get_patient_by_sg_id('S92xxx12F')`
       1.1. If patient is empty, run `create_new_patient()`
       1.2 If patient exists in SGiMed, load the patient id into the user record
    2. If user.sgimed_synced is False run `update_patient_data(patient_id)`. This value will flip to False whenever the profile is updated.
    '''

    def get_new_user_data(user: Account):
        '''
        Convert User data to SGiMed format for creating a new user
        '''
        new_user_data = {
            "ic_type": user.ic_type.value,
            "nric": user.nric,
            # On Registration
            "name": user.name,
            "date_of_birth": user.date_of_birth.strftime("%Y-%m-%d"),
            "nationality": user.nationality.value.upper(),
            "language": user.language.value if user.language else None,
            "gender": user.gender.value,
            # On Sign Up
            "mobile": user.mobile_code.value + user.mobile_number,
            
            "branches": [branch.sgimed_branch_id if branch else SGIMED_DEFAULT_BRANCH_ID],
        }
        if not branch:
            logging.error(f"Branch not found for new user: {user.id}")

        return new_user_data
    
    def get_update_user_data(user: Account):
        '''
        Convert User data to SGiMed format for updating the user profile
        '''
        user_data = {
            # On Profile Change
            # "ic_type": ic_types[user.ic_type],
            # "nric": user.nric,
            # "name": user.name,
            # "date_of_birth": user.date_of_birth.strftime("%Y-%m-%d"),
            # "nationality": user.nationality.value.upper(),
            # "gender": user.gender.value,
            "language": user.language.value if user.language else None,
            "mobile": user.mobile_code.value + user.mobile_number,
            # Optional Fields if null not sent to SGiMed
            "phone": user.secondary_mobile_code.value + user.secondary_mobile_number if user.secondary_mobile_code and user.secondary_mobile_number else None,
            "email": user.email if user.email else None,
            # User Delivery & Residential Address
            "postal": user.residential_postal if user.residential_postal else user.postal,
            "address": user.residential_address if user.residential_address else user.address,
            "unit": user.residential_unit if user.residential_unit else user.unit,
            "building_name": user.residential_building if user.residential_building else user.building,
            "mailing_address": user.get_address()
        }
        # Patients who are not primary users of the app
        if user.parent_nok:
            parent_account = user.parent_nok.account
            user_data['mobile'] = user_data['phone']
            user_data['phone'] = parent_account.mobile_code.value + parent_account.mobile_number
            upsert_patient_nok(user)
            # Use parent account address
            user_data["postal"] = parent_account.residential_postal if parent_account.residential_postal else parent_account.postal
            user_data["address"] = parent_account.residential_address if parent_account.residential_address else parent_account.address
            user_data["unit"] = parent_account.residential_unit if parent_account.residential_unit else parent_account.unit
            user_data["building_name"] = parent_account.residential_building if parent_account.residential_building else parent_account.building
            user_data["mailing_address"] = parent_account.get_address()

        # Set to empty strings as SGiMed ignore null values
        if not user_data['postal']: user_data['postal'] = None
        if not user_data['address']: user_data['address'] = None
        if not user_data['unit']: user_data['unit'] = None
        if not user_data['building_name']: user_data['building_name'] = None
        if not user_data['mailing_address']: user_data['mailing_address'] = None

        # If postal and address exists, then unit and building_name should exist as empty strings if not present
        if user_data['postal'] and user_data['address']:
            if not user_data['unit']: user_data['unit'] = ''
            if not user_data['building_name']: user_data['building_name'] = ''

        # Remove keys with None values
        user_data = {k: v for k, v in user_data.items() if v is not None}
        return user_data

    # 1. Do a check if existing SGiMed user exists
    if user.sgimed_patient_id and not user_exists_in_sgimed(user.sgimed_patient_id):
        logging.error(f"Existing Patient ID: {user.id}, SGiMed ID: {user.sgimed_patient_id} not found. Resetting")
        user.sgimed_patient_id = None
        user.sgimed_patient_given_id = None

    # Retreive existing record, else create new record
    patient = retrieve_sgimed_patient_id(db, user)
    if not user.sgimed_patient_id:
        user.sgimed_patient_id = create_new_patient(get_new_user_data(user))
        user.update_auth_code()
        db.commit()

    # If user.sgimed_patient_given_id is not set, then set it to the patient's given_id
    if not user.sgimed_patient_given_id:
        if not patient:
            patient = get_patient_data(user.sgimed_patient_id)
        if patient and 'given_id' in patient:
            user.sgimed_patient_given_id = patient['given_id']
            db.commit()
        else:
            logging.error(f"SGiMed Patient ID: {user.sgimed_patient_id} does not have a given_id")

    # 2. If user.sgimed_synced is False run `update_patient_data(patient_id)`. This value will flip to False whenever the profile is updated.
    # Update the user profile in SGiMed everytime upsert is called to ensure profile is always updated
    user_data = get_update_user_data(user)
    if employee:
        user_data.update({
            "employee_id": employee.employee_id,
            "employee_company": employee.employee_company
        })

    try:
        update_patient_data(user.sgimed_patient_id, user_data)
    except Exception as e:
        logging.error(f'Failed to update SGiMed user ID: {user.id}, SGiMed ID: {user.sgimed_patient_id}. Error: {str(e)}')

    db.commit()

def log_rate_limits(response: requests.Response):
    rate_limit = response.headers.get('x-ratelimit-limit', '')
    remaining_limit = response.headers.get('x-ratelimit-remaining')
    if remaining_limit is not None:
        # sentry_sdk.metrics.distribution(
        #     key="sgimed_limit",
        #     value=float(remaining_limit),
        #     unit="remaining",
        # )
        print(f'SGiMed Remaining Rate Limit: {remaining_limit} / {rate_limit}')
    else:
        print('Rate limit information not available.')

class ClientException(Exception):
    pass

# Not used as Production had not migrated to Refresh Token implementation
token = None
def get_bearer_token() -> str:
    global token
    if token:
        decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=["ES256"])
        if (datetime.fromtimestamp(decoded_token["exp"]) - datetime.now()).total_seconds() < 1200: # 20 mins
            token = get_sgimed_access_token()
    else:
        token = get_sgimed_access_token()

    return token

def get_sgimed_access_token():
    response = requests.post(f"{SGIMED_API_URL}/token",
        headers={ "accept": "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        data={ "grant_type": "refresh_token", "refresh_token": SGIMED_API_KEY }
    )
    return response.json()["access_token"]

@retry(retry=retry_if_exception_type(ClientException), reraise=True, stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
def send_request(req: Callable, endpoint: str, **kwargs):
    headers = {'Authorization': f'Bearer {SGIMED_API_KEY}'}
    response = req(f'{SGIMED_API_URL}{endpoint}', headers=headers, **kwargs)
    # # Only for debugging
    # print(f"SGiMed Request: {req} {SGIMED_API_URL}{endpoint} {kwargs}")
    if response.status_code != 200:
        error = f'SGiMed Error: {endpoint}, {response.status_code}, {response.text}'
        print(error)
        # For 400, 404 errors, these are not server exceptions, thus no need to retry
        if response.status_code in [400, 404]:
            raise Exception(error)
        else:
            raise ClientException(error)
    
    log_rate_limits(response)
    return response.json()

def convert_bools_to_strings(params: dict) -> dict:
    '''
    For requests.get, boolean values are sent raw as True / False. Thus need to convert to strings lowercase
    '''
    def convert_value(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        return value

    return {k: convert_value(v) for k, v in params.items()}

def get(endpoint: str, params: dict = {}):
    return send_request(requests.get, endpoint, params=convert_bools_to_strings(params))

def post(endpoint: str, params: dict):
    json_data = json.dumps(params, default=str)
    return send_request(requests.post, endpoint, data=json_data)

def put(endpoint: str, params: dict):
    json_data = json.dumps(params, default=str)
    return send_request(requests.put, endpoint, data=json_data)

def delete(endpoint: str):
    return send_request(requests.delete, endpoint)

def get_patient_by_sg_id(sg_id: str):
    data = get('/patient', {'nric': sg_id})
    if len(data['data']) == 0:
        return None
    return data['data'][0]

def create_new_patient(user_data):
    resp = post('/patient', user_data)
    return resp['id']

def get_patient_data(sgimed_patient_id: str):
    resp = get(f'/patient/{sgimed_patient_id}')
    return resp

def update_patient_data(sgimed_patient_id: str, update_user_data: dict):
    if 'nationality' in update_user_data:
        update_user_data['nationality'] = update_user_data['nationality'].value.upper()
    resp = put(f'/patient/{sgimed_patient_id}', update_user_data)
    print(resp)

def create_queue(sgimed_patient_id: str, payment: Payment, teleconsult: Teleconsult, appointment_type_id: str, is_new_user: bool, sgimed_branch_id: Optional[str] = None):
    # TODO: Need to determine a better way to track
    # PN - PayNow, DC/CC - Debit / Credit Card, NC - Nets Click
    def generate_remarks():
        payment_type_dict = {
            "paynow": "PN",
            "nets": "NC",
            "card": "DC/CC"
        }
        def get_payment_type(payment_method: PaymentMethod):
            for k, v in payment_type_dict.items():
                if k in payment_method.value.lower():
                    return v
            return None

        # Get Yuu tomo_id if corporate code is YUU
        yuu_tomo_id = None
        if teleconsult.corporate_code == "YUU" and teleconsult.account.yuu_link:
            yuu_tomo_id = teleconsult.account.yuu_link.tomo_id

        remarks = [
            '[Verify ID]' if is_new_user else '',
            teleconsult.corporate_code if teleconsult.corporate_code else '', 
            f'S${payment.payment_amount:.2f}',
            get_payment_type(payment.payment_method) if get_payment_type(payment.payment_method) else '',
            f'(Allergy - {teleconsult.account.allergy})' if teleconsult.account.allergy else '',
            f'[{teleconsult.collection_method.value}]' if teleconsult.collection_method else '',
            f'Tomo ID: {yuu_tomo_id}' if yuu_tomo_id else '',
        ]
        return " ".join([r for r in remarks if r])
    
    data = {
        "patient_id": sgimed_patient_id,
        "branch_id": sgimed_branch_id if sgimed_branch_id else teleconsult.branch.sgimed_branch_id,
        "date": sg_datetime.now().strftime("%Y-%m-%d"),
        "appointment_type_id": appointment_type_id,
        "remark": generate_remarks()
    }

    resp = post('/queue', data)
    return resp['id']

def create_sgimed_walkin_queue(patient_id: str, branch_id: str, appointment_type_id: str):
    data = {
        "patient_id": patient_id,
        "branch_id": branch_id,
        "date": sg_datetime.now().strftime("%Y-%m-%d"),
        "appointment_type_id": appointment_type_id,
    }
    resp = post('/queue', data)
    visit_id = resp['id']
    resp = get_queue_status(visit_id)
    queue_number = resp['queue_no']
    return visit_id, queue_number

def insert_prepayment_to_invoice(visit_id, items):
    queue = get(f"/queue/{visit_id}")
    invoice_id = queue['invoices'][0]['id']
    
    resp = post('/invoice/item', {
            "invoice_id": invoice_id,
            "method": "append",
            "items": items
        })

    return True

class InvoiceItemRecord(BaseModel):
    item_code: str
    qty: int
    selling_price: float
    
class InvoicePaymentRecord(BaseModel):
    payment_mode_id: str
    amount: float
    remark: str

class InvoiceRecord(BaseModel):
    patient_id: str
    branch_id: str
    date: date
    appointment_type_id: str
    doctor_id: str
    items: list[InvoiceItemRecord]
    payments: list[InvoicePaymentRecord]

def create_invoice(invoice: InvoiceRecord) -> str:
    resp = post('/invoice', invoice.model_dump(mode='json'))
    return resp['id']

def get_queue_status(visit_id: str):
    resp = get(f'/queue/{visit_id}')
    return resp

def update_queue_instructions(visit_id: str, instruction: str):
    try:
        data = {
            "instruction": instruction
        }
        put(f'/queue/{visit_id}/instruction', data)
    except Exception as e:
        logging.error(f"Failed to update SGImed queue instructions for visit_id: {visit_id}. Error: {str(e)}")

def get_invoice(invoice_id: str):
    return get(f'/invoice/{invoice_id}')

def get_invoice_by_visit_id(visit_id: str):
    resp = get(f'/queue/{visit_id}/invoice')
    if len(resp['data']) == 0:
        return None
    
    return resp['data'][0]

def get_invoice_html(invoice_id: str):
    data = { "invoice_id": invoice_id }
    resp = post('/invoice/print', data)
    return resp['html']

def update_payments(invoice_id: str, teleconsult: Teleconsult):
    for p in teleconsult.get_successful_payments():
        if not p.payment_mode:
            continue

        data = {
            "invoice_id": invoice_id,
            "payment_mode_id": p.payment_mode.sgimed_payment_mode_id,
            "amount": f"{p.payment_amount:.2f}",
            "remark": f'{p.payment_type.value}, {p.payment_method.value}: {p.payment_id}'
        }

        resp =  post('/invoice/payment', data)
        print(resp)

    return True

def get_items(visit_id: str):
    data = {
        'visit_id': visit_id
    }
    resp = get('/order/item', data)
    return resp['data']

def get_prescription(visit_id: str):
    data = {
        'visit_id': visit_id
    }
    resp = get('/order/prescription', data)
    return resp['data']

def check_mc_exists(order_item_id: str):
    try:
        resp = get(f'/order/mc/{order_item_id}')
        return True
    except Exception as e:
        if '404' in str(e):
            return False
        raise Exception(str(e))

def get_mc_html(order_item_id: str):
    resp = get(f'/order/mc/{order_item_id}/print')
    return resp['html']

def get_mc_order_item_id(visit_id: str):
    '''
    Require two steps to get order_item_id before getting the html version of the MC
    '''
    data = {
        'visit_id': visit_id,
    }
    resp = get('/order/mc', data)
    if not resp['data']:
        return None
    
    order_item_id = resp['data'][0]['id']
    return order_item_id

class SGiMedDoctorRecord(BaseModel):
    id: str
    branch_id: str
    name: str
    email: Optional[str] = None
    # gender: Optional[str] = None
    # mcr: Optional[str] = None
    # title: Optional[str] = None
    # short_name: str
    # is_locum: bool
    # qualification_title: Optional[str] = None
    # appointment_interval: int
    # image_url: Optional[str] = None
    # sort_key: Optional[str] = None
    # created_at: str
    # last_edited: str

def get_doctors():
    resp = get('/doctor')
    return [SGiMedDoctorRecord.model_validate(row) for row in resp['data']]

class BranchRecord(BaseModel):
    id: str
    name: str
    # code: str # Code and ID is the same. Need to check back
    description: Optional[str] = None
    fax: Optional[str] = None
    phone: Optional[str] = None
    is_main: bool
    is_enabled: bool

def get_branches():
    resp = get('/branch')
    return [BranchRecord.model_validate(row) for row in resp['data']]

class AppointmentTypeRecord(BaseModel):
    id: str
    name: str
    branch_id: str
    sort_key: int
    is_enabled: bool
    is_for_visit: bool
    is_for_appointment: bool
    is_block_type: bool
    last_edited: datetime
    created_at: datetime

def get_services():
    '''
    Retrieve /appointment-type from SGiMed and only for records that are is_enabled and is_for_visit
    '''
    resp = get('/appointment-type')
    records = [AppointmentTypeRecord.model_validate(row) for row in resp['data']]
    return [record for record in records if record.is_enabled]

def create_pending_queue(patient_id: str, branch_id: str, appointment_type_id: str, date: str):
    resp = post('/pending-queue/by_patient', {
        "patient_id": patient_id,
        "branch_id": branch_id,
        "appointment_type_id": appointment_type_id,
        "date": date
    })

    return resp['id'], resp['queue_no']

def cancel_pending_queue(pending_queue_id: str):
    try:
        resp = delete(f'/pending-queue/{pending_queue_id}')
    except Exception as e:
        logging.error(f"SGiMed cancel_pending_queue: {e}")
    return True

def get_visit_id(pending_queue_id: str):
    resp = get(f'/pending-queue/{pending_queue_id}')
    if resp.get('visit') is None or resp['visit'].get('id') is None:
        logging.warning(f"SGiMed pending_queue.updated webhook but no visit ID found. Pending Queue ID: {pending_queue_id}")
        return None
    return resp['visit']['id']

def get_walkin_queues(visit_id) -> tuple[str, str, list[str]]:
    # Identify the branch
    resp = get(f'/queue/{visit_id}')
    curr_queue_number = resp['queue_no']
    branch_id = resp['branch_id']
    
    # Get the queues from the branch that are checked in
    resp = get('/queue', {
        "date": sg_datetime.now().strftime("%Y-%m-%d"),
        "instruction": WalkinQueueStatus.CHECKED_IN.value,
        "branch_id": branch_id,
    })
    
    # Sort by check_in_time
    queues = resp['data']
    print("Queues: ", queues)
    queues.sort(key=lambda x: x['check_in_time'])
    print([row['check_in_time'] for row in queues]) 
    visit_ids = [
        row['id']
        for row in queues if row['appointment_type']['name'] != 'Telemed'
    ][:5]
    
    return branch_id, curr_queue_number, visit_ids

def get_payment_modes():
    resp = get('/payment-mode')
    return resp['data']

def fetch_modified_updates(endpoint: str, modified_since: datetime, **kwargs):
    # Start with Page 1
    modified_since_str = modified_since.strftime("%Y-%m-%d %H:%M:%S")
    resp = get(endpoint, { "modified_since": modified_since_str, **kwargs })
    updated_rows = resp['data']
    # Restrict these endpoints to only 1 pages
    max_pages = 5
    if endpoint in ['/order/mc', '/invoice']:
        max_pages = 1

    # More than Page 1, If pages more than 5, only take 5 pages to prevent overload
    for i in range(2, min(resp['pager']['pages'] + 1, max_pages + 1)):
        resp = get(endpoint, { "modified_since": modified_since_str, "page": i, **kwargs })
        updated_rows += resp['data']
    
    return updated_rows

def get_pages(endpoint: str, params: dict, pages: int = 5):
    # Get Incoming Reports
    records = []
    pager = {}
    for i in range(pages):
        p = i + 1
        resp = get(endpoint, { 'page': p, **params })
        records += resp['data']
        pager = resp['pager']
        
        if p >= pager['pages']:
            if pager['pages'] > pages:
                logging.error(f"Request {endpoint} has {pager['pages']} / {pages} queried")
            break
    
    print(f"{endpoint}: {pager}")
    return records

class SGiMedPatientFields(BaseModel):
    ic_type: Optional[SGiMedICType] = None
    nric: Optional[str] = None
    name: str
    date_of_birth: date
    nationality: Optional[SGiMedNationality] = None
    gender: SGiMedGender
    language: Optional[SGiMedLanguage] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    unit: Optional[str] = None
    building_name: Optional[str] = None
    postal: Optional[str] = None

    @field_validator("ic_type", mode="before")
    @classmethod
    def transform_ic_type(cls, raw: str) -> Optional[SGiMedICType]:
        try:
            return SGiMedICType(raw)
        except Exception:
            logging.error(f"Unsupported SGiMed IC Type: {raw}")
            return None

    @field_validator("nationality", mode="before")
    @classmethod
    def transform_nationality(cls, raw: Optional[str]) -> Optional[SGiMedNationality]:
        if not raw:
            return None
        return SGiMedNationality(raw.strip().title())

    @field_validator("language", mode="before")
    @classmethod
    def transform_language(cls, raw: Optional[str]) -> Optional[SGiMedLanguage]:
        if not raw:
            return None
        return SGiMedLanguage(raw.strip().title())

def compare_patient(patient: Account, sgimed_patient_id: Optional[str] = None):
    try:
        sgimed_patient_id = sgimed_patient_id if sgimed_patient_id else patient.sgimed_patient_id
        if sgimed_patient_id is None:
            logging.error(f"SGiMed Compare: No SGiMed ID found for patient: {patient.id}")
            return {}

        patient_sgimed = get_patient_data(sgimed_patient_id)
        patient_sgimed = SGiMedPatientFields.model_validate(patient_sgimed).model_dump()

        diff_dict = {}
        patient_db = patient.as_dict()
        
        update_keys = ['ic_type', 'nric', 'name', 'date_of_birth', 'nationality', 'gender', 'language', 'email']
        for key in update_keys:
            # Ignore if the field is empty from SGiMed
            if not patient_sgimed[key]:
                continue
            # If the key is a string, and the value is stripped and lowercase is the same, ignore
            if type(patient_db[key]) == str and patient_db[key] and patient_db[key].strip().lower() == patient_sgimed[key].strip().lower():
                continue
            
            if patient_db[key] != patient_sgimed[key]:
                diff_dict[key] = patient_sgimed[key]

        # Update Secondary Phone. Break up phone number in country code and phone
        if patient_sgimed['phone']:
            phone = patient_sgimed['phone']
            secondary_mobile_code = PhoneCountryCode.SINGAPORE
            secondary_mobile_number = phone[1:] if phone[0] == '+' else phone
            if phone[0] == '+':
                for i in range(4, 1,-1):
                    try:
                        secondary_mobile_code = PhoneCountryCode(phone[:i])
                        secondary_mobile_number = phone[i:]
                        break
                    except ValueError:
                        pass
            
            if patient.secondary_mobile_code != secondary_mobile_code or patient.secondary_mobile_number != secondary_mobile_number:
                diff_dict['secondary_mobile_code'] = secondary_mobile_code
                diff_dict['secondary_mobile_number'] = secondary_mobile_number

        # Update Address only if address and postal are present
        address_sgimed = ['address', 'unit', 'building_name', 'postal']
        address_db = ['address', 'unit', 'building', 'postal']
        if patient_sgimed['address'] and patient_sgimed['postal']:
            for sgimed_key, db_key in zip(address_sgimed, address_db):
                # If the key is a string, and the value is stripped and lowercase is the same, ignore
                if type(patient_db[db_key]) == str and patient_db[db_key] and patient_sgimed[sgimed_key] and patient_db[db_key].strip().lower() == patient_sgimed[sgimed_key].strip().lower():
                    continue

                if patient_db[db_key] != patient_sgimed[sgimed_key]:
                    diff_dict[db_key] = patient_sgimed[sgimed_key]

        return diff_dict
    except Exception as e:
        logging.error(f"Failed to compare patient: {sgimed_patient_id}. Error: {e}")
        return {}

def get_patient_profile_updates(modified_since: datetime):
    return fetch_modified_updates('/patient', modified_since)

def get_document_updates(modified_since: datetime):
    return fetch_modified_updates('/document', modified_since)

def get_mc_updates(modified_since: datetime, include_void: bool = False):
    return fetch_modified_updates('/order/mc', modified_since, include_void=include_void)

def get_invoice_updates(modified_since: datetime, include_drafts_and_void: bool = False):
    return fetch_modified_updates('/invoice', modified_since, include_drafts=include_drafts_and_void, include_void=include_drafts_and_void)

def get_queue_updates(modified_since: datetime, date: date):
    return fetch_modified_updates('/queue', modified_since, date=date)

class CalendarDoctorRecord(BaseModel):
    id: str
    is_default: bool

class CalendarFacilityRecord(BaseModel):
    id: str

class CalendarRecord(BaseModel):
    id: str
    name: str
    remark: Optional[str] = None
    color: Optional[str] = None
    branch_id: str
    google_calendar_name: Optional[str] = None
    sort_key: Optional[int] = None
    is_enabled: bool
    calendar_doctors: list[CalendarDoctorRecord] = []
    calendar_facilities: list[CalendarFacilityRecord] = []
    default_appointment_type_id: Optional[str] = None
    last_edited: datetime
    created_at: datetime

def get_calendars() -> list[CalendarRecord]:
    """
    Get all calendars for a specific SGiMed branch.

    Returns:
        list[CalendarRecord]: List of calendar records for the branch
    """
    resp = get('/calendar')
    return [CalendarRecord.model_validate(row) for row in resp['data']]

class CreateCalendarRequest(BaseModel):
    branch_id: str
    name: Optional[str] = None
    remark: Optional[str] = None
    default_appointment_type_id: Optional[str] = None
    is_enabled: Optional[bool] = True

def create_calendar(calendar_data: CreateCalendarRequest) -> dict:
    """
    Create a calendar in SGiMed.

    Args:
        calendar_data: Calendar creation data including branch_id, name, doctors, etc.

    Returns:
        dict: Response from SGiMed API containing calendar ID and details
    """
    return post('/calendar', calendar_data.model_dump())

def delete_calendar(calendar_id: str):
    return delete(f'/calendar/{calendar_id}')