import logging
from typing import Any
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session, DeclarativeBase, sessionmaker
from config import POSTGRES_POOL_SIZE, POSTGRES_URL
from threading import Lock

class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSON,
        list[dict[str, Any]]: JSON,
        list[str]: JSON,
    }

    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def update_vars(self, update_dict):
        for key, value in update_dict.items():
            setattr(self, key, value)

from .patient import *
from .document import *
from .payments import *
from .pinnacle import *
from .walkin import *
from .teleconsult import *
from .appointment import *
from .backend import *
from .corporate import *
from .sgimed import *
from .delivery import *

# Connect to the PostgreSQL database using SQLAlchemy
engine = create_engine(
    POSTGRES_URL, 
    pool_size=POSTGRES_POOL_SIZE, 
    max_overflow=2, 
    pool_pre_ping=True, 
    pool_recycle=300, 
    pool_use_lifo=True,
    # echo=True
)
# from sqlalchemy.pool import NullPool
# engine = create_engine(POSTGRES_URL, client_encoding='utf8', poolclass=NullPool, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# SQLAlchemyInstrumentor().instrument(engine=engine)
# Base.metadata.create_all(bind=engine)

# Global variables for tracking active connections and session times
active_db_conn = {
    "connections": {},
    "min_time": 1.0,
    "max_time": 0.0
}
lock = Lock()
import time

# Not sure if this will fix database disconnect issues
# @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def get_db():
    global active_db_conn, min_db_time, max_db_time
    # Generate a unique connection ID and start time
    connection_id = uuid.uuid4()
    start_time = time.time()
    with lock:
        active_db_conn['connections'][connection_id] = sg_datetime.now()

    # Actual Session
    logging.info(f"Starting get_db. Active connections: {len(active_db_conn)}. Pool: {engine.pool.status()}")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

    # Compute the session duration
    end_time = time.time()
    duration = end_time - start_time
    # Decrement the active connections count and log session duration statistics
    with lock:
        del active_db_conn['connections'][connection_id]
        active_db_conn['max_time'] = max(active_db_conn['max_time'], duration)
        active_db_conn['min_time'] = min(active_db_conn['min_time'], duration)

def get_user(db: Session, firebase_uid: str):
    record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
    if not record:
        return None
    return record.account
