from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from routers.delivery.typings.delivery import (
    TeleconsultDeliveryResponse,
    UpdateTeleconsultDeliveryStatusRequest,
    UpdateTeleconsultDeliveryRequest,
    DispatchUpdateTeleconsultDeliveryStatusRequest,
)
from models import Account
from models.delivery import TeleconsultDelivery, DeliveryStatus
from models.teleconsult import Teleconsult, CollectionMethod, PatientType
from datetime import date
from typing import Optional
from datetime import timedelta
import logging
from uuid import UUID
from utils import sg_datetime
from utils.fastapi import SuccessResp
from routers.delivery.actions.zone import retrieve_pinnacle_zone_by_sector_code, retrieve_pinnacle_zone_by_sector_codes
from utils.supabase_s3 import (
    upload_pdf,
    get_blob_data_from_s3,
    check_is_file_exists_in_s3,
    download_file_from_s3,
    download_files_as_zip,
    ZipFileRequest,
    get_signed_url,
    SignedURLResponse
)
from config import SGIMED_MEDICATION_ITEM_TYPE, SUPABASE_PRIVATE_BUCKET
from utils.excel import create_excel_with_styled_header
from routers.delivery.typings.delivery import TeleconsultDeliveryFamily, DriverFetchingResponse, UpdateBulkTeleconsultDeliveryStatusRequest
from routers.delivery.actions.zone import (
    RetrievePinnacleZoneResponse,
)
from models.pinnacle import PublicHoliday, PinnacleAccount
from models.model_enums import Role
from utils.supabase_auth import SupabaseUser
from datetime import datetime

def parse_teleconsult_delivery_object(
    delivery: TeleconsultDelivery | TeleconsultDeliveryFamily,
    db: Session
) -> TeleconsultDeliveryResponse:
    
    if isinstance(delivery, TeleconsultDeliveryFamily):
        record = {
            "dispatch_name": delivery.dispatch_name,
            "patient_name": delivery.combined_name,
            "patient_nric": delivery.combined_nric,
            "patient_queue_number": delivery.combined_queue_number,
            "sgimed_patient_id": delivery.combined_sgimed_patient_id,
            "phone_number": delivery.phone_number,
            "consultation_date": sg_datetime.sg(delivery.consultation_date) if delivery.consultation_date else None,
            # This already handled in the grouping_family_teleconsult_deliveries_handler, can directly pass the value
            "is_migrant_area": delivery.is_migrant_area,
        }
    else:
        zone_response: RetrievePinnacleZoneResponse = retrieve_pinnacle_zone_by_sector_code(
        delivery.postal[:2], db
        )
        record = {
            "dispatch_name": delivery.clinic_account.name if delivery.clinic_account else None,
            "patient_name": delivery.patient_account.name,
            "patient_nric": delivery.patient_account.nric,
            "patient_queue_number": delivery.teleconsult.queue_number,
            "sgimed_patient_id": delivery.patient_account.sgimed_patient_given_id,
            "phone_number": f"{delivery.patient_account.mobile_code.value} {delivery.patient_account.mobile_number}",
            "consultation_date": sg_datetime.sg(delivery.teleconsult.teleconsult_start_time) if delivery.teleconsult and delivery.teleconsult.teleconsult_start_time else None,
            # The logic here is that if the zone is Zone F and the delivery is migrant, then the is_migrant_area is True
            "is_migrant_area": zone_response.is_migrant_area and delivery.is_migrant,
        }
    
    return TeleconsultDeliveryResponse(
        id=str(delivery.id),
        zone=delivery.zone,
        address=delivery.address,
        postal=delivery.postal,
        status=delivery.status,
        dispatch_history=delivery.dispatch_history,
        is_migrant=delivery.is_migrant,
        number_of_packages=delivery.number_of_packages,
        delivery_date=delivery.delivery_date,
        delivery_attempt=delivery.delivery_attempt,
        recipient_name=delivery.recipient_name,
        is_delivery_note_exists=delivery.is_delivery_note_exists,
        delivery_note_file_path=delivery.delivery_note_file_path,
        receipt_date=sg_datetime.sg(delivery.receipt_date) if delivery.receipt_date else None,
        **record,
    )


