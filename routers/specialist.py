from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session,joinedload
from typing import List
from models.specialist import Specialist
from schemas.specialist import SpecialistCreate, SpecialistUpdate, SpecialistResponse
from models import get_db

router = APIRouter(prefix="/specialists", tags=["Specialists"])


@router.get("/", response_model=List[SpecialistResponse])
def get_all(db: Session = Depends(get_db)):
    return db.query(Specialist).order_by(Specialist.display_order).all()


@router.get("/active", response_model=List[SpecialistResponse])
def get_active(db: Session = Depends(get_db)):
    return (
        db.query(Specialist)
        .filter(Specialist.active == True)
        .order_by(Specialist.display_order)
        .all()
    )


@router.get("/by-specialisation/{specialisation_id}", response_model=List[SpecialistResponse])
def get_by_specialisation(specialisation_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Specialist)
        .options(joinedload(Specialist.specialisation))
        .filter(
            Specialist.specialisation_id == specialisation_id,
            Specialist.active == True
        )
        .order_by(Specialist.display_order)
        .all()
    )


@router.get("/{specialist_id}", response_model=SpecialistResponse)
def get_one(specialist_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialist not found")
    return record


@router.post("/", response_model=SpecialistResponse)
def create(payload: SpecialistCreate, db: Session = Depends(get_db)):
    record = Specialist(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{specialist_id}", response_model=SpecialistResponse)
def update(specialist_id: int, payload: SpecialistUpdate, db: Session = Depends(get_db)):
    record = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialist not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{specialist_id}")
def delete(specialist_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialist not found")
    db.delete(record)
    db.commit()
    return {"message": "Specialist deleted"}
