import hmac
import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from zoneinfo import ZoneInfo

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app import config, db

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("appointment_api")
ZONE = ZoneInfo("Asia/Kolkata")
SLOT_MINUTES = 30
app = FastAPI(title="Hospital Appointment API", version=config.APP_VERSION)


class AppointmentInput(BaseModel):
    patient_id: str = Field(pattern=r"^P[0-9]{3}$")
    doctor_id: str = Field(pattern=r"^D[0-9]{3}$")
    start_at: datetime


class RescheduleInput(BaseModel):
    start_at: datetime


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(json.dumps({"event": "request_error", "request_id": request_id}))
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            }
        )
    )
    return response


def principal(authorization: str | None = Header(default=None)) -> tuple[str, str | None]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    token = authorization[7:]
    for expected, identity in (
        (config.PATIENT_ONE_TOKEN, ("patient", "P001")),
        (config.PATIENT_TWO_TOKEN, ("patient", "P002")),
        (config.STAFF_TOKEN, ("staff", None)),
    ):
        if hmac.compare_digest(token, expected):
            return identity
    raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"})


def staff_only(identity: tuple[str, str | None] = Depends(principal)):
    if identity[0] != "staff":
        raise HTTPException(403, "Staff role required")
    return identity


def validate_slot(start: datetime) -> datetime:
    if start.tzinfo is None or start.utcoffset() is None:
        raise HTTPException(422, "start_at must include a UTC offset")
    local = start.astimezone(ZONE)
    now = datetime.now(ZONE)
    if not now < local <= now + timedelta(days=30):
        raise HTTPException(422, "Slot must be in the next 30 days")
    if local.weekday() >= 5 or local.minute not in (0, 30) or local.second or local.microsecond:
        raise HTTPException(422, "Slot must start on a weekday at a half-hour boundary")
    if not (dt_time(9, 0) <= local.time() < dt_time(17, 0)):
        raise HTTPException(422, "Slot must start between 09:00 and 16:30 Asia/Kolkata")
    return local


def record_audit(conn, action: str, actor: tuple[str, str | None], appointment_id: str):
    conn.execute(
        "INSERT INTO audit_events (action, actor_role, actor_id, appointment_id) "
        "VALUES (%s, %s, %s, %s)",
        (action, actor[0], actor[1], appointment_id),
    )


@app.get("/health/live")
def live():
    return {"status": "ok", "version": config.APP_VERSION}


@app.get("/health/ready")
def readiness(response: Response):
    if not db.ready():
        response.status_code = 503
        return {"status": "not_ready"}
    return {"status": "ready"}


@app.get("/v1/doctors")
def doctors():
    with db.connection() as conn:
        return conn.execute(
            "SELECT id, name, specialty FROM doctors WHERE active ORDER BY id"
        ).fetchall()


@app.get("/v1/doctors/{doctor_id}/slots")
def slots(doctor_id: str, day: date = Query(alias="date")):
    now = datetime.now(ZONE)
    today = now.date()
    if not today <= day <= today + timedelta(days=30) or day.weekday() >= 5:
        raise HTTPException(422, "Date must be a weekday in the next 30 days")
    with db.connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM doctors WHERE id=%s AND active", (doctor_id,)
        ).fetchone():
            raise HTTPException(404, "Doctor not found")
        booked = {
            row["start_at"].astimezone(ZONE)
            for row in conn.execute(
                "SELECT start_at FROM appointments WHERE doctor_id=%s AND status='confirmed' "
                "AND start_at >= %s AND start_at < %s",
                (
                    doctor_id,
                    datetime.combine(day, dt_time.min, ZONE),
                    datetime.combine(day + timedelta(days=1), dt_time.min, ZONE),
                ),
            )
        }
    result = []
    for hour in range(9, 17):
        for minute in (0, 30):
            slot = datetime.combine(day, dt_time(hour, minute), ZONE)
            if now < slot <= now + timedelta(days=30):
                result.append({"start_at": slot.isoformat(), "available": slot not in booked})
    return result


