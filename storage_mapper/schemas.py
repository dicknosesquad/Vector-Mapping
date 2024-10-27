from pydantic import BaseModel
from typing import List
from .models import DriveStatus, DataCenterLocation

class HardDriveCreate(BaseModel):
    serial_number: str
    capacity_gb: int
    latitude: float
    longitude: float
    status: DriveStatus
    data_center: DataCenterLocation

class HardDriveResponse(BaseModel):
    id: int
    serial_number: str
    capacity_gb: int
    latitude: float
    longitude: float
    status: DriveStatus
    data_center: DataCenterLocation
