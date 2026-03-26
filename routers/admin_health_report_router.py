from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from models import SessionLocal
from services.health_report_service import get_health_report
import pandas as pd
import io

router = APIRouter(
    prefix="/admin",
    tags=["Admin Health Report"]
)

@router.post("/health-report/export")
async def export_health_report(
    nric_text: str = Form(None),   # Manually typed NRICs (comma or newline separated)
    file: UploadFile = File(None)  # Excel or CSV file upload
):
    all_input_nrics = []

    # 1. Extract NRICs from File if provided
    if file:
        contents = await file.read()
        try:
            if file.filename.endswith('.csv'):
                df_input = pd.read_csv(io.BytesIO(contents))
            else:
                df_input = pd.read_excel(io.BytesIO(contents))
            
            # Look for a column named 'nric' (case-insensitive) or take the first column
            nric_col = next((c for c in df_input.columns if c.lower() == 'nric'), df_input.columns[0])
            file_nrics = df_input[nric_col].dropna().astype(str).str.strip().tolist()
            all_input_nrics.extend(file_nrics)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    # 2. Extract NRICs from manual text if provided
    if nric_text:
        # Split by comma or newline and clean whitespace
        manual_nrics = [n.strip() for n in nric_text.replace('\n', ',').split(',') if n.strip()]
        all_input_nrics.extend(manual_nrics)

    # 3. Validation & Deduplication
    unique_input_nrics = list(set(all_input_nrics))
    if not unique_input_nrics:
        raise HTTPException(status_code=400, detail="Please provide NRICs via text or file upload.")

    # 4. Fetch Data from Service
    with SessionLocal() as db:
        data = get_health_report(db, unique_input_nrics)

    # 5. Identify Missing NRICs
    # Compare input list against the NRICs found in the data rows
    found_nrics = set(row["nric"] for row in data)
    missing_nrics = [n for n in unique_input_nrics if n not in found_nrics]

    # 6. Generate Multi-Sheet Excel
    output = io.BytesIO()
    # Use xlsxwriter for multi-sheet support
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Sheet 1: Found Records
        if data:
            df_found = pd.DataFrame(data)
            df_found.to_excel(writer, index=False, sheet_name="Health History")
        
        # Sheet 2: Missing Records (The new feature)
        if missing_nrics:
            df_missing = pd.DataFrame(missing_nrics, columns=["NRICs Not Found"])
            df_missing.to_excel(writer, index=False, sheet_name="Missing Records")

    output.seek(0)

    # 7. Response with Custom Headers
    headers = {
        "Content-Disposition": "attachment; filename=health_report_export.xlsx",
        "X-Missing-Count": str(len(missing_nrics)) # Frontend can use this for an alert
    }

    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