@app.post("/v1/appointments", status_code=201)
def create_appointment(
    payload: AppointmentInput, identity: tuple[str, str | None] = Depends(principal)
):
    start = validate_slot(payload.start_at)
    if identity[0] == "patient" and identity[1] != payload.patient_id:
        raise HTTPException(403, "Cannot create another patient's appointment")
    appointment_id = str(uuid.uuid4())
    try:
        with db.connection() as conn:
            if not conn.execute(
                "SELECT 1 FROM patients WHERE id=%s AND active", (payload.patient_id,)
            ).fetchone():
                raise HTTPException(404, "Patient not found")
            if not conn.execute(
                "SELECT 1 FROM doctors WHERE id=%s AND active", (payload.doctor_id,)
            ).fetchone():
                raise HTTPException(404, "Doctor not found")
            conn.execute(
                "INSERT INTO appointments (id, patient_id, doctor_id, start_at) "
                "VALUES (%s,%s,%s,%s)",
                (appointment_id, payload.patient_id, payload.doctor_id, start),
            )
            record_audit(conn, "created", identity, appointment_id)
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(409, "Doctor slot is already booked") from exc
    return {"id": appointment_id, "status": "confirmed", **payload.model_dump(mode="json")}


def owned_appointment(
    conn, appointment_id: uuid.UUID, identity: tuple[str, str | None], lock=False
):
    query = "SELECT * FROM appointments WHERE id=%s"
    if lock:
        query += " FOR UPDATE"
    row = conn.execute(query, (appointment_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Appointment not found")
    if identity[0] == "patient" and row["patient_id"] != identity[1]:
        raise HTTPException(403, "Cannot access another patient's appointment")
    return row


@app.get("/v1/appointments/{appointment_id}")
def get_appointment(
    appointment_id: uuid.UUID, identity: tuple[str, str | None] = Depends(principal)
):
    with db.connection() as conn:
        return owned_appointment(conn, appointment_id, identity)


@app.patch("/v1/appointments/{appointment_id}")
def reschedule(
    appointment_id: uuid.UUID,
    payload: RescheduleInput,
    identity: tuple[str, str | None] = Depends(principal),
):
    start = validate_slot(payload.start_at)
    try:
        with db.connection() as conn:
            row = owned_appointment(conn, appointment_id, identity, lock=True)
            if row["status"] != "confirmed":
                raise HTTPException(409, "Cancelled appointments cannot be rescheduled")
            updated = conn.execute(
                "UPDATE appointments SET start_at=%s, updated_at=now() WHERE id=%s RETURNING *",
                (start, appointment_id),
            ).fetchone()
            record_audit(conn, "rescheduled", identity, appointment_id)
            return updated
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(409, "Doctor slot is already booked") from exc


@app.post("/v1/appointments/{appointment_id}/cancel")
def cancel(appointment_id: uuid.UUID, identity: tuple[str, str | None] = Depends(principal)):
    with db.connection() as conn:
        row = owned_appointment(conn, appointment_id, identity, lock=True)
        if row["status"] != "confirmed":
            raise HTTPException(409, "Appointment already cancelled")
        updated = conn.execute(
            "UPDATE appointments SET status='cancelled', updated_at=now() WHERE id=%s RETURNING *",
            (appointment_id,),
        ).fetchone()
        record_audit(conn, "cancelled", identity, appointment_id)
        return updated


@app.get("/v1/audit-events", dependencies=[Depends(staff_only)])
def audit_events(limit: int = Query(default=50, ge=1, le=100)):
    with db.connection() as conn:
        return conn.execute(
            "SELECT id, action, actor_role, actor_id, appointment_id, created_at "
            "FROM audit_events ORDER BY id DESC LIMIT %s",
            (limit,),
        ).fetchall()
