from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import json
from sqlalchemy.orm import Session
from database import SessionLocal, Product, Addon, Event, init_db
from datetime import datetime

app = FastAPI(title="JustTreats API", description="API for managing cake and pastry orders")

# Initialize database
init_db()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProductModel(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    price: float
    image: str
    available: Optional[bool] = True
    applicableAddons: List[int]
    eventOnly: bool
    eventId: Optional[int] = None

# Addon Models
class AddonModel(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    price: float
    available: bool
    applicableProducts: List[int]

# Event Models
class EventModel(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    date: datetime
    endDate: datetime
    location: str
    image: str
    active: bool
    featured: bool

@app.post("/api/products", response_model=ProductModel)
async def create_product(product: ProductModel, db: Session = Depends(get_db)):    
    # Validate eventId is provided when eventOnly is true
    if product.eventOnly and product.eventId is None:
        raise HTTPException(status_code=400, detail="eventId is required when eventOnly is true")
    
    # Convert applicableAddons to JSON string
    applicable_addons_json = json.dumps(product.applicableAddons)
    
    db_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        image=product.image,
        available=product.available,
        applicableAddons=applicable_addons_json,
        eventOnly=product.eventOnly,
        eventId=product.eventId
    )
    
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return {**db_product.__dict__, "applicableAddons": json.loads(db_product.applicableAddons)}

@app.get("/api/products", response_model=List[ProductModel])
async def get_products(page: int = 1, size: int = 1, db: Session = Depends(get_db)):
    products = db.query(Product).limit(size).offset((page - 1) * size)
    return [{**product.__dict__, "applicableAddons": json.loads(product.applicableAddons)} for product in products]

@app.get("/api/products/{product_id}", response_model=ProductModel)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return {**product.__dict__, "applicableAddons": json.loads(product.applicableAddons)}

@app.put("/api/products/{product_id}", response_model=ProductModel)
async def update_product(product_id: int, updated_product: ProductModel, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Validate eventId is provided when eventOnly is true
    if updated_product.eventOnly and updated_product.eventId is None:
        raise HTTPException(status_code=400, detail="eventId is required when eventOnly is true")
    
    # Update product fields
    for field, value in updated_product.model_dump().items():
        if field == "id":
            continue
        if field == "applicableAddons":
            value = json.dumps(value)
        setattr(db_product, field, value)
    
    db.commit()
    db.refresh(db_product)
    return {**db_product.__dict__, "applicableAddons": json.loads(db_product.applicableAddons)}

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted successfully"}

# Addon Endpoints
@app.post("/api/addons", response_model=AddonModel)
async def create_addon(addon: AddonModel, db: Session = Depends(get_db)):
    # Check if addon with same ID already exists
    db_addon = db.query(Addon).filter(Addon.id == addon.id).first()
    if db_addon:
        raise HTTPException(status_code=400, detail="Addon with this ID already exists")
    
    # Convert applicableProducts to JSON string
    applicable_products_json = json.dumps(addon.applicableProducts)
    
    db_addon = Addon(
        name=addon.name,
        description=addon.description,
        price=addon.price,
        available=addon.available,
        applicableProducts=applicable_products_json
    )
    
    db.add(db_addon)
    db.commit()
    db.refresh(db_addon)
    return {**db_addon.__dict__, "applicableProducts": json.loads(db_addon.applicableProducts)}

@app.get("/api/addons", response_model=List[AddonModel])
async def get_addons(db: Session = Depends(get_db)):
    addons = db.query(Addon).all()
    return [{**addon.__dict__, "applicableProducts": json.loads(addon.applicableProducts)} for addon in addons]

@app.get("/api/addons/{addon_id}", response_model=AddonModel)
async def get_addon(addon_id: int, db: Session = Depends(get_db)):
    addon = db.query(Addon).filter(Addon.id == addon_id).first()
    if addon is None:
        raise HTTPException(status_code=404, detail="Addon not found")
    return {**addon.__dict__, "applicableProducts": json.loads(addon.applicableProducts)}

@app.put("/api/addons/{addon_id}", response_model=AddonModel)
async def update_addon(addon_id: int, updated_addon: AddonModel, db: Session = Depends(get_db)):
    db_addon = db.query(Addon).filter(Addon.id == addon_id).first()
    if db_addon is None:
        raise HTTPException(status_code=404, detail="Addon not found")
    
    # Update addon fields
    for field, value in updated_addon.model_dump().items():
        if field == "id":
            continue
        if field == "applicableProducts":
            value = json.dumps(value)
        setattr(db_addon, field, value)
    
    db.commit()
    db.refresh(db_addon)
    return {**db_addon.__dict__, "applicableProducts": json.loads(db_addon.applicableProducts)}

@app.delete("/api/addons/{addon_id}")
async def delete_addon(addon_id: int, db: Session = Depends(get_db)):
    db_addon = db.query(Addon).filter(Addon.id == addon_id).first()
    if db_addon is None:
        raise HTTPException(status_code=404, detail="Addon not found")
    
    db.delete(db_addon)
    db.commit()
    return {"message": "Addon deleted successfully"}

# Event Endpoints
@app.post("/api/events", response_model=EventModel)
async def create_event(event: EventModel, db: Session = Depends(get_db)):
    # Check if event with same ID already exists
    db_event = db.query(Event).filter(Event.id == event.id).first()
    if db_event:
        raise HTTPException(status_code=400, detail="Event with this ID already exists")
    
    # Validate endDate is after date
    if event.endDate <= event.date:
        raise HTTPException(status_code=400, detail="endDate must be after date")
    
    db_event = Event(
        name=event.name,
        description=event.description,
        date=event.date,
        endDate=event.endDate,
        location=event.location,
        image=event.image,
        active=event.active,
        featured=event.featured
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@app.get("/api/events", response_model=List[EventModel])
async def get_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events

@app.get("/api/events/{event_id}", response_model=EventModel)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@app.put("/api/events/{event_id}", response_model=EventModel)
async def update_event(event_id: int, updated_event: EventModel, db: Session = Depends(get_db)):
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Validate endDate is after date
    if updated_event.endDate <= updated_event.date:
        raise HTTPException(status_code=400, detail="endDate must be after date")
    
    # Update event fields
    for field, value in updated_event.model_dump().items():
        if field == "id":
            continue
        setattr(db_event, field, value)
    
    db.commit()
    db.refresh(db_event)
    return db_event

@app.delete("/api/events/{event_id}")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(db_event)
    db.commit()
    return {"message": "Event deleted successfully"}

if __name__ == "__main__":
    import os
    reload = os.environ["ENV"] == "dev"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload) 