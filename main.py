import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import user_db
from worker import send_sms


database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:{DB_PASSWORD}@db:5432/trekker_db")
engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Trekker SOS")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UserCreate(BaseModel):
    full_name: str
    phone_number: str
    device_id: str


class OfflineEventCheck(BaseModel):
    checkpointid: UUID
    Timestamp: datetime
    lat: Optional[float] = None
    lon: Optional[float] = None
    battery: Optional[int] = None


class BatchSyncPayload(BaseModel):
    device_id: str
    trek_id: UUID
    events: List[OfflineEventCheck]


class LocationUpdate(BaseModel):
    latitude: float
    longitude: float


@app.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(user_db.User).filter(user_db.User.device_id == user.device_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="device already registered")
    new_user = user_db.User(
        name=user.full_name,
        phone_number=user.phone_number,
        device_id=user.device_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created", "user_id": new_user.id}


@app.post("/sync/batch")
def sync_off_data(payload: BatchSyncPayload, db: Session = Depends(get_db)):
    user = db.query(user_db.User).filter(user_db.User.device_id == payload.device_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="device not registered")
    trek = db.query(user_db.Trek).filter(user_db.Trek.id == payload.trek_id).first()
    if not trek:
        raise HTTPException(status_code=404, detail="trek not found")

    processed_count = 0
    for event in payload.events:
        processed_count += 1

    return {
        "status": "success",
        "message": f"no of events processed till now {processed_count}",
        "cleared_checkpoints": [e.checkpointid for e in payload.events],
    }


@app.post("/treks/{trek_id}/start-timer")
def start_checkpoint_timer(trek_id: str, grace_period_minutes: int):
    checkpoint_id = "cp_12345"
    sos_time = datetime.utcnow() + timedelta(minutes=grace_period_minutes)
    trigger_sos.apply_async(args=[checkpoint_id, trek_id], eta=sos_time)
    return {
        "message": "Timer started. Switch is armed.",
        "sos_scheduled_for": sos_time,
    }


@app.post("/user/{device_id}/location")
def user_location(device_id: str, location: LocationUpdate, db: Session = Depends(get_db)):
    user = db.query(user_db.User).filter(user_db.User.device_id == device_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user device not found")

    user.latitude = location.latitude
    user.longitude = location.longitude
    user.last_updated = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return {
        "message": "location updated successfully",
        "user": {
            "latitude": user.latitude,
            "longitude": user.longitude,
            "last_updated": user.last_updated,
        },
    }


@app.post("/user/{device_id}/sos")
def trigger_sos(device_id: str, db: Session = Depends(get_db)):
    user = db.query(user_db.User).filter(user_db.User.device_id == device_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user device not found")
    if not user.latitude or not user.longitude:
        raise HTTPException(status_code=400, detail="no location data available")
    send_sms.delay(device_id, user.latitude, user.longitude)
    return {"status": "success", "message": "sos alert sent"}