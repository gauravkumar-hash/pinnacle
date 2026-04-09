from datetime import datetime
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from models import get_db
from models.pinnacle import StAndrew, StAndrewMetadata, StAndrewTemp
from routers.admin.actions.st_andrew import compare_tables, convert_xlsx_to_csv, overwrite_changes, upload_csv
from utils import sg_datetime
from utils.fastapi import SuccessResp
from utils.supabase_auth import get_superadmin
import tempfile
import os.path as osp
from sqlalchemy.orm import Session
import pandas as pd

router = APIRouter(dependencies=[Depends(get_superadmin)])

class StAndrewMetadataResp(BaseModel):
    last_updated: datetime
    total_records: int
    imported_records: Optional[int] = None
    insert_diff: list[str] = []
    update_diff: list[str] = []
    delete_diff: list[str] = []

@router.get('/metadata', response_model=StAndrewMetadataResp)
def get_metadata(db: Session = Depends(get_db)):
    record = db.query(StAndrewMetadata).first()
    if not record:
        record = StAndrewMetadata(
            last_updated=sg_datetime.now(),
            total_records=db.query(StAndrew).count()
        )
        db.add(record)
        db.commit()
    
    return StAndrewMetadataResp(**record.as_dict())

class StAndrewUploadResp(BaseModel):
    new: list[str] = []
    updated: list[str] = []
    deleted: list[str] = []

@router.post('/upload', response_model=SuccessResp)
def upload_table(file: UploadFile = File(), db: Session = Depends(get_db)):
    tempdir = tempfile.gettempdir()
    if not file.filename:
        raise HTTPException(400, "Filename not found")
    # if not file.content_type in ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
    if file.content_type not in ['text/csv']:
        raise HTTPException(400, 'Only CSV files are supported')

    file_path = osp.join(tempdir, file.filename)
    print(f"Temp Path: {file_path}")
    print()
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Convert XLSX to CSV
    csv_file_path = file_path
    if file.content_type != 'text/csv':
        csv_file_path = f'{osp.splitext(file_path)[0]}.csv'
        convert_xlsx_to_csv(file_path, csv_file_path)

    # 2. Filter CSV to keep only unique records
    df = pd.read_csv(csv_file_path)
    df_unique = df.drop_duplicates(subset='NRIC', keep='first')
    filtered_csv_file_path = f'{osp.splitext(file_path)[0]}_unique.csv'
    df_unique.to_csv(filtered_csv_file_path, index=False)

    # 3. Upload CSV to Postgres
    upload_csv(filtered_csv_file_path)
    
    # 4. Compare Changes
    new, updated, deleted = compare_tables()
    
    record = db.query(StAndrewMetadata).first()
    if not record:
        record = StAndrewMetadata(
            last_updated=sg_datetime.now(),
            total_records=db.query(StAndrew).count()
        )
        db.add(record)
        
    record.imported_records = db.query(StAndrewTemp).count()
    record.insert_diff = list(new)
    record.update_diff = list(updated)
    record.delete_diff = list(deleted)
    db.commit()

    return SuccessResp(success=True)

@router.get('/update', response_model=SuccessResp)
def update_records(db: Session = Depends(get_db)):
    record = db.query(StAndrewMetadata).first()
    if not record:
        raise HTTPException(400, "No metadata record found")
    
    overwrite_changes(record)
    record.last_updated = sg_datetime.now()
    record.total_records = db.query(StAndrew).count()
    record.imported_records = None
    record.insert_diff = []
    record.update_diff = []
    record.delete_diff = []
    db.commit()
    return SuccessResp(success=True)