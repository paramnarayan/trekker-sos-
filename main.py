from fastapi.openapi.utils import status_code_ranges
from pydantic_core.core_schema import none_schema
from psycopg2 import Timestamp
from fastapi import FastAPI,Depends,HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from datetime import datetime, timedelta
from worker import trigger_sos
import user_db


database_url= "postgresql://postgres:mysecretpassword@localhost:5432/trekker_db"
engine = create_engine(database_url)

SessionLocal=sessionmaker(autocommit=False,autoflush=False,bind=engine)


app=FastAPI(title ="Trekker SOS")

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()



class Usercreate(BaseModel):
    full_name:str
    phone_number:str
    device_id:str


class Offline_event_check(BaseModel):
    checkpointid:UUID
    Timestamp: datetime
    lat:Optional[float]=None
    lon:Optional[float]= None
    battery:Optional[int]=None
    
class BatchSyncPayload(BaseModel):
    device_id: str
    trek_id: UUID
    events: List[Offline_event_check]


#API

@app.post("/users")
def create_user(user:Usercreate,db:Session=Depends(get_db)):
    existing_user=db.query(user_db.user).filter(user_db.User.device_id==user.device_id).first()
    if existing_user:
        raise HTTPException(status_code=400,detail="device already registered")
    new_user=user_db.user(
        name=user.full_name,
        phone_number=user.phone_number,
        device_id=user.device_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created", "user_id": new_user.id}

@app.post("/sync/batch")
def sync_off_data(payload:BatchSyncPayload,db:Session=Depends(get_db)):
    user=db.query(user_db.user).filter(user_db.user.device_id==payload.device_id).first()
    if not user:
        raise HTTPException(status_code=400,detail="device not registered")
    trek = db.query(user_db.Trek).filter(user_db.Trek.id == payload.trek_id).first()
    if not trek:
        raise HTTPException(status_code=404,detail="trek not found")
    processed_count=0

    for event in payload.events:
        processed_count+=1

    return{
        "status":"success",
        "message": f"no of events processed till now {processed_count}",
        "cleared_checkpoints":[e.checkpointid for e in payload.events]        

    }
            

@app.post("/treks/{trek_id}/start-timer")
def start_checkpoint_timer(trek_id: str, grace_period_minutes: int):
    checkpoint_id = "cp_12345" # Mocked for testing
    
    # Calculate exactly when the SOS should fire
    sos_time = datetime.utcnow() + timedelta(minutes=grace_period_minutes)
    
    # Schedule the background task in Redis
    trigger_sos.apply_async(args=[checkpoint_id, trek_id], eta=sos_time)
    
    return {
        "message": "Timer started. Switch is armed.", 
        "sos_scheduled_for": sos_time
    }