from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import json, uuid
from sqlalchemy.orm import Session
from database import SessionLocal, Product, Addon, Event, Banner, Contact, Admin, Order, init_db
from datetime import datetime, timedelta, timezone
from auth import authenticate_admin, create_access_token, init_admin, verify_token
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize admin account at startup
    db = next(get_db())
    init_admin(db)
    yield

app = FastAPI(
    title="JustTreats API", 
    description="API for managing cake and pastry orders",
    lifespan=lifespan
)

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

# Setup security
security = HTTPBearer()

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

# Banner Model
class BannerModel(BaseModel):
    enabled: bool
    imageUrl: str
    title: str
    description: str

# Contact Model
class ContactModel(BaseModel):
    instagram: str
    whatsapp: str
    email: str

# Admin Login Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

# Order Models
class OrderAddon(BaseModel):
    addonId: int
    quantity: int
    notes: Optional[str] = ""

class OrderItem(BaseModel):
    productId: int
    quantity: int
    addons: List[OrderAddon] = []

class OrderCustomer(BaseModel):
    name: str
    email: str
    phone: str
    contactMethod: str
    delivery: bool
    deliveryAddress: Optional[str] = None
    pickupAtEvent: bool

class OrderModel(BaseModel):
    id: Optional[int] = None
    date: Optional[datetime] = None
    items: List[OrderItem]
    customer: OrderCustomer
    total: Optional[float] = None
        unique_order_id: Optional[str] = None

