from typing import Any
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import UnaryExpression
from utils.admin_query.models import AdminQuery, AdminQueryApiParams, AdminQueryColumn, AdminQueryFilter, AdminQueryModel, FrontendComponent
from sqlalchemy import select, and_, or_, func, cast, text, String
from sqlalchemy.orm import joinedload
from sqlalchemy.dialects.postgresql import JSONB
from models import Account, Appointment
from models.model_enums import AppointmentStatus
from datetime import datetime
from utils.sg_datetime import sgtz

class AppointmentRow(BaseModel):
    id: str
    patient: str
    phone: str
    created_by: str
    start_datetime: datetime
    created_at: datetime
    amount: float
    status: str
    corporate_code: str
    patient_survey: str
    services: str
    service_items: str
    branch_name: str

columns = [
    AdminQueryColumn(id='id', name='Appointment ID'),
    AdminQueryColumn(id='patient', name='Patient Name'),
    AdminQueryColumn(id='phone', name='Phone Number'),
    AdminQueryColumn(id='created_by', name='Created By'),
    AdminQueryColumn(id='start_datetime', name='Appointment Date & Time'),
    AdminQueryColumn(id='created_at', name='Created At'),
    AdminQueryColumn(id='amount', name='Amount'),
    AdminQueryColumn(id='status', name='Status'),
    AdminQueryColumn(id='corporate_code', name='Corp Code'),
    AdminQueryColumn(id='patient_survey', name='Patient Survey'),
    AdminQueryColumn(id='services', name='Services'),
    AdminQueryColumn(id='service_items', name='Service Items'),
    AdminQueryColumn(id='branch_name', name='Branch Name')
]

filters = [
    AdminQueryFilter(id='search', name='Patient Search', component=FrontendComponent.TEXT),
    AdminQueryFilter(id='status', name='Status', component=FrontendComponent.SELECT, options=[]),
    AdminQueryFilter(id='branch_id', name='Branch', component=FrontendComponent.SELECT, options=[]),
    AdminQueryFilter(id='date_from', name='Date From', component=FrontendComponent.DATE),
    AdminQueryFilter(id='date_to', name='Date To', component=FrontendComponent.DATE),
    AdminQueryFilter(id='service_group_id', name='Service Group', component=FrontendComponent.SELECT, options=[]),
    AdminQueryFilter(id='corporate_code', name='Corporate Code', component=FrontendComponent.SELECT, options=[]),
]

# params = AdminQueryApiParams(
#     page=1,
#     rows=5,
#     filters={ 'search': 'Hu' },
#     order_by=[{ 'start_datetime': 'desc' }]
# )

def query_fn(model: AdminQueryModel[type[AppointmentRow]], params: AdminQueryApiParams):
    stmt = select(Appointment).options(
        joinedload(Appointment.account).load_only(
            Account.id,
            Account.name,
            Account.mobile_code,
            Account.mobile_number,
            Account.secondary_mobile_code,
            Account.secondary_mobile_number,
            Account.email,
            Account.nric,
            Account.date_of_birth
        ),
        joinedload(Appointment.created_by_account).load_only(
            Account.name,
        ),

    )

    conditions = [
        Appointment.status.not_in([
            AppointmentStatus.PREPAYMENT,
            AppointmentStatus.PAYMENT_STARTED
        ]),
        or_(
            Appointment.account_id.isnot(None),
            and_(
                Appointment.guests.isnot(None),
                func.jsonb_array_length(cast(Appointment.guests, JSONB)) > 0
            )
        )
    ]
    stmt = stmt.where(and_(*conditions))

    # Filtering based on user parameters
    for filter in model.filters:
        if filter.id not in params.filters:
            continue

        if filter.id == 'search':
            search = params.filters['search']
            search_term = f"%{search}%"
            search_conditions = [
                # Search in account name
                Appointment.account.has(Account.name.ilike(search_term)),
                # Search in account mobile numbers
                Appointment.account.has(Account.mobile_number.ilike(search_term)),
                Appointment.account.has(Account.secondary_mobile_number.ilike(search_term)),
                # Search in guests JSON
                cast(Appointment.guests, String).ilike(search_term),
                # Search in services JSON (service names)
                cast(Appointment.services, String).ilike(search_term)
            ]
            stmt = stmt.where(or_(*search_conditions))

        elif filter.id == 'status':
            status = params.filters['status']
            stmt = stmt.where(Appointment.status == status)

        elif filter.id == 'branch_id':
            branch_id = params.filters['branch_id']
            stmt = stmt.where(Appointment.branch.op('->>')('id') == branch_id)

        # Apply date filters with Singapore timezone handling
        elif filter.id == 'date_from':
            date_from = params.filters['date_from']
            stmt = stmt.where(Appointment.start_datetime >= date_from)

        elif filter.id == 'date_to':
            date_to = params.filters['date_to']
            stmt = stmt.where(Appointment.start_datetime <= date_to)

        elif filter.id == 'corporate_code':
            corporate_code = params.filters['corporate_code']
            stmt = stmt.where(Appointment.corporate_code == corporate_code)

        elif filter.id == 'service_group_id':
            service_group_id = params.filters['service_group_id']
            # Services are stored as JSON array with structure: [{"id": "<service_group_id>", ...}]
            # Cast to jsonb for proper containment check
            stmt = stmt.where(
                text("services::jsonb @> :services").params(
                    services=f'[{{"id": "{service_group_id}"}}]'
                )
            )

    # Apply ordering
    order_list: list[UnaryExpression[Any]] = []
    for order_row in params.order_by:
        for k, v in order_row.items():
            if k == 'created_at':
                order_list.append(
                    Appointment.created_at.asc().nullslast()
                    if v == 'asc'
                    else Appointment.created_at.desc().nullslast()
                )
            elif k == 'start_datetime':
                order_list.append(
                    Appointment.start_datetime.asc().nullslast()
                    if v == 'asc'
                    else Appointment.start_datetime.desc().nullslast()
                )

    if order_list:
        stmt = stmt.order_by(*order_list)

    # Apply pagination
    if params.rows:
        page = params.page
        rows = params.rows
        stmt = stmt.limit(rows).offset((page - 1) * rows)

    return stmt

