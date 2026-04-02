from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from models.specialisation import Specialisation
from schemas.specialisation import (
    SpecialisationCreate,
    SpecialisationUpdate,
    SpecialisationResponse
)
from models  import get_db

router = APIRouter(prefix="/specialisations", tags=["Specialisations"])


@router.get("/", response_model=List[SpecialisationResponse])
def get_all(db: Session = Depends(get_db)):
    return db.query(Specialisation).order_by(Specialisation.display_order).all()


@router.get("/active", response_model=List[SpecialisationResponse])
def get_active(db: Session = Depends(get_db)):
    return (
        db.query(Specialisation)
        .filter(Specialisation.active == True)
        .order_by(Specialisation.display_order)
        .all()
    )


@router.get("/{specialisation_id}", response_model=SpecialisationResponse)
def get_one(specialisation_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialisation).filter(Specialisation.id == specialisation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    return record


@router.post("/", response_model=SpecialisationResponse)
def create(payload: SpecialisationCreate, db: Session = Depends(get_db)):
    record = Specialisation(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{specialisation_id}", response_model=SpecialisationResponse)
def update(specialisation_id: int, payload: SpecialisationUpdate, db: Session = Depends(get_db)):
    record = db.query(Specialisation).filter(Specialisation.id == specialisation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{specialisation_id}")
def delete(specialisation_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialisation).filter(Specialisation.id == specialisation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    db.delete(record)
    db.commit()
    return {"message": "Specialisation deleted"}