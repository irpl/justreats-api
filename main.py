from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import json
from sqlalchemy.orm import Session
from database import SessionLocal, Product, init_db

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


@app.post("/products", response_model=ProductModel)
async def create_product(product: ProductModel, db: Session = Depends(get_db)):    
    # Validate eventId is provided when eventOnly is true
    if product.eventOnly and product.eventId is None:
        raise HTTPException(status_code=400, detail="eventId is required when eventOnly is true")
    
    # Convert applicableAddons to JSON string
    applicable_addons_json = json.dumps(product.applicableAddons)
    
    db_product = Product(
        id=product.id,
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

@app.get("/products", response_model=List[ProductModel])
async def get_products(page: int = 1, size: int = 1, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.available == True).limit(size).offset((page - 1) * size)
    return [{**product.__dict__, "applicableAddons": json.loads(product.applicableAddons)} for product in products]

@app.get("/products/{product_id}", response_model=ProductModel)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}", response_model=ProductModel)
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

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted successfully"}

# if __name__ == "__main__":
#     import os
#     reload = os.environ["ENV"] == "dev"
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload) 