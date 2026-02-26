from sqlalchemy.orm import Session
from models.patient import Account, FamilyNok
from utils.integrations.sgimed import delete_patient_nok

def get_patients(db: Session, user: Account, include_user: bool, family_ids: list[str]):
    '''
    Retreive all the patients required for the prepayment rate
    '''
    patients: list[Account] = []
    if include_user:
        patients.append(user)
    
    if family_ids:
        # Ensure that all the patients are valid family members
        family_accs = get_family_accounts(db, user, family_ids)
        if len(family_accs) != len(family_ids):
            return None
            
        patients += family_accs
    return patients

def get_family_accounts(db: Session, user: Account, patient_ids: list[str]):
    records = db.query(FamilyNok).join(FamilyNok.nok_account).filter(
            FamilyNok.account_id == user.id,
            FamilyNok.nok_id.in_(patient_ids),
            FamilyNok.deleted == False
        ).all()
     
    return [r.nok_account for r in records]
    
def delete_family_account(db: Session, nok: FamilyNok):
    '''
    1. Delete from SGiMed if relationship is present
    2. Delete from database
    '''
    # Deleting relationship with nok_id present
    if nok.sgimed_nok_id:
        delete_patient_nok(nok)
        nok.sgimed_nok_id = None
    # Update database as deleted
    nok.deleted = True
    db.commit()
