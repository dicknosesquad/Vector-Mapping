import asyncio
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine, Column, Integer, String, Float, Enum, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from pydantic import BaseModel
from typing import List, Dict
import enum
import json
from pgvector.sqlalchemy import Vector
from postgresml import Model
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

# Database setup
DATABASE_URL = "postgresql://user:password@localhost/regional_datacenter_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class DataCenterLocation(str, enum.Enum):
    SEATTLE = "Seattle"
    DENVER = "Denver"

class DriveStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    MAINTENANCE = "Maintenance"
    FAILED = "Failed"

# Models
class HardDrive(Base):
    __tablename__ = "hard_drives"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String, unique=True, index=True)
    capacity_gb = Column(Integer)
    location = Column(Geometry('POINT', srid=4326))
    status = Column(Enum(DriveStatus))
    data_center = Column(Enum(DataCenterLocation))
    embedding = Column(Vector(384))  # For AI-based similarity search

Base.metadata.create_all(bind=engine)

# Pydantic models
class HardDriveCreate(BaseModel):
    serial_number: str
    capacity_gb: int
    latitude: float
    longitude: float
    elevation: float
    status: DriveStatus
    data_center: DataCenterLocation

class HardDriveResponse(BaseModel):
    id: int
    serial_number: str
    capacity_gb: int
    latitude: float
    longitude: float
    elevation: float
    status: DriveStatus
    data_center: DataCenterLocation

# FastAPI app
app = FastAPI()

# Helper functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# AI model setup
ml_model = Model(name="hard_drive_failure_prediction")
ml_model.fit("SELECT * FROM hard_drives", "status")

# Azure AI setup
azure_credential = AzureKeyCredential("<your-azure-key>")
text_analytics_client = TextAnalyticsClient(endpoint="<your-azure-endpoint>", credential=azure_credential)

# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# API endpoints
@app.post("/hard_drives/", response_model=HardDriveResponse)
async def create_hard_drive(hard_drive: HardDriveCreate):
    db = next(get_db())
    db_hard_drive = HardDrive(
        serial_number=hard_drive.serial_number,
        capacity_gb=hard_drive.capacity_gb,
        location=f'POINT({hard_drive.longitude} {hard_drive.latitude} {hard_drive.elevation})',
        status=hard_drive.status,
        data_center=hard_drive.data_center,
        embedding=generate_embedding(hard_drive.serial_number)
    )
    db.add(db_hard_drive)
    db.commit()
    db.refresh(db_hard_drive)
    await manager.broadcast(json.dumps({"event": "new_hard_drive", "data": hard_drive.dict()}))
    return HardDriveResponse(**db_hard_drive.__dict__)

@app.get("/hard_drives/", response_model=List[HardDriveResponse])
async def get_all_hard_drives():
    db = next(get_db())
    hard_drives = db.query(HardDrive).all()
    return [HardDriveResponse(**hd.__dict__) for hd in hard_drives]

@app.get("/hard_drives/nearby/", response_model=List[HardDriveResponse])
async def get_nearby_hard_drives(
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(...),
    data_center: DataCenterLocation = Query(None)
):
    db = next(get_db())
    query = db.query(HardDrive).filter(
        func.ST_DWithin(
            HardDrive.location,
            func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
            radius_km * 1000
        )
    )
    if data_center:
        query = query.filter(HardDrive.data_center == data_center)
    nearby_drives = query.all()
    return [HardDriveResponse(**hd.__dict__) for hd in nearby_drives]

@app.put("/hard_drives/{hard_drive_id}/status/", response_model=HardDriveResponse)
async def update_hard_drive_status(hard_drive_id: int, status: DriveStatus):
    db = next(get_db())
    hard_drive = db.query(HardDrive).filter(HardDrive.id == hard_drive_id).first()
    if not hard_drive:
        raise HTTPException(status_code=404, detail="Hard drive not found")
    hard_drive.status = status
    db.commit()
    db.refresh(hard_drive)
    await manager.broadcast(json.dumps({"event": "status_update", "data": HardDriveResponse(**hard_drive.__dict__).dict()}))
    return HardDriveResponse(**hard_drive.__dict__)

@app.get("/hard_drives/by_data_center/{data_center}", response_model=List[HardDriveResponse])
async def get_hard_drives_by_data_center(data_center: DataCenterLocation):
    db = next(get_db())
    hard_drives = db.query(HardDrive).filter(HardDrive.data_center == data_center).all()
    return [HardDriveResponse(**hd.__dict__) for hd in hard_drives]

@app.get("/data_centers/stats", response_model=Dict[str, Dict])
async def get_data_center_stats():
    db = next(get_db())
    stats = {}
    for dc in DataCenterLocation:
        dc_drives = db.query(HardDrive).filter(HardDrive.data_center == dc)
        total_capacity = sum(drive.capacity_gb for drive in dc_drives)
        drive_count = dc_drives.count()
        status_counts = {status: dc_drives.filter(HardDrive.status == status).count() for status in DriveStatus}
        stats[dc] = {
            "total_drives": drive_count,
            "total_capacity_gb": total_capacity,
            "status_counts": status_counts
        }
    return stats

@app.get("/hard_drives/similar/{hard_drive_id}", response_model=List[HardDriveResponse])
async def get_similar_hard_drives(hard_drive_id: int, limit: int = 5):
    db = next(get_db())
    target_drive = db.query(HardDrive).filter(HardDrive.id == hard_drive_id).first()
    if not target_drive:
        raise HTTPException(status_code=404, detail="Hard drive not found")
    similar_drives = db.query(HardDrive).order_by(
        HardDrive.embedding.cosine_distance(target_drive.embedding)
    ).limit(limit).all()
    return [HardDriveResponse(**hd.__dict__) for hd in similar_drives]

@app.get("/hard_drives/predict_failure", response_model=List[Dict])
async def predict_hard_drive_failure():
    db = next(get_db())
    hard_drives = db.query(HardDrive).all()
    predictions = ml_model.predict([hd.__dict__ for hd in hard_drives])
    return [{"id": hd.id, "failure_probability": prob} for hd, prob in zip(hard_drives, predictions)]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Message text was: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def generate_embedding(text: str):
    # Use Azure AI to generate embeddings
    documents = [text]
    response = text_analytics_client.extract_key_phrases(documents)
    key_phrases = response[0].key_phrases if response else []
    # Convert key phrases to a fixed-size vector (simplified for this example)
    return [len(phrase) for phrase in key_phrases][:384]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
