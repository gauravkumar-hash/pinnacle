from datetime import datetime, timedelta
from models.model_enums import BranchType
from models.patient import Account
from models.pinnacle import Branch
from utils.integrations.sgimed import get, post, put
from utils.sg_datetime import sgtz

def get_appointment(appointment_id: str):
    resp = get(f'/appointment/{appointment_id}')
    return resp

def update_appointment_status(appointment_id: str, is_confirmed: bool | None = None, is_informed: bool | None = None, is_cancelled: bool | None = None):
    resp = get_appointment(appointment_id)
    params = {
        'branch_id': resp['branch_id'],
        'appointment_type_id': resp['appointment_type']['id'],
        'calendar_ids': [row['id'] for row in resp['calendars']],
        'start_date': resp['start_date'], # Mandatory. Start date. (YYYY-MM-DD format)
        'start_time': resp['start_time'], # Optional. Start time. (HH:mm:ss format)
        'end_date': resp['end_date'], # Mandatory. End date. (YYYY-MM-DD format)
        'end_time': resp['end_time'], # Optional. End time. (HH:mm:ss format)
        'subject': resp['subject'],
        'description': resp['description'],
    }
    
    if resp['patient']:
        resp = put(f'/appointment/{appointment_id}/by_patient', {
            **params,
            'patient_id': str(resp['patient']['id']),
            'is_confirmed': is_confirmed if is_confirmed is not None else resp['is_confirmed'],
            'is_informed': is_informed if is_informed is not None else resp['is_informed'],
            'is_cancelled': is_cancelled if is_cancelled is not None else resp['is_cancelled'],
        })
    else:
        resp = put(f'/appointment/{appointment_id}/by_guest', {
            **params,
            'guest_name': resp['guest']['name'],
            'mobile': resp['guest']['phone'],
            'is_confirmed': is_confirmed if is_confirmed is not None else resp['is_confirmed'],
            'is_informed': is_informed if is_informed is not None else resp['is_informed'],
            'is_cancelled': is_cancelled if is_cancelled is not None else resp['is_cancelled'],
        })

def update_appointment_start_datetime(appointment_id: str, new_start_dt: datetime, duration: int):
    resp = get(f'/appointment/{appointment_id}')
    new_start_dt = new_start_dt.astimezone(sgtz)
    new_end_dt = new_start_dt + timedelta(minutes=duration)
    params = {
        'branch_id': resp['branch_id'],
        'appointment_type_id': resp['appointment_type']['id'],
        'calendar_ids': [row['id'] for row in resp['calendars']],
        'start_date': new_start_dt.strftime('%Y-%m-%d'), # Mandatory. Start date. (YYYY-MM-DD format)
        'start_time': new_start_dt.strftime('%H:%M:%S'), # Optional. Start time. (HH:mm:ss format)
        'end_date': new_end_dt.strftime('%Y-%m-%d'), # Mandatory. End date. (YYYY-MM-DD format)
        'end_time': new_end_dt.strftime('%H:%M:%S'), # Optional. End time. (HH:mm:ss format)
        'subject': resp['subject'],
        'description': resp['description'],
    }
    
    if resp['patient']:
        resp = put(f'/appointment/{appointment_id}/by_patient', {
            **params,
            'patient_id': str(resp['patient']['id']),
        })
    else:
        resp = put(f'/appointment/{appointment_id}/by_guest', {
            **params,
            'guest_name': resp['guest']['name'],
            'mobile': resp['guest']['phone'],
        })

def generate_default_params(created_by: Account, branch: Branch, start_dt: datetime, duration: int, service_groups: list[str], service_items: list[str], price: float):
    start_dt = start_dt.astimezone(sgtz)
    end_dt = start_dt + timedelta(minutes=duration)

    if not branch.sgimed_branch_id or not branch.sgimed_appointment_type_id:
        raise ValueError(f"Branch {branch.id} does not have sgimed_branch_id or sgimed_appointment_type_id configured")

    return {
        'branch_id': str(branch.sgimed_branch_id),
        'appointment_type_id': branch.sgimed_appointment_type_id,
        'calendar_ids': [str(branch.sgimed_calendar_id)],
        'start_date': start_dt.strftime('%Y-%m-%d'), # Mandatory. Start date. (YYYY-MM-DD format)
        'start_time': start_dt.strftime('%H:%M:%S'), # Optional. Start time. (HH:mm:ss format)
        'end_date': end_dt.strftime('%Y-%m-%d'), # Mandatory. End date. (YYYY-MM-DD format)
        'end_time': end_dt.strftime('%H:%M:%S'), # Optional. End time. (HH:mm:ss format)
        'subject': f"[${price:.2f}] " + ", ".join(service_groups),
        'description': "\n".join(service_items) + f"\n\nCreated by: {created_by.nric} {created_by.name}",
    }

def post_appointment_by_patient(user: Account, created_by: Account, branch: Branch, start_dt: datetime, duration: int, service_groups: list[str], service_items: list[str], price: float):
    resp = post('/appointment/by_patient', {
        **generate_default_params(created_by, branch, start_dt, duration, service_groups, service_items, price),
        'patient_id': str(user.sgimed_patient_id),
        'is_confirmed': True,
    })
    return resp['id']

def post_appointment_by_guest(guest_name: str, guest_mobile: str, created_by: Account, branch: Branch, start_dt: datetime, duration: int, service_groups: list[str], service_items: list[str], price: float):
    start_dt = start_dt.astimezone(sgtz)
    end_dt = start_dt + timedelta(minutes=duration)
    resp = post('/appointment/by_guest', {
        **generate_default_params(created_by, branch, start_dt, duration, service_groups, service_items, price),
        'guest_name': guest_name, # guest_name: Mandatory. Guest name.
        'mobile': guest_mobile, # mobile: Optional. Guest mobile.
        'is_confirmed': True,
    })
    return resp['id']

def put_appointment_by_patient(appointment_id: str, user: Account, created_by: Account, branch: Branch, start_dt: datetime, duration: int, service_groups: list[str], service_items: list[str], price: float, is_confirmed: bool, is_informed: bool, is_cancelled: bool):
    resp = put(f'/appointment/{appointment_id}/by_patient', {
        **generate_default_params(created_by, branch, start_dt, duration, service_groups, service_items, price),
        'patient_id': str(user.sgimed_patient_id),
        'is_confirmed': is_confirmed,
        'is_informed': is_informed,
        'is_cancelled': is_cancelled,
    })

def put_appointment_by_guest(appointment_id: str, guest_name: str, guest_mobile: str, created_by: Account, branch: Branch, start_dt: datetime, duration: int, service_groups: list[str], service_items: list[str], price: float, is_confirmed: bool, is_informed: bool, is_cancelled: bool):
    resp = put(f'/appointment/{appointment_id}/by_guest', {
        **generate_default_params(created_by, branch, start_dt, duration, service_groups, service_items, price),
        'guest_name': guest_name,
        'mobile': guest_mobile,
        'is_confirmed': is_confirmed,
        'is_informed': is_informed,
        'is_cancelled': is_cancelled,
    })
