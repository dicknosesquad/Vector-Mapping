from sqlalchemy import Column, Integer, String, Float, Enum, func
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
import enum

Base = declarative_base()

class DataCenterLocation(str, enum.Enum):
    SEATTLE = "Seattle"
    DENVER = "Denver"

class DriveStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    MAINTENANCE = "Maintenance"
    FAILED = "Failed"

class HardDrive(Base):
    __tablename__ = "hard_drives"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String, unique=True, index=True)
    capacity_gb = Column(Integer)
    location = Column(Geometry('POINT', srid=4326))
    status = Column(Enum(DriveStatus))
    data_center = Column(Enum(DataCenterLocation))
    embedding = Column(Vector(384))  # For AI-based similarity search
