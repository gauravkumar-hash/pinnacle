from datetime import date
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from models import get_db, get_user
from models.model_enums import PhoneCountryCode, SGiMedGender, SGiMedICType, SGiMedLanguage, SGiMedNationality, SGiMedNokRelation
from sqlalchemy.orm import Session
from models.patient import Account, FamilyNok
from repository.family_nok import delete_family_account
from routers.patient.utils import validate_firebase_token, validate_user
from services.family import OngoingStatus, check_ongoing_consults
from utils.auth import id_number_validation
from utils.fastapi import ExceptionCode, HTTPJSONException, SuccessResp
from utils.integrations.sgimed import retrieve_sgimed_patient_id

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class FamilyMember(BaseModel):
    id: str
    name: str
    relation: SGiMedNokRelation

@router.get("/list", response_model=list[FamilyMember])
def get_family(user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    family_members = db.query(FamilyNok).join(FamilyNok.nok_account).filter(FamilyNok.account_id == user.id, FamilyNok.deleted == False).order_by(FamilyNok.created_at).all()
    return [FamilyMember(id=str(member.nok_account.id), name=member.nok_account.name, relation=member.relation) for member in family_members]

class FamilyDetails(BaseModel):
    id_type: SGiMedICType
    nric: str
    date_of_birth: date
    relation: SGiMedNokRelation
    name: str
    gender: SGiMedGender
    nationality: SGiMedNationality
    language: SGiMedLanguage
    secondary_mobile_code: PhoneCountryCode
    secondary_mobile_number: str

@router.get("/details/{id}", response_model=FamilyDetails)
def get_family_details(id: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    family_member = db.query(FamilyNok).join(FamilyNok.nok_account).filter(FamilyNok.account_id == user.id, FamilyNok.nok_id == id, FamilyNok.deleted == False).first()
    if not family_member:
        raise HTTPException(status_code=404, detail="Family member not found")
    
    nok_account = family_member.nok_account
    return FamilyDetails(
        id_type=nok_account.ic_type,
        nric=nok_account.nric,
        date_of_birth=nok_account.date_of_birth,
        relation=family_member.relation,
        name=nok_account.name,
        gender=nok_account.gender,
        nationality=nok_account.nationality,
        language=nok_account.language,
        secondary_mobile_code=nok_account.secondary_mobile_code if nok_account.secondary_mobile_code else PhoneCountryCode.SINGAPORE,
        secondary_mobile_number=nok_account.secondary_mobile_number if nok_account.secondary_mobile_number else '',
    )

@router.delete("/remove/{id}", response_model=SuccessResp)
def remove_family_member(id: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    nok = db.query(FamilyNok).filter(FamilyNok.account_id == user.id, FamilyNok.nok_id == id, FamilyNok.deleted == False).first()
    if not nok:
        raise HTTPException(status_code=404, detail="Family member not found")

    has_ongoing_consult = check_ongoing_consults(db, str(nok.nok_id))
    if has_ongoing_consult == OngoingStatus.TELECONSULT:
        raise HTTPJSONException(
            status_code=400, 
            code=ExceptionCode.INVALID,
            title="Ongoing Teleconsultation",
            message="Unable to delete as there is an ongoing teleconsultation for this family member"
        )
    elif has_ongoing_consult == OngoingStatus.WALKIN_QUEUE:
        raise HTTPJSONException(
            status_code=400, 
            code=ExceptionCode.INVALID,
            title="Ongoing Queue Request",
            message="Unable to delete as there is an ongoing queue request for this family member"
        )

    delete_family_account(db, nok)
    return SuccessResp(success=True)

class VerifyFamilyReq(BaseModel):
    id_type: SGiMedICType
    nric: str
    date_of_birth: date
    relation: SGiMedNokRelation

    @field_validator("id_type", mode="before")
    def validate_id_type(cls, value: str):
        # This is for earlier versions where the id_type used is defined as BLUE IC
        if value == 'BLUE IC':
            return SGiMedICType.BLUE_IC
        return SGiMedICType(value)

    @field_validator("nric")
    def validate_nric(cls, value: str) -> str:
        # Strip whitespace and newlines
        return value.strip()
    
class VerifyFamilyResp(BaseModel):
    is_new_user: bool

@router.post("/verify", response_model=VerifyFamilyResp)
def verify_family(params: VerifyFamilyReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    # ID Validation
    id_type = params.id_type
    id_number = params.nric.upper().strip()
    id_error = id_number_validation(id_type, id_number)
    if id_error:
        raise HTTPException(status_code=400, detail=id_error)
    
    # If there is no existing account for the NRIC, then it is a new user
    nok_account = db.query(Account).filter(Account.nric == id_number).first()
    if not nok_account:
        return VerifyFamilyResp(is_new_user=True)
    
    # If there is already a mobile number, it can no longer be added as a family member
    if nok_account.mobile_number:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID,
            title="Unable to add family member",
            message="Family member is already a registered account user.\n[]()\nIf this was a mistake, kindly call\n[+65 6235 1852](tel:62351852)"
        )        
    
    # if NOK exists, but is linked to another account, then cannot be linked
    nok = db.query(FamilyNok).filter(FamilyNok.nok_id == nok_account.id, FamilyNok.deleted == False).first()
    if nok:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID,
            title="Unable to add family member",
            message=f"Family member is already associated with another account with **ID ending {str(nok.account.nric)[-4:]}**. Remove it from the account first.\n[]()\nIf this was a mistake, kindly call\n[+65 6235 1852](tel:62351852)"
        )

    # If the NOK details do not match, then cannot be linked
    if nok_account.ic_type != id_type or nok_account.date_of_birth != params.date_of_birth:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID,
            title="Unable to add family member",
            message="Family member details do not match the recorded entry.\n[]()\nIf this was a mistake, kindly call\n[+65 6235 1852](tel:62351852)"
        )
    
    # If account exists, nok not linked, and details match, then link the NOK
    record = FamilyNok(
        account_id=user.id,
        nok_id=nok_account.id,
        relation=params.relation,
    )
    db.add(record)
    db.commit()
    return VerifyFamilyResp(is_new_user=False)

class FamilyDetailsReq(BaseModel):
    id_type: SGiMedICType
    nric: str
    date_of_birth: date
    relation: SGiMedNokRelation
    name: str
    gender: SGiMedGender
    nationality: SGiMedNationality
    language: SGiMedLanguage
    # TODO: Interim due to earlier versions setting mobile as optional. Should merge back with FamilyDetails subsequently
    secondary_mobile_code: PhoneCountryCode = PhoneCountryCode.SINGAPORE
    secondary_mobile_number: Optional[str] = None

    @field_validator("id_type", mode="before")
    def validate_id_type(cls, value: str):
        # This is for earlier versions where the id_type used is defined as BLUE IC
        if value == 'BLUE IC':
            return SGiMedICType.BLUE_IC
        return SGiMedICType(value)

    @field_validator("nric")
    def validate_nric(cls, value: str) -> str:
        # Strip whitespace and newlines
        return value.strip()

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        # Strip whitespace and newlines
        return value.strip()

@router.post('/register', response_model=SuccessResp)
def register_family(params: FamilyDetailsReq, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    if not params.secondary_mobile_number:
        raise HTTPException(status_code=400, detail="Mobile number is required")

    # ID Validation
    id_type = params.id_type
    id_number = params.nric.upper().strip()
    id_error = id_number_validation(id_type, id_number)
    if id_error:
        raise HTTPException(status_code=400, detail=id_error)

    # 1. Check if account is not in patient_family and no mobile_number
    # Run through the verification process again to ensure that the family member is not already registered
    verify_family(
        VerifyFamilyReq(
            id_type=id_type, 
            nric=id_number, 
            date_of_birth=params.date_of_birth, 
            relation=params.relation
        ),
        firebase_uid, 
        db
    )
    
    user = get_user(db, firebase_uid)
    if not user:
        logging.error(f"Firebase UID not found in AccountFirebase: {firebase_uid}")
        raise HTTPException(status_code=403, detail="Invalid user")

    # Create Patient Record
    nok = FamilyNok(
        account_id=user.id,
        relation=params.relation,
        nok_account=Account(
            ic_type=id_type,
            nric=id_number,
            date_of_birth=params.date_of_birth,
            name=params.name,
            gender=params.gender,
            nationality=params.nationality,
            language=params.language,
            mobile_code=PhoneCountryCode.SINGAPORE,
            mobile_number='', # No mobile number for linked accounts
            secondary_mobile_code=params.secondary_mobile_code,
            secondary_mobile_number=params.secondary_mobile_number,
            # Update with user's address as well
            residential_postal=user.residential_postal,
            residential_address=user.residential_address,
            residential_unit=user.residential_unit,
            residential_building=user.residential_building,
            postal=user.postal,
            address=user.address,
            unit=user.unit,
            building=user.building,
        )
    )
    
    db.add(nok)
    db.commit()
    retrieve_sgimed_patient_id(db, nok.nok_account)

    return SuccessResp(success=True)
