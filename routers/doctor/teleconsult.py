from datetime import date
import time
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
import jwt
from pydantic import BaseModel
from sqlalchemy import or_
from routers.doctor.actions.teleconsult import get_ended_teleconsults_with_doctor_id, get_teleconsult_with_doctor_id, get_teleconsult_with_id, get_teleconsults
from routers.doctor.actions.webhook import TeleconsultResponse, UserResponse
from models import get_db, Teleconsult, TeleconsultStatus, PinnacleAccount, Role, PatientType, SGiMedICType
from routers.patient.actions.teleconsult_utils import get_grouped_teleconsults, user_triggered_queue_status_change
from utils.fastapi import SuccessResp
from utils.supabase_auth import SupabaseUser, get_doctor_or_superadmin
from config import ZOOM_APP_KEY, ZOOM_APP_SECRET
from utils import sg_datetime
from sqlalchemy.orm import Session

router = APIRouter(dependencies=[Depends(get_doctor_or_superadmin)])

# Teleconsult Endponts
@router.get("/teleconsults/ongoing", response_model=Optional[TeleconsultResponse])
async def read_ongoing_teleconsult(current_user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    return get_teleconsult_with_doctor_id(db, current_user.id)

@router.get("/teleconsults", response_model=list[TeleconsultResponse])
async def read_teleconsults(current_user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    account = db.query(PinnacleAccount).filter(PinnacleAccount.id == current_user.id).first()
    if not account or 'appstore' in account.email:
        return []
    
    return get_teleconsults(db)

@router.get("/teleconsults/ended", response_model=list[TeleconsultResponse])
def read_ended_teleconsults_with_doctor_id(date: date, current_user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    return get_ended_teleconsults_with_doctor_id(db, current_user.id, date)

test_record = 'test-teleconsult-record'

@router.get("/teleconsults/{id}", response_model=TeleconsultResponse)
async def read_teleconsults_by_id(id: str, db: Session = Depends(get_db)):
    if id == test_record:
        return TeleconsultResponse(
            id=test_record,
            patient_type=PatientType.PRIVATE_PATIENT,
            status=TeleconsultStatus.CHECKED_IN,
            queue_number="T001",
            checkin_time=sg_datetime.now(),
            branch_name="Test Branch",
            user=UserResponse(
                name="Test Patient",
                ic_type=SGiMedICType.PINK_IC,
                nric="S1234567A"
            )
        )
    resp = get_teleconsult_with_id(db, id)
    if not resp:
        raise HTTPException(status_code=404, detail="No teleconsult found")
    return resp

# Zoom Related Endpoints

class TeleconsultRequest(BaseModel):
    teleconsult_id: str

class VideoParams(BaseModel):
    id: str

class VideoResp(BaseModel):
    sessionName: str
    token: str
    userName: str
    sessionIdleTimeoutMins: int
    audioOptions: dict
    videoOptions: dict

def create_video_token(teleconsult_id: str):
    session_name = teleconsult_id
    user_name = "Doctor"

    def get_token():
        try:
            iat = int(time.time()) - 60  # 1 minute before
            exp = iat + 60 * 60 * 1  # 1 hour expiry
            payload = {
                'app_key': ZOOM_APP_KEY,
                'version': 1,
                # 'user_identity': user.name,
                'iat': iat,
                'exp': exp,
                'tpc': session_name,
                'role_type': 1,
                'cloud_recording_option': 1,
            }

            token = jwt.encode(
                payload,
                ZOOM_APP_SECRET,
                algorithm='HS256'
            )
            return token
        except Exception as e:
            print(e)
            return None

    token = get_token()
    if not token:
        raise HTTPException(status_code=500, detail="Failed to generate token")

    return VideoResp(
        sessionName=session_name,
        # sessionPassword="",
        token=token,
        userName=user_name,
        audioOptions={"connect": True, "mute": False,
                      "autoAdjustSpeakerVolume": False},
        videoOptions={"localVideoOn": True},
        sessionIdleTimeoutMins=10,
    )

@router.get("/start-test-session", response_model=VideoResp)
async def start_test_session():
    return create_video_token("test")

@router.post("/start-session", response_model=VideoResp)
async def start_session(request: TeleconsultRequest, background_tasks: BackgroundTasks, current_user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    # Test record - skip all validation and database operations
    if request.teleconsult_id == test_record:
        return create_video_token(test_record)

    record = db.query(Teleconsult).filter(Teleconsult.id == request.teleconsult_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    if record.status == TeleconsultStatus.CONSULT_START:
        raise HTTPException(status_code=400, detail="Consultation already started")

    doctor = db.query(PinnacleAccount).filter(PinnacleAccount.role == Role.DOCTOR, PinnacleAccount.id == current_user.id).first()
    if not doctor or 'appstore' in doctor.email:
        raise HTTPException(status_code=400, detail="This account cannot start a teleconsultation call")

    # Only the same doctor can start the call again
    if record.doctor_id and record.doctor_id != doctor.id:
        raise HTTPException(status_code=400, detail="Already assigned to a different doctor")

    curr_time = sg_datetime.now()
    teleconsults = get_grouped_teleconsults(db, record)
    for teleconsult in teleconsults:
        teleconsult.doctor_id = doctor.id
        teleconsult.status = TeleconsultStatus.CONSULT_START
        teleconsult.queue_status = "Doctor has started the call"
        teleconsult.teleconsult_start_time = curr_time

    db.commit()
    for teleconsult in teleconsults:
        background_tasks.add_task(user_triggered_queue_status_change, str(teleconsult.id))

    # Create a zoom room
    session_name = str(record.group_id if record.group_id else record.id)
    print(f"Doctor Zoom Room: {session_name}")
    return create_video_token(session_name)
    # output_response = get_teleconsult_with_id(db, request.teleconsult_id)


@router.post("/resume-session", response_model=VideoResp)
async def resume_session(request: TeleconsultRequest, current_user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(Teleconsult.id == request.teleconsult_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    if str(record.doctor_id) != current_user.id:
        raise HTTPException(status_code=400, detail="Already assigned to a different doctor")
    if record.status != TeleconsultStatus.CONSULT_START:
        raise HTTPException(status_code=400, detail="Consultation is not started yet.")

    # Create a zoom room
    session_name = str(record.group_id if record.group_id else record.id)
    print(f"Doctor Zoom Room: {session_name}")
    return create_video_token(session_name)

@router.post("/leave-session", response_model=SuccessResp)
async def leave_session(request: TeleconsultRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(Teleconsult.id == request.teleconsult_id, Teleconsult.status == TeleconsultStatus.CONSULT_START).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    teleconsults = get_grouped_teleconsults(db, record)
    for teleconsult in teleconsults:
        if teleconsult.status == TeleconsultStatus.CONSULT_START:
            teleconsult.teleconsult_end_time = sg_datetime.now()
    db.commit()

    return SuccessResp(success=True)

@router.post("/end-session", response_model=SuccessResp)
async def end_session(request: TeleconsultRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(Teleconsult.id == request.teleconsult_id, Teleconsult.status == TeleconsultStatus.CONSULT_START).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    teleconsults = get_grouped_teleconsults(db, record)
    for teleconsult in teleconsults:
        if teleconsult.status == TeleconsultStatus.CONSULT_START:
            teleconsult.status = TeleconsultStatus.CONSULT_END
            teleconsult.queue_status = "Preparing prescription and MC (if any)"
        teleconsult.teleconsult_end_time = sg_datetime.now()
    db.commit()

    for teleconsult in teleconsults:
        if teleconsult.status == TeleconsultStatus.CONSULT_END:
            background_tasks.add_task(user_triggered_queue_status_change, str(teleconsult.id))

    return SuccessResp(success=True)

@router.post("/cancel-session", response_model=SuccessResp)
async def cancel_session(request: TeleconsultRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(Teleconsult.id == request.teleconsult_id, Teleconsult.status == TeleconsultStatus.CONSULT_START).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    teleconsults = get_grouped_teleconsults(db, record)
    for teleconsult in teleconsults:
        teleconsult.doctor_id = None
        teleconsult.status = TeleconsultStatus.MISSED
        teleconsult.queue_status = "You may wish to join the queue again."
    db.commit()
    for teleconsult in teleconsults:
        background_tasks.add_task(user_triggered_queue_status_change, str(teleconsult.id))

    return SuccessResp(success=True)

class ElapsedTimeResp(BaseModel):
    elapsed_time: int

@router.get("/elapsed-time/{id}", response_model=ElapsedTimeResp)
async def get_elapsed_time(id: str, db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(
        or_(Teleconsult.id == id, Teleconsult.group_id == id),
        Teleconsult.status == TeleconsultStatus.CONSULT_START,
        Teleconsult.teleconsult_join_time != None
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    # Calculate elapsed time in seconds since teleconsult_start_time
    elapsed_time = 0
    if record.teleconsult_join_time:
        elapsed_time = int((sg_datetime.now() - sg_datetime.sg(record.teleconsult_join_time)).total_seconds())
    
    return ElapsedTimeResp(elapsed_time=elapsed_time)
