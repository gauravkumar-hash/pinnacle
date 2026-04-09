import time
from sqlalchemy.orm import Session
from models.model_enums import CollectionMethod, TeleconsultStatus, VisitType
from models.payments import PaymentMethod
from models.teleconsult import Teleconsult
from routers.patient.activity import ActivityResp
from routers.patient.teleconsult_family import JoinQueueReq, JoinQueueResp, PrepaymentRateReq, PrepaymentRateResp
from tests.utils_auth import get, login_latest_user, post

def new_user_start_teleconsult():
    '''
    Given: New user starts teleconsult
    When: teleconsult started
    Then: patient record with details updated in SGiMed
    '''
    pass


def test_teleconsult_corporate_code(db: Session):
    '''
    Given: User with corporate code starts teleconsult
    When: teleconsult started
    Then: patient record with details updated in SGiMed
    '''
    token = login_latest_user(db)
    time.sleep(4)
    body = PrepaymentRateReq(code='INS', include_user=True).model_dump_json()
    resp = post('/api/teleconsult/v2/prepayment/rate', body, token)
    resp = PrepaymentRateResp(**resp)
    
    assert resp.code == 'INS'
    
    body = JoinQueueReq(
            include_user=True,
            code='INS',
            branch_id='a478c945-619f-4134-b696-c17a86017c30', # Dakota
            user_allergy=None,
            payment_method=PaymentMethod.CARD_STRIPE,
            collection_method=CollectionMethod.DELIVERY
        ).model_dump_json()
    resp = post('/api/teleconsult/v2/queue/join', body, token)
    resp = JoinQueueResp(**resp)
    
    assert resp.prepayment_required == False
    
    resp = get('/api/activity', token=token)
    resp = ActivityResp(**resp)
    
    assert resp.activity and resp.activity.type == VisitType.TELECONSULT
    teleconsult = db.query(Teleconsult).filter(Teleconsult.id == resp.activity.id).first()
    assert teleconsult and teleconsult.status == TeleconsultStatus.CHECKED_IN

    # TODO: 
    # Login as Doctor
    # Start Teleconsult
    # End Teleconsult
    teleconsult.status = TeleconsultStatus.CHECKED_OUT
    db.commit()

    
