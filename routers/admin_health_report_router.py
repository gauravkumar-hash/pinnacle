from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models import SessionLocal
from services.health_report_service import get_health_report
import pandas as pd
import io
router = APIRouter(
    prefix="/admin",
    tags=["Admin Health Report"]
)


@router.post("/health-report")
def health_report(nrics: list[str]):

    with SessionLocal() as db:

        data = get_health_report(db, nrics)

        return {
            "count": len(data),
            "data": data
        }


@router.post("/health-report/export")
def export_health_report(nrics: list[str]):

    with SessionLocal() as db:
        data = get_health_report(db, nrics)

    df = pd.DataFrame(data)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Health Report")

    output.seek(0)

    headers = {
        "Content-Disposition": "attachment; filename=health_report.xlsx"
    }

    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