def grouping_family_teleconsult_deliveries_handler(teleconsult_deliveries: list[TeleconsultDelivery], db: Session) -> list[TeleconsultDeliveryFamily]:
    # Group deliveries by group_id
    grouped_deliveries: dict[str, list[TeleconsultDelivery]] = {}

    for delivery in teleconsult_deliveries:
        if not delivery.group_id:
            # If no group_id, treat as individual delivery
            grouped_deliveries[str(delivery.id)] = [delivery]
            continue

        if delivery.group_id not in grouped_deliveries:
            grouped_deliveries[delivery.group_id] = []
        grouped_deliveries[delivery.group_id].append(delivery)

    # Process each group and combine queue numbers
    result = []
    postal_codes = retrieve_pinnacle_zone_by_sector_codes(
        [deliveries[0].postal[:2] for deliveries in grouped_deliveries.values()], db
    )
    for deliveries in grouped_deliveries.values():
        # For multiple deliveries in a group, combine queue numbers
        base_delivery = deliveries[0]
        zone_response = postal_codes[base_delivery.postal[:2]]
        # Sort deliveries by queue number
        sorted_deliveries = sorted(
            deliveries,
            key=lambda x: (
                x.teleconsult.queue_number if x.teleconsult.queue_number else ""
            ),
        )

        # Combine information maintaining queue number order
        combined_queue_numbers = "\n".join(
            delivery.teleconsult.queue_number
            for delivery in sorted_deliveries
            if delivery.teleconsult.queue_number
        )

        combined_patient_nric = "\n ".join(
            delivery.patient_account.nric
            for delivery in sorted_deliveries
            if delivery.patient_account.nric
        )

        combined_patient_name = "\n".join(
            delivery.patient_account.name
            for delivery in sorted_deliveries
            if delivery.patient_account.name
        )

        combined_sgimed_patient_id = "\n ".join(
            delivery.patient_account.sgimed_patient_given_id
            for delivery in sorted_deliveries
            if delivery.patient_account.sgimed_patient_given_id
        )

        # Create a copy of the base delivery object
        delivery_copy = TeleconsultDeliveryFamily(
            id=str(base_delivery.id),
            zone=base_delivery.zone,
            address=base_delivery.address,
            postal=base_delivery.postal,
            is_migrant_area=zone_response.is_migrant_area and base_delivery.is_migrant,
            status=base_delivery.status,
            dispatch_history=(
                base_delivery.dispatch_history.copy()
                if base_delivery.dispatch_history
                else []
            ),
            is_migrant=base_delivery.is_migrant,
            number_of_packages=base_delivery.number_of_packages,
            delivery_date=base_delivery.delivery_date,
            delivery_attempt=base_delivery.delivery_attempt,
            recipient_name=base_delivery.recipient_name,
            receipt_date=base_delivery.receipt_date,
            is_delivery_note_exists=base_delivery.is_delivery_note_exists,
            delivery_note_file_path=base_delivery.delivery_note_file_path,
            dispatch_name=(
                base_delivery.clinic_account.name
                if base_delivery.clinic_account
                else None
            ),
            consultation_date=base_delivery.teleconsult.teleconsult_start_time if base_delivery.teleconsult and base_delivery.teleconsult.teleconsult_start_time else None,
            phone_number=f"{base_delivery.patient_account.mobile_code.value} {base_delivery.patient_account.mobile_number}"
        )

        # Modify the copy with combined information
        delivery_copy.combined_queue_number = combined_queue_numbers
        delivery_copy.combined_nric = combined_patient_nric
        delivery_copy.combined_name = combined_patient_name
        delivery_copy.combined_sgimed_patient_id = combined_sgimed_patient_id

        result.append(delivery_copy)

    return result


