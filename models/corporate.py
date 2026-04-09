from enum import Enum
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from models.model_enums import SGiMedICType

from . import Base

class CorpAuthorisation(str, Enum):
    BLOCK_EDOCS = "block_edocs"

class CorporateAuth(Base):
    __tablename__ = "corporate_authorisations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str]
    permission: Mapped[CorpAuthorisation]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    
class CorporateUser(Base):
    __tablename__ = "corporate_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ic_type: Mapped[SGiMedICType] = mapped_column(index=True)
    nric: Mapped[str] = mapped_column(index=True)
    code: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
