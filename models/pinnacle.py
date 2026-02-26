from typing import Any, Optional, List, TYPE_CHECKING
from datetime import datetime, date, time, timedelta
import uuid
from models.model_enums import DayOfWeek
from sqlalchemy import ARRAY, Column, ForeignKey, String, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from utils import sg_datetime
from utils.time import is_time_in_range

from .model_enums import BranchType, CollectionMethod, ContentCategory, Role
from . import Base

if TYPE_CHECKING:
    from .walkin import WalkInQueue
    from .teleconsult import Teleconsult
    from .delivery import TeleconsultDelivery

branches_services_assoc_table = Table(
    "pinnacle_branch_services",
    Base.metadata,
    Column("branch_id", ForeignKey("pinnacle_branches.id"), primary_key=True),
    Column("service_id", ForeignKey("pinnacle_services.id", ondelete="CASCADE"), primary_key=True),
)

branches_blockoffs_assoc_table = Table(
    "pinnacle_branch_blockoffs",
    Base.metadata,
    Column("branch_id", ForeignKey("pinnacle_branches.id"), primary_key=True),
    Column("blockoff_id", ForeignKey("pinnacle_blockoffs.id", ondelete="CASCADE"), primary_key=True),
)


class StAndrew(Base):
    __tablename__ = 'pinnacle_sa_records'

    nric: Mapped[str] = mapped_column(primary_key=True)
    comp_code: Mapped[Optional[str]]
    company_name: Mapped[Optional[str]]
    uen: Mapped[Optional[str]]
    employee_no: Mapped[Optional[str]]
    employee_name: Mapped[Optional[str]]
    passport: Mapped[Optional[str]]
    sector: Mapped[Optional[str]]
    pcp_start: Mapped[Optional[str]]
    pcp_end: Mapped[Optional[str]]
    checkup_mwoc: Mapped[Optional[str]]
    status: Mapped[Optional[str]]
    created_date_time: Mapped[Optional[str]]
    termination_date: Mapped[Optional[str]]
    handphone_no: Mapped[Optional[str]]

# This is for Raw Postgres connection to load a large CSV
class StAndrewTemp(Base):
    __tablename__ = 'pinnacle_sa_records_temp'

    nric: Mapped[str] = mapped_column(primary_key=True)
    comp_code: Mapped[Optional[str]]
    company_name: Mapped[Optional[str]]
    uen: Mapped[Optional[str]]
    employee_no: Mapped[Optional[str]]
    employee_name: Mapped[Optional[str]]
    passport: Mapped[Optional[str]]
    sector: Mapped[Optional[str]]
    pcp_start: Mapped[Optional[str]]
    pcp_end: Mapped[Optional[str]]
    checkup_mwoc: Mapped[Optional[str]]
    status: Mapped[Optional[str]]
    created_date_time: Mapped[Optional[str]]
    termination_date: Mapped[Optional[str]]
    handphone_no: Mapped[Optional[str]]

# This is for Raw Postgres connection to load a large CSV
class StAndrewMetadata(Base):
    __tablename__ = 'pinnacle_sa_records_metadata'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    last_updated: Mapped[datetime]
    total_records: Mapped[int]
    imported_records: Mapped[Optional[int]]
    insert_diff: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    update_diff: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    delete_diff: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    
class PinnacleAccount(Base):
    __tablename__ = "pinnacle_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supabase_uid: Mapped[str]
    sgimed_id: Mapped[Optional[str]] # Used for doctors to reference the relevant id
    branch_id: Mapped[Optional[str]] = mapped_column(ForeignKey('pinnacle_branches.id'), index=True)
    name: Mapped[str]
    email: Mapped[str] # Used for login
    role: Mapped[Role]
    push_token: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    enable_notifications: Mapped[bool] = mapped_column(server_default='false')
    deleted: Mapped[bool] = mapped_column(server_default='false')
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
    branch: Mapped["Branch"] = relationship("Branch", back_populates="accounts")
    teleconsults: Mapped[list["Teleconsult"]] = relationship(back_populates="doctor", foreign_keys="Teleconsult.doctor_id")
    teleconsult_deliveries: Mapped[list["TeleconsultDelivery"]] = relationship(back_populates="clinic_account")