def logistics_get_teleconsult_delivery_objects_by_date(date: date, db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(TeleconsultDelivery.delivery_date == date)
        .options(
            joinedload(TeleconsultDelivery.teleconsult),
            joinedload(TeleconsultDelivery.patient_account),
            joinedload(TeleconsultDelivery.clinic_account),
        )
        .all()
    )

    if not teleconsult_deliveries:
        return []

    # Sort by status priority: retry -> pending -> cancelled -> success
    status_priority = {
        DeliveryStatus.FAILED.value: 0,
        DeliveryStatus.RETRY.value: 1,
        DeliveryStatus.PENDING.value: 2,
        DeliveryStatus.CANCELLED.value: 3,
        DeliveryStatus.SUCCESS.value: 4,
        DeliveryStatus.NO_DELIVERY_SERVICE.value: 5,
    }

    sorted_deliveries = sorted(
        teleconsult_deliveries,
        key=lambda x: (
            status_priority[x.status.value],
            x.teleconsult.teleconsult_start_time if x.teleconsult and x.teleconsult.teleconsult_start_time else datetime.max
        )
    )

    grouped_deliveries = grouping_family_teleconsult_deliveries_handler(
        sorted_deliveries, db
    )

    return [
        parse_teleconsult_delivery_object(delivery, db) for delivery in grouped_deliveries
    ]


def logistics_get_teleconsult_delivery_objects_without_date(db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(
            TeleconsultDelivery.status.in_(
                [
                    DeliveryStatus.PENDING,
                    DeliveryStatus.RETRY,
                    DeliveryStatus.FAILED,
                    DeliveryStatus.NO_DELIVERY_SERVICE,
                ]
            )
        )
        .options(
            joinedload(TeleconsultDelivery.teleconsult),
            joinedload(TeleconsultDelivery.patient_account),
            joinedload(TeleconsultDelivery.clinic_account),
        )
        .all()
    )
    teleconsult_deliveries = [
        delivery
        for delivery in teleconsult_deliveries
        if not (
            delivery.status == DeliveryStatus.NO_DELIVERY_SERVICE
            and (delivery.delivery_date < sg_datetime.now().date() if delivery.delivery_date else False)
        )
    ]
    if not teleconsult_deliveries:
        return []

    # Sort by status priority: retry -> pending -> failed
    status_priority = {
        DeliveryStatus.FAILED.value: 1,
        DeliveryStatus.RETRY.value: 2,
        DeliveryStatus.PENDING.value: 3,
        DeliveryStatus.NO_DELIVERY_SERVICE.value: 4,
    }

    sorted_deliveries = sorted(
        teleconsult_deliveries,
        key=lambda x: (
            0 if (x.status == DeliveryStatus.PENDING and 
            (x.number_of_packages is None or x.delivery_date is None)) 
            else status_priority[x.status.value],
            x.teleconsult.teleconsult_start_time if x.teleconsult and x.teleconsult.teleconsult_start_time else datetime.max
        ),
    )
    
    grouped_deliveries = grouping_family_teleconsult_deliveries_handler(
        sorted_deliveries, db
    )

    return [
        parse_teleconsult_delivery_object(delivery, db) for delivery in grouped_deliveries
    ]

# Delivery Endponts
def logistics_get_teleconsult_delivery_objects(db: Session, date: Optional[date] = None):
    if date:
        return logistics_get_teleconsult_delivery_objects_by_date(date, db)
    return logistics_get_teleconsult_delivery_objects_without_date(db)

def dispatch_get_teleconsult_delivery_objects(db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(
            TeleconsultDelivery.status.in_(
                [
                    DeliveryStatus.PENDING,
                    DeliveryStatus.RETRY,
                ]
            ),
            TeleconsultDelivery.number_of_packages != None,
        )
        .order_by(TeleconsultDelivery.delivery_date)
        .options(
            joinedload(TeleconsultDelivery.teleconsult),
            joinedload(TeleconsultDelivery.patient_account),
            joinedload(TeleconsultDelivery.clinic_account),
        )
        .all()
    )
    
    sorted_deliveries = sorted(
        teleconsult_deliveries,
        key=lambda x: (
            x.delivery_date,
            x.teleconsult.teleconsult_start_time if x.teleconsult and x.teleconsult.teleconsult_start_time else datetime.max
        )
    )

    grouped_deliveries = grouping_family_teleconsult_deliveries_handler(
        sorted_deliveries, db
    )

    return [
        parse_teleconsult_delivery_object(delivery, db) for delivery in grouped_deliveries
    ]

