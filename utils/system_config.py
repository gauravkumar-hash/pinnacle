import logging
from typing import Literal, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import SystemConfig, Account, Teleconsult, Branch
from models.model_enums import CollectionMethod, PatientType
import json

def get_config_value(db: Session, key: str, default=None) -> Optional[bool | int | float | str | dict | list]:
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        return default
        
    if config.value_type == "boolean":
        return config.value.lower() == "true"
    elif config.value_type == "integer":
        return int(config.value)
    elif config.value_type == "float":
        return float(config.value)
    elif config.value_type == "json":
        return json.loads(config.value)
    return config.value  # string

def update_config_value(db: Session, key: str, value: bool | int | float | str | dict | list, value_type: Optional[str] = None, description: Optional[str] = None, category: Optional[str] = None):
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        raise ValueError(f"Config with key {key} not found")
    
    # Convert value to string for storage
    str_value = str(value)
    if isinstance(value, bool):
        str_value = str(value).lower()
        value_type = value_type or "boolean"
    elif isinstance(value, int):
        value_type = value_type or "integer"
    elif isinstance(value, float):
        value_type = value_type or "float"
    elif isinstance(value, (dict, list)):
        str_value = json.dumps(value)
        value_type = value_type or "json"
    else:
        value_type = value_type or "string"

    config.value = str_value
    if value_type:
        config.value_type = value_type
    if description:
        config.description = description
    if category:
        config.category = category

    db.commit()
    return config

def is_test_user(db: Session, user: Account):
    test_users: Optional[list[str]] = get_config_value(db, "TEST_USERS") # type: ignore
    if not test_users:
        return False
    return user.nric in test_users

class PTTelemedRouting(BaseModel):
    """
    Configuration model for PT teleconsult routing.
    
    Attributes:
        state: The state of the PT routing feature ('off', 'test', 'on')
        sgimed_branch_id: The SGiMed branch ID to route to
        delivery_sgimed_appointment_type_id: Appointment type ID for delivery method
        pickup_sgimed_appointment_type_id: Dictionary mapping branch IDs to pickup appointment type IDs
    """
    state: Literal["off", "test", "on"] = "off"
    sgimed_branch_id: Optional[str] = None
    delivery_sgimed_appointment_type_id: Optional[str] = None
    pickup_sgimed_appointment_type_id: dict[str, str] = {}

def get_telemed_app_branch(db: Session, user: Account, collection_method: CollectionMethod, branch_id: Optional[str] = None):
    # If collection method is not delivery, return the branch id
    if collection_method != CollectionMethod.DELIVERY:
        return db.query(Branch).filter(Branch.id == branch_id).first()

    # If collection method is delivery, return the branch id from the routing config
    pt_telemed_routing: Optional[dict] = get_config_value(db, "TELECONSULT_BRANCH_ROUTING") # type: ignore
    if pt_telemed_routing:
        routing = PTTelemedRouting(**pt_telemed_routing)
        if routing.state == "on" or (routing.state == "test" and is_test_user(db, user)):
            return db.query(Branch).filter(Branch.sgimed_branch_id == routing.sgimed_branch_id).first()

    # If no routing config, return based on the fallback branch id
    return db.query(Branch).filter(Branch.id == branch_id).first()

def get_delivery_require_branch_picker(db: Session, user: Account):
    pt_telemed_routing: Optional[dict] = get_config_value(db, "TELECONSULT_BRANCH_ROUTING") # type: ignore
    if pt_telemed_routing:
        routing = PTTelemedRouting(**pt_telemed_routing)
        if routing.state == "on" or (routing.state == "test" and is_test_user(db, user)):
            return ['pickup']
    return ['delivery', 'pickup']

def get_sgimed_telemed_routing_params(db: Session, teleconsult: Teleconsult):
    pt_telemed_routing: Optional[dict] = get_config_value(db, "TELECONSULT_BRANCH_ROUTING") # type: ignore

    if pt_telemed_routing and teleconsult.patient_type == PatientType.PRIVATE_PATIENT:
        routing = PTTelemedRouting(**pt_telemed_routing)
        if not routing.sgimed_branch_id:
            logging.error("PT Telemed Routing is on, but no SGiMed branch id found")
        elif routing.state == "on" or (routing.state == "test" and is_test_user(db, teleconsult.account)):
            # Delivery PT Routing
            if teleconsult.collection_method == CollectionMethod.DELIVERY:
                if not routing.delivery_sgimed_appointment_type_id:
                    logging.error("Delivery PT Routing is on, but no delivery appointment type id found")
                else:
                    return routing.sgimed_branch_id, routing.delivery_sgimed_appointment_type_id
            # Pickup PT Routing
            else:
                pickup_sgimed_appointment_id = routing.pickup_sgimed_appointment_type_id.get(teleconsult.branch.sgimed_branch_id, None)
                if not pickup_sgimed_appointment_id:
                    logging.error(f"Pickup PT Routing is on, but no pickup appointment type id found for branch: {teleconsult.branch.sgimed_branch_id}")
                else:
                    return routing.sgimed_branch_id, pickup_sgimed_appointment_id

    # Default Routing
    return teleconsult.branch.sgimed_branch_id, teleconsult.get_appointment_type_id(db)

class TeleconsultWarningMessage(BaseModel):
    state: Literal["on", "off"]
    display_after_secs: int
    message: str

def get_teleconsult_warning_message(db: Session):
    warning_message: Optional[dict] = get_config_value(db, "TELECONSULT_WARNING_MESSAGE") # type: ignore
    if warning_message:
        return TeleconsultWarningMessage(**warning_message)
    return None