class Branch(Base):
    __tablename__ = 'pinnacle_branches'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sgimed_branch_id: Mapped[Optional[str]] = mapped_column(index=True) # UUID to relate branch record to SGIMED 
    name: Mapped[str] 
    address: Mapped[Optional[str]]
    phone: Mapped[Optional[str]]
    whatsapp: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
    url: Mapped[Optional[str]]
    image_url: Mapped[Optional[str]]
    category: Mapped[str] # North, Central, East, West
    walk_in_curr_queue_number: Mapped[Optional[str]]
    sgimed_calendar_id: Mapped[Optional[str]]
    sgimed_appointment_type_id: Mapped[Optional[str]]  # Appointment type linked to calendar
    branch_type: Mapped[BranchType]

    # Boolean Flags
    has_delivery_operating_hours: Mapped[bool] = mapped_column(server_default='false')
    hidden: Mapped[bool] = mapped_column(server_default='false')

    deleted: Mapped[bool] = mapped_column(server_default='false') # Branch should never by deleted
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    walkin_queues: Mapped[list["WalkInQueue"]] = relationship(back_populates="branch")
    operating_hours: Mapped[list["OperatingHour"]] = relationship(back_populates="branch")
    accounts: Mapped[list["PinnacleAccount"]] = relationship(back_populates="branch")
    teleconsults: Mapped[list["Teleconsult"]] = relationship(back_populates="branch")
    services: Mapped[list["Service"]] = relationship(secondary=branches_services_assoc_table)
    blockoffs: Mapped[list["Blockoff"]] = relationship(secondary=branches_blockoffs_assoc_table, back_populates="branches")

    # Checking if holiday, day = Day.ph else day is enum Monday - Sunday
    def get_operating_hours(self, db: Any) -> Optional["OperatingHour"]:
        curr_dt = sg_datetime.now()
        holiday = db.query(PublicHoliday).filter(PublicHoliday.date == curr_dt.date()).first()
        day = DayOfWeek.PUBLIC_HOLIDAY if holiday else DayOfWeek[curr_dt.strftime("%A").upper()]
        # Fetch Operating Hours
        operating_hours = db.query(OperatingHour).filter(
            OperatingHour.branch_id == self.id,
            OperatingHour.day == day
        ).all()
        
        # Loop through all possible operating hours for the day
        # There will be multiple operating hours for each day
        # If now not within operating hour, check the next operating hour
        # If now is within operating hour, create queue reqeust and exit loop
        for hr in operating_hours:
            if not is_time_in_range(curr_dt, hr.start_time, hr.end_time, hr.cutoff_time):
                continue
            
            return hr

        return None

    def get_dayofweek(self, db: Session, curr_dt: datetime) -> DayOfWeek:
        curr_date = curr_dt.date()
        record = db.query(PublicHoliday).filter(PublicHoliday.date == curr_date).first()
        if record:
            return DayOfWeek.PUBLIC_HOLIDAY
        
        return list(DayOfWeek)[curr_date.weekday()]

    def is_operating(self, db: Session, curr_dt: datetime, mode: CollectionMethod):
        curr_day = self.get_dayofweek(db, curr_dt)
        curr_date = curr_dt.date()
        curr_time = curr_dt.time()
        
        # For now Open and Pickup uses the same set of operating hours
        if self.has_delivery_operating_hours == False or mode == CollectionMethod.PICKUP or mode == CollectionMethod.WALKIN:
            operating = db.query(OperatingHour).filter(
                    OperatingHour.branch_id == self.id,
                    OperatingHour.day == curr_day,
                    OperatingHour.start_time <= curr_time,
                    OperatingHour.end_time > curr_time,
                ).first()
        else:
            operating = db.query(DeliveryOperatingHour).filter(
                    DeliveryOperatingHour.branch_id == self.id,
                    DeliveryOperatingHour.day == curr_day,
                    DeliveryOperatingHour.start_time <= curr_time,
                    DeliveryOperatingHour.end_time > curr_time,
                ).first()
            
        # If there is cutoff_time, check if it is still operating
        if operating and operating.cutoff_time > 0:
            if (curr_dt + timedelta(minutes=operating.cutoff_time)).time() > operating.end_time:
                operating = None

        # If branch is operating, check if there is a blockoff
        if operating:
            blockoff = (
                db
                    .query(Blockoff)
                    .join(Blockoff.branches)
                    .filter(
                        Branch.id == self.id,
                        Blockoff.date == curr_date,
                        Blockoff.start_time <= curr_time,
                        Blockoff.end_time > curr_time,
                        Blockoff.enabled == True,
                        Blockoff.deleted == False
                    )
                    .first()
            )
            if blockoff:
                return None

        return operating

    def get_next_operating_hour(self, db: Session, next_dt: datetime, mode: CollectionMethod):
        next_day = self.get_dayofweek(db, next_dt)
        if self.has_delivery_operating_hours == False or mode == CollectionMethod.PICKUP or mode == CollectionMethod.WALKIN:
            next_operating_hours = db.query(OperatingHour).filter(
                OperatingHour.branch_id == self.id,
                OperatingHour.day == next_day,
                OperatingHour.start_time > next_dt.time(),
            ).all()
        else:
            next_operating_hours = db.query(DeliveryOperatingHour).filter(
                DeliveryOperatingHour.branch_id == self.id,
                DeliveryOperatingHour.day == next_day,
                DeliveryOperatingHour.start_time > next_dt.time(),
            ).all()

        for next_operating in next_operating_hours:
            operating = self.is_operating(db, datetime.combine(next_dt.date(), next_operating.start_time), mode)
            if operating:
                return operating
        
        return None