def check_can_delivery_today(db: Session) -> bool:
    curr_dt = sg_datetime.now()
    curr_date = curr_dt.date()
    curr_time = curr_dt.time()
    
    holiday = db.query(PublicHoliday.date).filter(PublicHoliday.date == curr_date).first()
    is_weekend = curr_dt.weekday() >= 5
    
    if holiday or is_weekend:
        can_deliver = curr_time.hour < 19  # Before 7pm
    else:
        can_deliver = curr_time.hour < 21  # Before 9pm
    
    return can_deliver

def get_delivery_date(db: Session):
    can_deliver = check_can_delivery_today(db)
    return sg_datetime.now().date() if can_deliver else sg_datetime.now().date() + timedelta(days=1)
    
    
def patient_get_teleconsult_delivery_objects(id: str, db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(
            TeleconsultDelivery.patient_id == id,
            TeleconsultDelivery.is_delivery_note_exists == True,
            TeleconsultDelivery.status == DeliveryStatus.SUCCESS,
        )
        .order_by(TeleconsultDelivery.delivery_date)
        .all()
    )
    return [
        parse_teleconsult_delivery_object(delivery, db)
        for delivery in teleconsult_deliveries
    ]

def teleconsult_delivery_object_handler(teleconsult: Teleconsult, db: Session):
    '''
    This is to ensure it does not crash the main teleconsult processing logic
    '''
    try:
        has_medication = any([item['item_type'] == SGIMED_MEDICATION_ITEM_TYPE for item in teleconsult.invoices[0].items])
        if has_medication and teleconsult.collection_method == CollectionMethod.DELIVERY:
            _teleconsult_delivery_object_handler(teleconsult, db)
    except Exception as e:
        logging.error(f"delivery.py: {e}", exc_info=True)

def _teleconsult_delivery_object_handler(teleconsult: Teleconsult, db: Session):
    teleconsult_delivery = (
        db.query(TeleconsultDelivery)
            .filter(TeleconsultDelivery.teleconsult_id == teleconsult.id)
            .first()
    )
    user = teleconsult.account
    sector_code = user.postal[:2] if user.postal else None
    if teleconsult_delivery:
        raise Exception(f"Teleconsult delivery already exists for teleconsult {teleconsult.id}")
    if not sector_code:
        raise Exception(f"Postal code not found for user {user.id}, teleconsult {teleconsult.id}")

    group_teleconsults = [teleconsult]
    if teleconsult.group_id:
        group_teleconsults = (
            db.query(Teleconsult)
                .filter(Teleconsult.group_id == teleconsult.group_id)
                .all()
        )

    # Delivery date logic
    zone_response: RetrievePinnacleZoneResponse = retrieve_pinnacle_zone_by_sector_code(sector_code, db)
    delivery_date = get_delivery_date(db)

    for teleconsult in group_teleconsults:
        teleconsult_delivery = TeleconsultDelivery(
            teleconsult_id=teleconsult.id,
            zone=zone_response.zone,
            address=user.get_address_without_postal(),
            postal=user.postal,
            delivery_date=delivery_date,
            number_of_packages=1,
            status=(
                DeliveryStatus.PENDING
                if zone_response.has_service
                else DeliveryStatus.NO_DELIVERY_SERVICE
            ),
            is_migrant=teleconsult.patient_type == PatientType.MIGRANT_WORKER,
            delivery_attempt=1,
            patient_id=teleconsult.account_id,
            dispatch_history=[],
            group_id=teleconsult.group_id if teleconsult.group_id else None,
        )
        db.add(teleconsult_delivery)
    db.commit()

def get_grouping_teleconsult_deliveries_by_delivery_object_for_updating(teleconsult_delivery: TeleconsultDelivery, db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
            .filter(TeleconsultDelivery.group_id == teleconsult_delivery.group_id)
            .all()
    )
    return teleconsult_deliveries

