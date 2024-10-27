from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from .models import HardDrive, DataCenterLocation, DriveStatus
from .schemas import HardDriveCreate, HardDriveResponse
from .database import engine, SessionLocal
from geoalchemy2 import func
import json

app = FastAPI()

@app.post("/hard_drives/", response_model=HardDriveResponse)
async def create_hard_drive(hard_drive: HardDriveCreate):
    db = SessionLocal()
    db_hard_drive = HardDrive(
        serial_number=hard_drive.serial_number,
        capacity_gb=hard_drive.capacity_gb,
        location=f'POINT({hard_drive.longitude} {hard_drive.latitude})',
        status=hard_drive.status,
        data_center=hard_drive.data_center,
        embedding=generate_embedding(hard_drive.serial_number)
    )
    db.add(db_hard_drive)
    db.commit()
    db.refresh(db_hard_drive)
    await manager.broadcast(json.dumps({"event": "new_hard_drive", "data": hard_drive.dict()}))
    return HardDriveResponse(**db_hard_drive.__dict__)