class Service(Base):
    __tablename__ = 'pinnacle_services'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label: Mapped[str]
    sgimed_branch_id: Mapped[str]
    sgimed_appointment_type_id: Mapped[str]
    is_for_visit: Mapped[bool]
    is_for_appointment: Mapped[bool]
    is_for_telemed: Mapped[bool]
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class DeliveryOperatingHour(Base):
    __tablename__ = 'pinnacle_branches_delivery_operating_hours'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey('pinnacle_branches.id'), index=True)
    day: Mapped[DayOfWeek]
    start_time: Mapped[time]
    end_time: Mapped[time]
    cutoff_time: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    branch: Mapped["Branch"] = relationship() # back_populates="operating_hours")

class OperatingHour(Base):
    __tablename__ = 'pinnacle_branches_operating_hours'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey('pinnacle_branches.id'), index=True)
    day: Mapped[DayOfWeek]
    start_time: Mapped[time]
    end_time: Mapped[time]
    cutoff_time: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    branch: Mapped["Branch"] = relationship(back_populates="operating_hours")

class PublicHoliday(Base):
    __tablename__ = "pinnacle_public_holidays"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date]
    remarks: Mapped[Optional[str]]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
class Blockoff(Base):
    __tablename__ = "pinnacle_blockoffs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date]
    start_time: Mapped[time] 
    end_time: Mapped[time] 
    enabled: Mapped[bool] = mapped_column(server_default='true')
    deleted: Mapped[bool] = mapped_column(server_default='false')
    allow_toggle: Mapped[bool] = mapped_column(server_default='false')
    created_by: Mapped[str]
    remarks: Mapped[Optional[str]]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    branches: Mapped[List["Branch"]] = relationship(secondary=branches_blockoffs_assoc_table, back_populates="blockoffs")

class Content(Base):
    __tablename__ = "pinnacle_content"
    
    id: Mapped[str] = mapped_column(primary_key=True)
    category: Mapped[ContentCategory]
    title: Mapped[str]
    content: Mapped[str]
    sort_order: Mapped[int]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