def update_bulk_teleconsult_delivery_status(request: UpdateBulkTeleconsultDeliveryStatusRequest, db: Session):
    teleconsult_deliveries_query = (
        db.query(TeleconsultDelivery)
        .filter(TeleconsultDelivery.id.in_(request.ids))
        .all()
    )
    
    for delivery in teleconsult_deliveries_query:
        teleconsult_deliveries = get_grouping_teleconsult_deliveries_by_delivery_object_for_updating(delivery, db) if delivery.group_id else [delivery]
        
        for td in teleconsult_deliveries:
            td.status = request.status
            td.receipt_date = sg_datetime.now()
            td.dispatch_id = UUID(request.driver_id) if request.driver_id else None
            
            if request.status == DeliveryStatus.SUCCESS:
                td.recipient_name = td.patient_account.name
            
    db.commit()
    return SuccessResp(success=True)

def update_teleconsult_delivery_status(request: UpdateTeleconsultDeliveryStatusRequest, user: SupabaseUser, db: Session):
    teleconsult_delivery = (
        db.query(TeleconsultDelivery)
            .filter(TeleconsultDelivery.id == request.id)
            .first()
    )
    if not teleconsult_delivery:
        raise HTTPException(status_code=404, detail="Teleconsult delivery not found")
    
    teleconsult_deliveries = get_grouping_teleconsult_deliveries_by_delivery_object_for_updating(teleconsult_delivery, db) if teleconsult_delivery.group_id else [teleconsult_delivery]
    
    for teleconsult_delivery in teleconsult_deliveries:
        teleconsult_delivery.status = request.status

        if (
            request.status == DeliveryStatus.SUCCESS
            or request.status == DeliveryStatus.FAILED
            or request.status == DeliveryStatus.CANCELLED
        ):
            teleconsult_delivery.receipt_date = sg_datetime.now()
            teleconsult_delivery.dispatch_id = UUID(user.id) if user.id else None
        
        if request.status == DeliveryStatus.SUCCESS:
            teleconsult_delivery.recipient_name = request.recipient_name if request.recipient_name and request.recipient_name.strip() != "" else teleconsult_delivery.patient_account.name
            # TODO: generate a dummy delivery note to store in s3

    db.commit()
    return SuccessResp(success=True)

