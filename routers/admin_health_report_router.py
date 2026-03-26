from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from models import SessionLocal
import pandas as pd
import io
from repository.health_report_repository import fetch_health_history, fetch_latest_health_report
router = APIRouter(prefix="/admin/health-report", tags=["Admin Health Report"])

# --- HELPERS ---

async def get_nrics_from_input(nric_text: str, file: UploadFile):
    """Parses NRICs from both text field and uploaded file."""
    nrics = []
    if file:
        contents = await file.read()
        try:
            df = pd.read_csv(io.BytesIO(contents)) if file.filename.endswith('.csv') else pd.read_excel(io.BytesIO(contents))
            # Find NRIC column or take first column
            nric_col = next((c for c in df.columns if c.lower() == 'nric'), df.columns[0])
            nrics.extend(df[nric_col].dropna().astype(str).str.strip().tolist())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"File error: {str(e)}")
            
    if nric_text:
        # Split by comma or newline
        nrics.extend([n.strip() for n in nric_text.replace('\n', ',').split(',') if n.strip()])
    
    return list(set(nrics)) # Deduplicate

def generate_excel_response(data, input_nrics, filename):
    """Generates a 2-sheet Excel: Data and Missing Records."""
    found_nrics = set(row["nric"] for row in data)
    missing_nrics = [n for n in input_nrics if n not in found_nrics]
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Sheet 1: Clinical Data
        df_found = pd.DataFrame(data)
        df_found.to_excel(writer, index=False, sheet_name="Health Data")
        
        # Sheet 2: Missing NRICs
        if missing_nrics:
            df_missing = pd.DataFrame(missing_nrics, columns=["NRICs Not Found"])
            df_missing.to_excel(writer, index=False, sheet_name="Missing Records")
            
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}.xlsx",
            "X-Missing-Count": str(len(missing_nrics))
        }
    )

# --- ENDPOINTS ---

@router.post("/export-history")
async def export_history(nric_text: str = Form(None), file: UploadFile = File(None)):
    """Exports every visit for the provided NRICs."""
    nrics = await get_nrics_from_input(nric_text, file)
    if not nrics: raise HTTPException(400, "No NRICs provided")
    
    with SessionLocal() as db:
        data = fetch_health_history(db, nrics)
    
    return generate_excel_response(data, nrics, "Health_Timeline_History")

@router.post("/export-latest")
async def export_latest(nric_text: str = Form(None), file: UploadFile = File(None)):
    """Exports only the most recent visit for the provided NRICs."""
    nrics = await get_nrics_from_input(nric_text, file)
    if not nrics: raise HTTPException(400, "No NRICs provided")
    
    with SessionLocal() as db:
        data = fetch_latest_health_report(db, nrics)
    
    return generate_excel_response(data, nrics, "Latest_Health_Snapshot")
