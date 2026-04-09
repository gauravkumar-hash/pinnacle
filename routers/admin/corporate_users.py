from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
import csv
import io
from typing import List, Optional
from fastapi.responses import StreamingResponse

from models import get_db
from models.corporate import CorporateUser
from models.model_enums import SGiMedICType
from utils.fastapi import SuccessResp
from utils.supabase_auth import get_superadmin

router = APIRouter(dependencies=[Depends(get_superadmin)])

class CsvUploadResponse(BaseModel):
    success: bool
    total_records: int
    successful_records: int
    failed_records: List[dict]
    error_message: Optional[str]

@router.post("/upload", response_model=CsvUploadResponse)
async def upload_corporate_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files are allowed")

    # Read CSV content
    content = await file.read()
    csv_data = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(csv_data))
    
    if not csv_reader.fieldnames:
        raise HTTPException(400, "CSV file is empty or invalid")
        
    required_headers = ['ic_type', 'nric', 'code']
    if not all(header in csv_reader.fieldnames for header in required_headers):
        raise HTTPException(400, "CSV must contain ic_type, nric, and code columns")

    # Get unique corporate codes
    codes = {row['code'] for row in csv_reader}

    # Reset file pointer
    csv_reader = csv.DictReader(io.StringIO(csv_data))
    
    # Clear existing records for these codes
    db.query(CorporateUser).filter(CorporateUser.code.in_(codes)).delete()
    
    # Process records
    total_records = 0
    successful_records = 0
    failed_records = []
    
    for row in csv_reader:
        total_records += 1
        try:
            # Validate IC type
            try:
                ic_type = SGiMedICType(row['ic_type'].upper())
            except ValueError:
                raise ValueError(f"Invalid IC type: {row['ic_type']}")

            # Create new record
            corporate_user = CorporateUser(
                ic_type=ic_type,
                nric=row['nric'].upper(),
                code=row['code']
            )
            db.add(corporate_user)
            successful_records += 1
            
        except Exception as e:
            failed_records.append({
                "row": row,
                "error": str(e)
            })
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to commit changes: {str(e)}")

    return CsvUploadResponse(
        success=True,
        total_records=total_records,
        successful_records=successful_records,
        failed_records=failed_records,
        error_message=None if not failed_records else "Some records failed to process"
    )

class CorporateUserCount(BaseModel):
    code: str
    count: int

class CorporateUserCountResponse(BaseModel):
    counts: List[CorporateUserCount]

@router.get("/", response_model=CorporateUserCountResponse)
async def get_corporate_user_counts(db: Session = Depends(get_db)):
    # Query to count users grouped by code
    counts_query = (
        db.query(
            CorporateUser.code,
            func.count(CorporateUser.id).label('count')
        )
        .group_by(CorporateUser.code)
        .all()
    )
    
    # Convert query results to Pydantic models
    counts = [
        CorporateUserCount(code=code, count=count)
        for code, count in counts_query
    ]
    return CorporateUserCountResponse(
        counts=counts
    )

@router.delete("/{code}", response_model=SuccessResp)
async def delete_corporate_users(
    code: str,
    db: Session = Depends(get_db)
):
    try:
        # Delete all users with the given code
        deleted_count = db.query(CorporateUser).filter(CorporateUser.code == code).delete()
        db.commit()
        return SuccessResp(success=True)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to delete corporate users: {str(e)}")

@router.get("/{code}/download", response_class=StreamingResponse)
async def download_corporate_users(
    code: str,
    db: Session = Depends(get_db)
):
    # Query users for the given code
    users = db.query(CorporateUser).filter(CorporateUser.code == code).all()
    
    if not users:
        raise HTTPException(404, f"No users found for code: {code}")

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['ic_type', 'nric', 'code'])
    writer.writeheader()
    
    for user in users:
        writer.writerow({
            'ic_type': user.ic_type.value,
            'nric': user.nric,
            'code': user.code
        })
    
    # Create response with CSV file
    output.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename=corporate_users_{code}.csv',
        'Content-Type': 'text/csv'
    }
    
    return StreamingResponse(
        iter([output.getvalue()]),
        headers=headers
    )

