from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app

ZONE = ZoneInfo("Asia/Kolkata")


def future_slot(hour=9, minute=0):
    day = datetime.now(ZONE).date() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return datetime.combine(day, time(hour, minute), ZONE).isoformat()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_appointments():
    if config.DATABASE_NAME != "appointments_test":
        raise RuntimeError("Tests must run against appointments_test")
    with db.connection() as conn:
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM appointments")
    yield


def test_health_catalog_and_time_validation():
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert len(client.get("/v1/doctors").json()) == 2
        day = future_slot()[:10]
        slots = client.get(f"/v1/doctors/D001/slots?date={day}")
        assert slots.status_code == 200
        assert len(slots.json()) == 16
        invalid = client.post(
            "/v1/appointments",
            headers=auth(config.PATIENT_ONE_TOKEN),
            json={"patient_id": "P001", "doctor_id": "D001", "start_at": "2030-01-01T09:00:00"},
        )
        assert invalid.status_code == 422


def test_roles_lifecycle_and_audit():
    with TestClient(app) as client:
        payload = {"patient_id": "P001", "doctor_id": "D001", "start_at": future_slot()}
        assert client.post("/v1/appointments", json=payload).status_code == 401
        assert (
            client.post(
                "/v1/appointments", headers=auth(config.PATIENT_TWO_TOKEN), json=payload
            ).status_code
            == 403
        )
        created = client.post(
            "/v1/appointments", headers=auth(config.PATIENT_ONE_TOKEN), json=payload
        )
        assert created.status_code == 201
        appointment_id = created.json()["id"]
        assert (
            client.get(
                f"/v1/appointments/{appointment_id}", headers=auth(config.PATIENT_TWO_TOKEN)
            ).status_code
            == 403
        )
        assert (
            client.get("/v1/audit-events", headers=auth(config.PATIENT_ONE_TOKEN)).status_code
            == 403
        )
        changed = client.patch(
            f"/v1/appointments/{appointment_id}",
            headers=auth(config.PATIENT_ONE_TOKEN),
            json={"start_at": future_slot(9, 30)},
        )
        assert changed.status_code == 200
        cancelled = client.post(
            f"/v1/appointments/{appointment_id}/cancel", headers=auth(config.PATIENT_ONE_TOKEN)
        )
        assert cancelled.json()["status"] == "cancelled"
        assert (
            client.patch(
                f"/v1/appointments/{appointment_id}",
                headers=auth(config.PATIENT_ONE_TOKEN),
                json={"start_at": future_slot(10)},
            ).status_code
            == 409
        )
        events = client.get("/v1/audit-events", headers=auth(config.STAFF_TOKEN)).json()
        assert [event["action"] for event in events] == ["cancelled", "rescheduled", "created"]


def test_bad_references_and_slot_reuse_after_cancellation():
    with TestClient(app) as client:
        slot = future_slot()
        response = client.post(
            "/v1/appointments",
            headers=auth(config.STAFF_TOKEN),
            json={"patient_id": "P999", "doctor_id": "D001", "start_at": slot},
        )
        assert response.status_code == 404
        response = client.post(
            "/v1/appointments",
            headers=auth(config.STAFF_TOKEN),
            json={"patient_id": "P001", "doctor_id": "D999", "start_at": slot},
        )
        assert response.status_code == 404
        first = client.post(
            "/v1/appointments",
            headers=auth(config.PATIENT_ONE_TOKEN),
            json={"patient_id": "P001", "doctor_id": "D001", "start_at": slot},
        )
        assert first.status_code == 201
        assert (
            client.post(
                f"/v1/appointments/{first.json()['id']}/cancel",
                headers=auth(config.PATIENT_ONE_TOKEN),
            ).status_code
            == 200
        )
        second = client.post(
            "/v1/appointments",
            headers=auth(config.PATIENT_TWO_TOKEN),
            json={"patient_id": "P002", "doctor_id": "D001", "start_at": slot},
        )
        assert second.status_code == 201


def test_concurrent_conflict_is_blocked_by_database():
    slot = future_slot(10)
    barrier = Barrier(2)

    def submit(patient_id, token):
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            response = client.post(
                "/v1/appointments",
                headers=auth(token),
                json={"patient_id": patient_id, "doctor_id": "D001", "start_at": slot},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(submit, "P001", config.PATIENT_ONE_TOKEN),
            pool.submit(submit, "P002", config.PATIENT_TWO_TOKEN),
        ]
        statuses = sorted(future.result() for future in futures)
        assert statuses == [201, 409]
    with db.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM appointments "
            "WHERE doctor_id='D001' AND start_at=%s AND status='confirmed'",
            (datetime.fromisoformat(slot),),
        ).fetchone()["n"]
    assert count == 1
    print(f"Concurrent HTTP statuses: {statuses}; confirmed database rows: {count}")
