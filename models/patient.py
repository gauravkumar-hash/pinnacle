from typing import Any, Optional, List, TYPE_CHECKING
import uuid
from datetime import datetime, date
from sqlalchemy import ForeignKey, null
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from .model_enums import FirebaseLoginType, SGiMedICType, SGiMedGender, SGiMedNationality, SGiMedLanguage, SGiMedMaritalStatus, PhoneCountryCode, SGiMedNokRelation
from . import Base
from .payments import PaymentMethod

if TYPE_CHECKING:
    from .teleconsult import Teleconsult
    from .walkin import WalkInQueue
    from .appointment import Appointment
    from .payments import Payment, Invoice, PaymentToken
    from .delivery import TeleconsultDelivery

class Account(Base):
    __tablename__ = "patient_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Mapped based on SGiMed
    sgimed_patient_id: Mapped[Optional[str]] = mapped_column(unique=True, index=True)
    sgimed_patient_given_id: Mapped[Optional[str]]
    sgimed_auth_code: Mapped[Optional[str]]
    sgimed_synced: Mapped[bool] = mapped_column(server_default='false') # Toggle to False whenever the profile is updated. Will be True once synced with SGiMed
    # Fields for New Users
    ic_type: Mapped[SGiMedICType]
    nric: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    gender: Mapped[SGiMedGender]
    date_of_birth: Mapped[date]
    nationality: Mapped[SGiMedNationality] # Reference SGiMed Nationality List
    language: Mapped[SGiMedLanguage] # Reference SGiMed Language List
    sgimed_diff: Mapped[Optional[dict[str, Any]]]
    # Fields for Existing Users
    ## mobile = mobile_code + mobile_number
    mobile_code: Mapped[PhoneCountryCode]
    mobile_number: Mapped[str]
    ## Secondary Contact
    secondary_mobile_code: Mapped[Optional[PhoneCountryCode]]
    secondary_mobile_number: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
    marital_status: Mapped[Optional[SGiMedMaritalStatus]]
    country: Mapped[Optional[str]] # Reference SGiMed Country list
    
    postal: Mapped[Optional[str]]
    address: Mapped[Optional[str]]
    unit: Mapped[Optional[str]]
    building: Mapped[Optional[str]]
    
    residential_postal: Mapped[Optional[str]]
    residential_address: Mapped[Optional[str]]
    residential_unit: Mapped[Optional[str]]
    residential_building: Mapped[Optional[str]]

    allergy: Mapped[Optional[str]]

    # Stripe User Account
    stripe_id: Mapped[Optional[str]]
    # Default Payments
    default_payment_method: Mapped[Optional[PaymentMethod]]
    default_payment_id: Mapped[Optional[str]]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    firebase_auths: Mapped[List["AccountFirebase"]] = relationship(back_populates="account")
    payments: Mapped[List["Payment"]] = relationship(back_populates="account")
    teleconsults: Mapped[List["Teleconsult"]] = relationship(back_populates="account", foreign_keys='Teleconsult.account_id')
    walkins: Mapped[List["WalkInQueue"]] = relationship(back_populates="account", foreign_keys='WalkInQueue.account_id')
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="account")
    family_members: Mapped[List["FamilyNok"]] = relationship(
        back_populates="account",
        foreign_keys='FamilyNok.account_id',
        primaryjoin="and_(FamilyNok.account_id == Account.id, FamilyNok.deleted == False)"
    )
    parent_nok: Mapped[Optional["FamilyNok"]] = relationship(
        back_populates="nok_account",
        foreign_keys='FamilyNok.nok_id',
        primaryjoin="and_(FamilyNok.nok_id == Account.id, FamilyNok.deleted == False)"
    )
    payment_tokens: Mapped[List["PaymentToken"]] = relationship(back_populates="account")
    teleconsult_deliveries: Mapped[List["TeleconsultDelivery"]] = relationship(back_populates="patient_account")
    yuu_link: Mapped[Optional["AccountYuuLink"]] = relationship(
        back_populates="account",
        primaryjoin="and_(AccountYuuLink.account_id == Account.id, AccountYuuLink.deleted == False)"
    )

    # documents: Mapped[List["Document"]] = relationship(foreign_keys='Document.sgimed_patient_id')

    def get_linked_account_ids(self):
        return [str(self.id)] + [str(family_member.nok_id) for family_member in self.family_members]

    def get_linked_sgimed_patient_ids(self):
        return [self.sgimed_patient_id] + [family_member.nok_account.sgimed_patient_id for family_member in self.family_members]

    def calculate_age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    def get_address(self):
        full_address = []
        if self.address:
            full_address.append(self.address)
        if self.building:
            full_address.append(self.building)
        if self.unit:
            full_address.append(self.unit)
        if self.postal:
            full_address.append(self.postal)
    
        return ", ".join(full_address)
    
    def get_address_without_postal(self):
        full_address = []
        if self.address:
            full_address.append(self.address)
        if self.building:
            full_address.append(self.building)
        if self.unit:
            full_address.append(self.unit)
    
        return ", ".join(full_address)

    def get_residential_address(self):
        full_address = []
        if self.residential_address:
            full_address.append(self.residential_address)
        if self.residential_building:
            full_address.append(self.residential_building)
        if self.residential_unit:
            full_address.append(self.residential_unit)
        if self.residential_postal:
            full_address.append(self.residential_postal)
    
        return ", ".join(full_address)

    def update_auth_code(self, dob: Optional[date] = None):
        dob = self.date_of_birth if not dob else dob
        self.sgimed_auth_code = str(self.nric[-4:] + dob.strftime("%d%m%y")).upper()

    def reset_diff(self):
        self.sgimed_diff = null()