@app.post("/api/admin/login", response_model=AdminLoginResponse)
async def admin_login(login_data: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = authenticate_admin(db, login_data.username, login_data.password)
    if not admin:
        return AdminLoginResponse(
            success=False,
            message="Invalid credentials"
        )
        
    # Create access token
    access_token = create_access_token(
        data={"sub": admin.username, "id": admin.id}
    )
    
    return AdminLoginResponse(
        success=True,
        token=access_token,
        user={
            "id": str(admin.id),
            "username": admin.username
        }
    )

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
async def get_products(available: Optional[bool] = None, page: int = 1, size: int = 10, db: Session = Depends(get_db)):
    query = db.query(Product)

    if available is not None:
        query = query.filter(Product.available == available)

    products = query.limit(size).offset((page - 1) * size)

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

# Banner Endpoints
@app.get("/api/banner", response_model=BannerModel)
async def get_banner(db: Session = Depends(get_db)):
    banner = db.query(Banner).first()
    if banner is None:
        raise HTTPException(status_code=404, detail="Banner configuration not found")
    return banner

@app.put("/api/banner", response_model=BannerModel)
async def update_banner(banner_config: BannerModel, db: Session = Depends(get_db)):
    # Check if banner config exists
    db_banner = db.query(Banner).first()
    
    if db_banner is None:
        # Create new banner if none exists
        db_banner = Banner(
            enabled=banner_config.enabled,
            imageUrl=banner_config.imageUrl,
            title=banner_config.title,
            description=banner_config.description
        )
        db.add(db_banner)
    else:
        # Update existing banner
        db_banner.enabled = banner_config.enabled
        db_banner.imageUrl = banner_config.imageUrl
        db_banner.title = banner_config.title
        db_banner.description = banner_config.description
    
    db.commit()
    db.refresh(db_banner)
    return db_banner

# Contact Endpoints
@app.get("/api/contact", response_model=ContactModel)
async def get_contact(db: Session = Depends(get_db)):
    contact = db.query(Contact).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact configuration not found")
    return contact

@app.put("/api/contact", response_model=ContactModel)
async def update_contact(contact_config: ContactModel, db: Session = Depends(get_db)):
    # Check if contact config exists
    db_contact = db.query(Contact).first()
    
    if db_contact is None:
        # Create new contact if none exists
        db_contact = Contact(
            instagram=contact_config.instagram,
            whatsapp=contact_config.whatsapp,
            email=contact_config.email
        )
        db.add(db_contact)
    else:
        # Update existing contact
        db_contact.instagram = contact_config.instagram
        db_contact.whatsapp = contact_config.whatsapp
        db_contact.email = contact_config.email
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

# Order Endpoints
@app.post("/api/orders", response_model=OrderModel)
async def create_order(order: OrderModel, db: Session = Depends(get_db)):
    # Set the current date
    current_date = datetime.now(timezone.utc)
    
    # Calculate total price by fetching product and addon details
    total_price = 0
    
    # Process each item in the order
    for item in order.items:
        # Get the product
        product = db.query(Product).filter(Product.id == item.productId).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with ID {item.productId} not found")
        
        # Add product price to total
        total_price += product.price * item.quantity
        
        # Process addons for this item
        for addon_item in item.addons:
            # Get the addon
            addon = db.query(Addon).filter(Addon.id == addon_item.addonId).first()
            if not addon:
                raise HTTPException(status_code=404, detail=f"Addon with ID {addon_item.addonId} not found")
            
            # Add addon price to total
            total_price += addon.price * addon_item.quantity
    
    # Create new order
    db_order = Order(
        date=current_date,
        items=json.dumps([item.model_dump() for item in order.items]),
        customer=json.dumps(order.customer.model_dump()),
        total=total_price,
        unique_order_id=uuid.uuid4().hex
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Prepare the response
    return OrderModel(
        id=db_order.id,
        date=db_order.date,
        items=order.items,
        customer=order.customer,
        total=db_order.total,
        unique_order_id=db_order.unique_order_id
    )

@app.put("/api/orders/unique/{order_id}", response_model=OrderModel)
async def update_order_by_unique_id(order_id: str, updated_order: OrderModel, db: Session = Depends(get_db)):
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Calculate total price by fetching product and addon details
    total_price = 0
    
    # Process each item in the order
    for item in updated_order.items:
        # Get the product
        product = db.query(Product).filter(Product.id == item.productId).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with ID {item.productId} not found")
        
        # Add product price to total
        total_price += product.price * item.quantity
        
        # Process addons for this item
        for addon_item in item.addons:
            # Get the addon
            addon = db.query(Addon).filter(Addon.id == addon_item.addonId).first()
            if not addon:
                raise HTTPException(status_code=404, detail=f"Addon with ID {addon_item.addonId} not found")
            
            # Add addon price to total
            total_price += addon.price * addon_item.quantity
    
    # Update the order data
    db_order.items = json.dumps([item.model_dump() for item in updated_order.items])
    db_order.customer = json.dumps(updated_order.customer.model_dump())
    db_order.total = total_price
    
    db.commit()
    db.refresh(db_order)

    return updated_order

@app.get("/api/orders/unique/{unique_order_id}", response_model=OrderModel)
async def get_order_by_unique_id(unique_order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.unique_order_id == unique_order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items_data = json.loads(order.items)
    customer_data = json.loads(order.customer)
    items = [OrderItem(**item_data) for item_data in items_data]
    customer = OrderCustomer(**customer_data)

    return OrderModel(
        id=order.id,
        date=order.date,
        items=items,
        customer=customer,
        total=order.total,
        unique_order_id=order.unique_order_id
    )


@app.get("/api/orders", response_model=List[OrderModel])
async def get_orders(token_data: Dict = Depends(verify_token), db: Session = Depends(get_db)):
    # Authentication is handled by the verify_token dependency
    
    orders = db.query(Order).all()
    
    # Convert the orders from database format to response format
    result = []
    for order in orders:
        # Parse the JSON strings
        items_data = json.loads(order.items)
        customer_data = json.loads(order.customer)
        
        # Convert items data to OrderItem objects
        items = []
        for item_data in items_data:
            # Convert addons data to OrderAddon objects
            addons = []
            for addon_data in item_data.get("addons", []):
                addons.append(OrderAddon(**addon_data))
            
            # Create OrderItem with its addons
            items.append(OrderItem(
                productId=item_data["productId"],
                quantity=item_data["quantity"],
                addons=addons
            ))
        
        # Create OrderCustomer object
        customer = OrderCustomer(**customer_data)
        
        # Create complete OrderModel
        result.append(OrderModel(
            id=order.id,
            date=order.date,
            items=items,
            customer=customer,
            total=order.total,
            unique_order_id=order.unique_order_id
        ))
    
    return result

if __name__ == "__main__":
    import os
    reload = os.environ["ENV"] == "dev"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload) 