def update_teleconsult_delivery(request: UpdateTeleconsultDeliveryRequest, db: Session):
    teleconsult_delivery = (
        db.query(TeleconsultDelivery)
        .filter(TeleconsultDelivery.id == request.id)
        .first()
    )
    if not teleconsult_delivery:
        logging.error(f"Teleconsult delivery not found for id {request.id}")
        raise HTTPException(status_code=404, detail="Teleconsult delivery not found")

    teleconsult_deliveries = get_grouping_teleconsult_deliveries_by_delivery_object_for_updating(teleconsult_delivery, db) if teleconsult_delivery.group_id else [teleconsult_delivery]

    if request.date_of_delivery < sg_datetime.now().date():
        raise HTTPException(
            status_code=400, detail="Delivery date cannot be in the past"
        )

    if request.number_of_package < 0:
        raise HTTPException(
            status_code=400, detail="Number of packages cannot be less than 0"
        )

    if (
        teleconsult_delivery.status == DeliveryStatus.SUCCESS
        or teleconsult_delivery.status == DeliveryStatus.CANCELLED
    ):
        raise HTTPException(
            status_code=400,
            detail="Delivery cannot be updated after it is successful or cancelled",
        )

    if teleconsult_delivery.status == DeliveryStatus.FAILED:
        for teleconsult_delivery in teleconsult_deliveries:
            teleconsult_delivery.dispatch_history = teleconsult_delivery.dispatch_history + [
                {
                    "number_of_packages": teleconsult_delivery.number_of_packages,
                    "delivery_date": sg_datetime.custom_date_serializer(
                        teleconsult_delivery.delivery_date
                    ),
                    "delivery_attempt": teleconsult_delivery.delivery_attempt,
                    "receipt_date": sg_datetime.custom_date_serializer(
                        sg_datetime.sg(teleconsult_delivery.receipt_date) if teleconsult_delivery.receipt_date else sg_datetime.now()
                    ),
                    "dispatch_name": (
                        teleconsult_delivery.clinic_account.name
                        if teleconsult_delivery.clinic_account
                        else None
                    ),
                    "dispatch_id": (
                        str(teleconsult_delivery.dispatch_id)
                        if teleconsult_delivery.dispatch_id
                        else None
                    ),
                }
            ]
            teleconsult_delivery.delivery_attempt += 1

    if request.postal_code and teleconsult_delivery.postal != request.postal_code:
        sector_code = request.postal_code[:2]
        zone_response: RetrievePinnacleZoneResponse = (
            retrieve_pinnacle_zone_by_sector_code(sector_code, db)
        )

        # LOGIC TO REVERT STATUS TO PENDING/RETRY WHEN CHANGE FROM NO DELIVERY SERVICE TO DELIVERY SERVICE
        for teleconsult_delivery in teleconsult_deliveries:
            teleconsult_delivery.zone = zone_response.zone
            if teleconsult_delivery.dispatch_history == []:
                teleconsult_delivery.status = (
                    DeliveryStatus.PENDING
                    if zone_response.has_service
                    else DeliveryStatus.NO_DELIVERY_SERVICE
                )
            else:
                teleconsult_delivery.status = (
                    DeliveryStatus.RETRY
                    if zone_response.has_service
                    else DeliveryStatus.NO_DELIVERY_SERVICE
                )

    for teleconsult_delivery in teleconsult_deliveries:
        teleconsult_delivery.zone = (
            request.zone if request.zone else teleconsult_delivery.zone
        )
        teleconsult_delivery.address = (
            request.address if request.address else teleconsult_delivery.address
        )
        teleconsult_delivery.postal = (
            request.postal_code if request.postal_code else teleconsult_delivery.postal
        )
        teleconsult_delivery.number_of_packages = request.number_of_package
        teleconsult_delivery.delivery_date = request.date_of_delivery
        teleconsult_delivery.delivery_attempt = (
            request.number_of_attempt
            if request.number_of_attempt
            else teleconsult_delivery.delivery_attempt
        )

        teleconsult_delivery.status = (
            DeliveryStatus.RETRY
            if teleconsult_delivery.status == DeliveryStatus.FAILED
            else teleconsult_delivery.status
        )
    db.commit()
    return SuccessResp(success=True)

async def dispatch_update_teleconsult_delivery_status_action(request: DispatchUpdateTeleconsultDeliveryStatusRequest, user: SupabaseUser, db: Session, file: UploadFile | None = None):
    teleconsult_delivery = (
        db.query(TeleconsultDelivery)
        .filter(TeleconsultDelivery.id == request.id)
        .first()
    )
    if not teleconsult_delivery:
        raise HTTPException(
            status_code=404,
            detail=f"Teleconsult delivery with id {request.id} not found",
        )

    if (
        teleconsult_delivery.status != DeliveryStatus.PENDING
        and teleconsult_delivery.status != DeliveryStatus.RETRY
    ):
        raise HTTPException(
            status_code=400,
            detail="Teleconsult delivery status is not pending and retry. This is not a valid task.",
        )

    # Determine if there is a delivery_note to be recorded
    delivery_note_key = None
    if not teleconsult_delivery.is_migrant and request.success:
        if not file:
            logging.error(f"Delivery note file was not provided for teleconsult delivery {teleconsult_delivery.id}")
        else:
            delivery_note_key = await upload_delivery_note_action(teleconsult_delivery, file)

    teleconsult_deliveries = (
        get_grouping_teleconsult_deliveries_by_delivery_object_for_updating(
            teleconsult_delivery, db
        )
        if teleconsult_delivery.group_id
        else [teleconsult_delivery]
    )

    for td in teleconsult_deliveries:
        td.receipt_date = sg_datetime.now()
        td.dispatch_id = UUID(user.id) if user.id else None

    if not request.success:
        for td in teleconsult_deliveries:
            td.status = DeliveryStatus.FAILED
        db.commit()
        return SuccessResp(success=True)

    for td in teleconsult_deliveries:
        td.status = DeliveryStatus.SUCCESS
        td.recipient_name = (
            request.recipient_name
            if request.recipient_name
            else td.patient_account.name
        )
        td.is_delivery_note_exists = (
            True if delivery_note_key else False
        )
        td.delivery_note_file_path = delivery_note_key

    db.commit()
    return SuccessResp(success=True)

