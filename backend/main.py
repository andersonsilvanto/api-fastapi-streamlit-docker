from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend import models, schemas
from backend.database import engine, get_db
from backend.metrics import setup_metrics

# Cria as tabelas na base de dados automaticamente
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Items API - Version 2",
    version="2.0.0",
    description="API do projeto app_v2 isolada via Docker Compose"
)
setup_metrics(app)

@app.get("/")
def read_root():
    return {"message": "Aplicação app_v2 a rodar com sucesso no container!"}

@app.post("/items/", response_model=schemas.ItemResponse)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    db_item = models.Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.get("/items/", response_model=List[schemas.ItemResponse])
def read_items(db: Session = Depends(get_db)):
    return db.query(models.Item).all()