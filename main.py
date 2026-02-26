from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk
from config import ADMIN_WEB_URL, BACKEND_ENVIRONMENT, SENTRY_DSN
from utils.fastapi import HTTPJSONException
from routers.realtime import ws_manager

sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=0.5,
    profiles_sample_rate=0.5,
    send_default_pii=True,
    enable_tracing=True
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ws_manager.broadcaster.connect()
    await ws_manager.listen()
    yield
    # Shutdown executors before disconnecting broadcaster
    from utils.executors import shutdown_executors
    shutdown_executors()
    await ws_manager.broadcaster.disconnect()

# Disable Docs in Production Environment
IS_DEV = BACKEND_ENVIRONMENT == 'development'
print("Current Environment:", BACKEND_ENVIRONMENT)
if BACKEND_ENVIRONMENT == 'production':
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
else:
    app = FastAPI(lifespan=lifespan)

@app.exception_handler(HTTPJSONException)
async def unicorn_exception_handler(request: Request, exc: HTTPJSONException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code.value,
            "title": exc.title,
            "message": exc.message,
            "detail": exc.message,
        },
    )

# Patient App Routers
from routers.patient.auth import router as auth_router
from routers.patient.user import router as user_router
from routers.patient.teleconsult import router as teleconsult_router
from routers.patient import teleconsult_family, visits, family, document, appointment
from routers.patient.webhook import router as webhook_router
from routers.patient.mobile_app import router as mobile_app_router
from routers.patient.crons import router as crons_router
from routers.patient.support import router as support_router
from routers.patient.yuu import router as yuu_router
from routers.payments import payment_methods, stripe
from routers.payments.pgw2c2p.router import router as pgw2c2p_router
app.include_router(auth_router, prefix="/api/auth", tags=["Patient Mobile App"])
app.include_router(user_router, prefix="/api/user", tags=["Patient Mobile App"])
app.include_router(mobile_app_router, prefix="/api/mobile_app", tags=["Patient Mobile App"])
app.include_router(teleconsult_router, prefix="/api/teleconsult", tags=["Patient Mobile App (Teleconsult)"])
app.include_router(teleconsult_family.router, prefix="/api/teleconsult/v2", tags=["Patient Mobile App (Teleconsult v2)"])
app.include_router(appointment.router, prefix="/api/appointment/v1", tags=["Patient Mobile App (Appointment)"])
app.include_router(visits.router, prefix="/api/visits", tags=["Patient Mobile App (Records)"])
app.include_router(family.router, prefix="/api/family", tags=["Patient Mobile App (Family Members)"])
app.include_router(document.router, prefix="/api/document", tags=["Patient Mobile App (Family Members)"])
app.include_router(support_router, prefix="/api/support", tags=["Patient Mobile App (Support)"])
app.include_router(yuu_router, prefix="/api/v1/patient", tags=["Patient Mobile App (Yuu)"])
from routers.patient import activity, realtime, walkin, health_report, testing
app.include_router(activity.router, prefix="/api/activity", tags=["Patient Mobile App"])
app.include_router(realtime.router, prefix="/api", tags=["Patient Mobile App"])
app.include_router(walkin.router, prefix="/api/walkin", tags=["Patient Mobile App (Queue Request)"])
app.include_router(health_report.router, prefix="/api/health_report", tags=["Patient Mobile App (Health Report)"])
app.include_router(stripe.router, prefix="/api/stripe/v1", tags=["Patient Mobile App (Stripe)"])
app.include_router(pgw2c2p_router, prefix="/api/2c2p", tags=["Patient Mobile App (Payments 2C2P)"])
app.include_router(payment_methods.router, prefix="/api/payment_methods", tags=["Patient Mobile App (Payment Methods)"])
app.include_router(testing.router, prefix="/api/testing", tags=["Patient Mobile App (Testing)"])
# Doctor App Routers
from routers.doctor import doctor, teleconsult, realtime
app.include_router(teleconsult.router, prefix="/api/doctor/teleconsult", tags=["Doctor App"])
app.include_router(doctor.router, prefix="/api/doctor", tags=["Doctor App"])
app.include_router(realtime.router, prefix="/api/doctor", tags=["Doctor App"])
# Admin App Routers
from routers.admin import st_andrew, teleconsult, admin, branch, blockoff, realtime, walkin, patients, rates, notifications, corporate_codes, corporate_users, reports, health_reports, yuu as admin_yuu
from routers.admin import documents as admin_documents
from routers.admin import appointment as admin_appointment
from routers.admin import specialists as admin_specialists
app.include_router(realtime.router, prefix="/api/admin", tags=["Admin Web App (Teleconsult)"])
app.include_router(teleconsult.router, prefix="/api/admin/teleconsult", tags=["Admin Web App (Teleconsult)"])
app.include_router(walkin.router, prefix="/api/admin/walkin", tags=["Admin Web App (Queue Request)"])
app.include_router(st_andrew.router, prefix="/api/admin/st_andrew", tags=["Admin Web App"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin Web App"])
app.include_router(branch.router, prefix="/api/admin/branches", tags=["Admin Web App (Branch)"])
app.include_router(blockoff.router, prefix="/api/admin/blockoffs", tags=["Admin Web App (Blockoff)"])
app.include_router(patients.router, prefix="/api/admin/patients", tags=["Admin Web App (Patients)"])
app.include_router(admin_documents.router, prefix="/api/admin/patients", tags=["Admin Web App (Patients)"])
app.include_router(rates.router, prefix="/api/admin/rates", tags=["Admin Web App (Rates)"])
app.include_router(corporate_codes.router, prefix="/api/admin/corporate_codes", tags=["Admin Web App (Rates)"])
app.include_router(corporate_users.router, prefix="/api/admin/corporate_users", tags=["Admin Web App (Corporate Users)"])
app.include_router(notifications.router, prefix="/api/admin/notifications", tags=["Admin Web App (Notifications)"])
app.include_router(reports.router, prefix="/api/admin/reports", tags=["Admin Web App (Reports)"])
app.include_router(health_reports.router, prefix="/api/admin/health_reports", tags=["Admin Web App (Health Reports)"])
app.include_router(admin_yuu.router, prefix="/api/admin/yuu", tags=["Admin Web App (Yuu)"])
app.include_router(admin_appointment.router, prefix="/api/admin/appointments/v1", tags=["Admin Web App (Appointments)"])
app.include_router(admin_specialists.router, prefix="/api/admin/specialists/v1", tags=["Admin Web App (Specialists)"])
# Dispatch Module
from routers.delivery import dispatch, logistic, zone
app.include_router(dispatch.router, prefix="/api/delivery/dispatch", tags=["Admin Web App (Delivery Module)"])
app.include_router(logistic.router, prefix="/api/delivery/logistic", tags=["Admin Web App (Delivery Module)"])
app.include_router(zone.router, prefix="/api/delivery/pinnacle_zone", tags=["Admin Web App (Delivery Module)"])
# Backend Routers
app.include_router(webhook_router, prefix="/api/webhook", tags=["Webhooks"])
app.include_router(crons_router, prefix="/api/crons", tags=["Cron Jobs"])

from routers import render
app.include_router(render.router, prefix="/api/render", tags=["Render APIs"])

# CORS Support: https://stackoverflow.com/a/66460861
origins = [
    ADMIN_WEB_URL,
    "http://localhost:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# uvicorn main:app --reload --host 0.0.0.0 --port 8000
if __name__ == '__main__':
    import uvicorn
    if IS_DEV:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, workers=1)
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=2)
    