async def upload_delivery_note_action(teleconsult_delivery: TeleconsultDelivery, file: UploadFile):
    key = f"delivery_note/{teleconsult_delivery.id}.pdf"
    file_bytes = await file.read()
    upload_pdf(SUPABASE_PRIVATE_BUCKET, key, file_bytes)

    return key

def retrieve_delivery_note_action(delivery_note_key: str):
    if not check_is_file_exists_in_s3(delivery_note_key, SUPABASE_PRIVATE_BUCKET):
        raise HTTPException(status_code=404, detail="Delivery note not found")

    return get_blob_data_from_s3(delivery_note_key, SUPABASE_PRIVATE_BUCKET)

def retrieve_delivery_note_action_with_signed_url(delivery_note_key: str) -> SignedURLResponse:
    signed_url = get_signed_url(SUPABASE_PRIVATE_BUCKET, delivery_note_key)
    if not signed_url:
        raise HTTPException(status_code=404, detail="Delivery note not found")
    return signed_url

def logistic_download_delivery_note_action(delivery_note_key: str):
    return download_file_from_s3(delivery_note_key, SUPABASE_PRIVATE_BUCKET)

def logistic_download_delivery_note_by_date_action(date: date, db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(
            TeleconsultDelivery.delivery_date == date,
            TeleconsultDelivery.is_delivery_note_exists == True,
        )
        .all()
    )

    delivery_note_keys = [
        ZipFileRequest(
            key=delivery.delivery_note_file_path,
            filename=f"{delivery.patient_account.sgimed_patient_given_id} - {delivery.patient_account.name}.pdf",
        )
        for delivery in teleconsult_deliveries
        if delivery.delivery_note_file_path
    ]
    return download_files_as_zip(
        delivery_note_keys, SUPABASE_PRIVATE_BUCKET, f"delivery_notes_{date}.zip" if date else "delivery_notes.zip"
    )

def logistic_export_delivery_sheet_action(db: Session, date: Optional[date] = None, is_migrant: Optional[bool] = None):
    # TODO: Should not name variables as library names
    selected_date = date
    qry = db.query(TeleconsultDelivery) \
        .filter(
            TeleconsultDelivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.RETRY, DeliveryStatus.NO_DELIVERY_SERVICE])
        )
    if selected_date:
        qry = qry.filter(TeleconsultDelivery.delivery_date == selected_date)
    if is_migrant is not None:
        qry = qry.filter(TeleconsultDelivery.is_migrant == is_migrant)

    teleconsult_deliveries = qry.options(
            joinedload(TeleconsultDelivery.teleconsult).load_only(Teleconsult.teleconsult_start_time, Teleconsult.queue_number),
            joinedload(TeleconsultDelivery.patient_account).load_only(Account.sgimed_patient_given_id, Account.nric, Account.name, Account.mobile_code, Account.mobile_number),
            joinedload(TeleconsultDelivery.clinic_account).load_only(PinnacleAccount.name),
        ) \
        .all()

    teleconsult_deliveries = sorted(
        teleconsult_deliveries,
        key=lambda x: (
            sg_datetime.sg(x.teleconsult.teleconsult_start_time) if x.teleconsult.teleconsult_start_time else sg_datetime.now()
        ),
    )

    teleconsult_deliveries = grouping_family_teleconsult_deliveries_handler(
        teleconsult_deliveries, db
    )

    headers = [
        "Queue Number",
        "SGIMED Patient ID",
        "Patient Type",
        "Patient Name",
        "Phone Number",
        "Status",
        "Consultation Time",
        "Delivery Date",
        "No. of Packages",
        "Address",
        "Postal",
        "Zone",
    ]

    data_rows = [
        [
            delivery.combined_queue_number,
            delivery.combined_sgimed_patient_id,
            "MW" if delivery.is_migrant else "Private",
            delivery.combined_name,
            delivery.phone_number.replace('+65 ', '') if delivery.phone_number and delivery.phone_number.startswith('+65 ') else delivery.phone_number,
            delivery.status.value,
            sg_datetime.sg(delivery.consultation_date).strftime("%Y-%m-%d %I:%M %p") if delivery.consultation_date else "N/A",
            delivery.delivery_date,
            delivery.number_of_packages if delivery.number_of_packages else "N/A",
            delivery.address,
            delivery.postal,
            delivery.zone.value.title() + (" - Zone F" if delivery.is_migrant_area and delivery.is_migrant else ''),
        ]
        for delivery in teleconsult_deliveries
    ]
    excel_buffer = create_excel_with_styled_header(headers, data_rows)

    # Generate Excel File Name
    filename: str = ''
    if is_migrant is not None:
        filename += 'migrant_worker_' if is_migrant else 'private_patient_'
    filename += f'delivery_sheet_{selected_date.strftime("%Y-%m-%d")}.xlsx' if selected_date else 'upcoming_delivery_sheet.xlsx'

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