def transform_fn(data: list[Appointment]):
    rows: list[AppointmentRow] = []

    def format_patient_survey(appointment: Appointment) -> str:
        """Format patient survey data into readable string"""
        if not appointment.patient_survey:
            return ''

        # Handle case where patient_survey is already a string
        if isinstance(appointment.patient_survey, str):
            return appointment.patient_survey

        # Handle case where patient_survey is a dict
        if isinstance(appointment.patient_survey, dict):
            survey_items = []
            for key, value in appointment.patient_survey.items():
                if isinstance(value, (list, dict)):
                    survey_items.append(f"{key}: {str(value)}")
                else:
                    survey_items.append(f"{key}: {value}")
            return '; '.join(survey_items)

        # Fallback for other types
        return str(appointment.patient_survey)

    def format_services(appointment: Appointment) -> str:
        """Format services list into readable string"""
        if not appointment.services:
            return ''

        service_names = []
        for service in appointment.services:
            service_names.append(service.get('name', ''))

        return ', '.join(filter(None, service_names))

    def format_service_items(appointment: Appointment) -> str:
        """Format selected service items into readable string"""
        if not appointment.services:
            return ''

        all_items = []
        for service_group in appointment.services:
            items = service_group.get('items', [])
            for item in items:
                item_name = item.get('name', '')
                if item_name:
                    all_items.append(item_name)

        return ', '.join(all_items)

    for appointment in data:
        row_data = {
            'created_by': appointment.created_by_account.name if appointment.created_by_account else 'Unknown',
            'start_datetime': appointment.start_datetime.astimezone(sgtz),
            'created_at': appointment.created_at.astimezone(sgtz),
            'amount': appointment.payment_breakdown.get('total', 0.0) if appointment.payment_breakdown else 0.0,
            'status': appointment.status.value if appointment.status else '',
            'corporate_code': appointment.corporate_code or '',
            'patient_survey': format_patient_survey(appointment),
            'services': format_services(appointment),
            'service_items': format_service_items(appointment),
            'branch_name': appointment.branch.get('name', '') if appointment.branch else '',
        }

        # If appointment has an account (registered user)
        if appointment.account and appointment.account.name:
            # Format phone number from mobile_code and mobile_number
            phone = ''
            if hasattr(appointment.account, 'mobile_code') and hasattr(appointment.account, 'mobile_number'):
                if appointment.account.mobile_code and appointment.account.mobile_number:
                    phone = f"{appointment.account.mobile_code.value}{appointment.account.mobile_number}"
                elif appointment.account.secondary_mobile_code and appointment.account.secondary_mobile_number:
                    phone = f"{appointment.account.secondary_mobile_code.value}{appointment.account.secondary_mobile_number}"

            rows.append(
                AppointmentRow(
                    id=str(appointment.id),
                    patient=appointment.account.name,
                    phone=phone,
                    **row_data
                )
            )

        # If appointment has guests
        if appointment.guests:
            for guest in appointment.guests:
                guest_name: str = guest.get('name', '')
                guest_phone: str = guest.get('mobile', '')
                if guest_name:  # Only include if we have a name
                    formatted_name = f"{guest_name} (Guest)"
                    rows.append(
                        AppointmentRow(
                            id=str(appointment.id),
                            patient=formatted_name,
                            phone=guest_phone,
                            **row_data
                        )
                    )

    return rows

def get_csv_response(db: Session, params: AdminQueryApiParams) -> StreamingResponse:
    qry = AdminQuery(
        model = AdminQueryModel(
            model=AppointmentRow,
            columns=columns,
            filters=filters
        ),
        params=params,
        query_fn=query_fn,
        transform_fn=transform_fn
    )
    formattings = {
        datetime: lambda x: x.strftime('%Y-%m-%d %H:%M:%S'),
        'amount': lambda x: f"S${x:.2f}"
    }
    return qry.get_csv_response(db, formattings)
