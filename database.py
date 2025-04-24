from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variable, default to SQLite if not set
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./justreats.db")

# Configure engine based on database type
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
    image = Column(String)
    available = Column(Boolean, default=True)
    eventOnly = Column(Boolean, default=False)
    eventId = Column(Integer, nullable=True)

    # For storing applicableAddons as a JSON string
    applicableAddons = Column(String)

class Addon(Base):
    __tablename__ = "addons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
    available = Column(Boolean, default=True)
    
    # For storing applicableProducts as a JSON string
    applicableProducts = Column(String)

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    date = Column(DateTime)
    endDate = Column(DateTime)
    location = Column(String)
    image = Column(String)
    active = Column(Boolean, default=True)
    featured = Column(Boolean, default=False)

class Banner(Base):
    __tablename__ = "banners"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=True)
    imageUrl = Column(String)
    title = Column(String)
    description = Column(String)

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    instagram = Column(String)
    whatsapp = Column(String)
    email = Column(String)

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.now)
    unique_order_id = Column(String, unique=True)
    items = Column(String)  # JSON string of ordered items
    customer = Column(String)  # JSON string of customer information
    total = Column(Float)

    def generate_unique_id(self):
        # Generate a unique ID using a combination of random letters and numbers
        self.unique_order_id = str(uuid.uuid4()).replace("-", "")[:12]  # 12 characters long


def init_db():
    Base.metadata.create_all(bind=engine)




def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 