def logistic_export_end_day_report_action(date: date, db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(TeleconsultDelivery.delivery_date == date)
        .options(
            joinedload(TeleconsultDelivery.teleconsult),
            joinedload(TeleconsultDelivery.patient_account),
            joinedload(TeleconsultDelivery.clinic_account),
        )
        .all()
    )
    teleconsult_deliveries = sorted(
        teleconsult_deliveries,
        key=lambda x: (
            x.teleconsult.teleconsult_start_time if x.teleconsult.teleconsult_start_time else datetime.now()
        ),
    )

    sorting_priority = {
        DeliveryStatus.SUCCESS.value: 0,
        DeliveryStatus.FAILED.value: 1,
        DeliveryStatus.CANCELLED.value: 2,
        DeliveryStatus.PENDING.value: 3,
        DeliveryStatus.RETRY.value: 4,
        DeliveryStatus.NO_DELIVERY_SERVICE.value: 5,
    }

    teleconsult_deliveries = grouping_family_teleconsult_deliveries_handler(
        teleconsult_deliveries, db
    )

    # teleconsult_deliveries = sorted(
    #     teleconsult_deliveries, key=lambda x: sorting_priority[x.status.value]
    # )
    headers = [
        "Queue Number",
        "SGIMED Patient ID",
        "Patient Type",
        "Patient Name",
        "Phone Number",
        "Status",
        "Consultation Time",
        "Delivery Attempt",
        "Address",
        "Postal",
        "Zone",
        "Dispatch Name",
        "Delivery Time",
    ]

    data_rows = [
        [
            delivery.combined_queue_number,
            delivery.combined_sgimed_patient_id,
            "MW" if delivery.is_migrant else "Private",
            delivery.combined_name,
            delivery.phone_number.replace('+65 ', '') if delivery.phone_number and delivery.phone_number.startswith('+65 ') else delivery.phone_number,
            delivery.status.value.replace("_", " ").title(),
            sg_datetime.sg(delivery.consultation_date).strftime("%Y-%m-%d %I:%M %p") if delivery.consultation_date else "N/A",
            str(delivery.delivery_attempt),
            str(delivery.address),
            str(delivery.postal),
            f"{delivery.zone.value} - Zone F" if delivery.is_migrant_area and delivery.is_migrant else delivery.zone.value,
            (
                delivery.dispatch_name
                if isinstance(delivery, TeleconsultDeliveryFamily)
                else delivery.clinic_account.name if delivery.clinic_account else "N/A"
            ),
            (
                sg_datetime.sg(delivery.receipt_date).strftime("%Y-%m-%d %I:%M %p")
                if delivery.receipt_date and delivery.status == DeliveryStatus.SUCCESS
                else "N/A"
            ),
        ]
        for delivery in teleconsult_deliveries
    ]

    excel_buffer = create_excel_with_styled_header(headers, data_rows)

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=end_day_report_{date}.xlsx"
        },
    )

def logistics_get_drivers_action(db: Session):
    drivers = db.query(PinnacleAccount).filter(PinnacleAccount.role == Role.DISPATCH).all()
    return [DriverFetchingResponse(id=str(driver.id), name=driver.name) for driver in drivers]