class AccountFirebase(Base):
    __tablename__ = "patient_firebase_auths"
    # Composite keys
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), primary_key=True, unique=True, index=True)
    firebase_uid: Mapped[str] = mapped_column(primary_key=True, unique=True, index=True)
    push_token: Mapped[Optional[str]]
    fcm_token: Mapped[Optional[str]]
    apn_token: Mapped[Optional[str]]
    device: Mapped[Optional[str]]
    login_type: Mapped[FirebaseLoginType]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="firebase_auths")

class FamilyNok(Base):
    __tablename__ = "patient_family"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sgimed_nok_id: Mapped[Optional[str]]
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    nok_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    relation: Mapped[SGiMedNokRelation]
    deleted: Mapped[bool] = mapped_column(server_default='false')

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
    account: Mapped["Account"] = relationship(back_populates='family_members', foreign_keys=[account_id])
    nok_account: Mapped["Account"] = relationship(back_populates='parent_nok', foreign_keys=[nok_id])


class AccountYuuLink(Base):
    __tablename__ = "patient_account_yuu_links"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    tomo_id: Mapped[str] = mapped_column(index=True) # Yuu member ID (8 digits)
    user_identifier: Mapped[str]  # Yuu user unique identifier
    linked_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted: Mapped[bool] = mapped_column(server_default='false')
    deleted_at: Mapped[Optional[datetime]]
    
    # Relationships
    account: Mapped["Account"] = relationship(back_populates="yuu_link")

class YuuTransactionLog(Base):
    __tablename__ = "yuu_transaction_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    tomo_id: Mapped[str]
    sgimed_invoice_id: Mapped[str]
    sgimed_invoice_dict: Mapped[dict[str, Any]]
    transaction_id: Mapped[str]
    yuu_payload: Mapped[dict[str, Any]]
    success: Mapped[bool] = mapped_column(server_default='false')
    refund_details: Mapped[Optional[dict[str, Any]]] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
    # Relationships
    account: Mapped["Account"] = relationship(foreign_keys=[account_id])
