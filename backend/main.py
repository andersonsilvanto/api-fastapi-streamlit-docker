import os
from typing import List

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from backend import auth, models, schemas
from backend.database import SessionLocal, engine, get_db
from backend.logging_conf import setup_logging
from backend.metrics import setup_metrics
from backend.middleware import setup_request_middleware

setup_logging()

# Cria as tabelas na base de dados automaticamente
models.Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    auth.bootstrap_admin(db)

app = FastAPI(
    title="Items API - Version 2",
    version="2.0.0",
    description="API do projeto app_v2 isolada via Docker Compose",
)
setup_metrics(app)
setup_request_middleware(app)


@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=credentials.username).first()
    if user is None or not auth.verify_user_password(user, credentials.password):
        raise auth.invalid_login()

    return {
        "access_token": auth.create_access_token(user, ["items:read", "items:write"]),
        "must_change_password": user.must_change_password,
    }


@app.post("/auth/change-password", response_model=schemas.TokenResponse)
def change_password(
    request: schemas.ChangePasswordRequest,
    claims: dict = Depends(auth.authenticated_claims),
    db: Session = Depends(get_db),
):
    user = auth.get_user_for_claims(db, claims)
    if not auth.verify_user_password(user, request.current_password):
        raise auth.invalid_login()

    try:
        auth.passwords.validate_password(
            request.new_password,
            development_mode=os.getenv("APP_ENV", "production").lower()
            == "development",
        )
    except ValueError as error:
        raise auth.password_policy_error(error) from error

    if auth.passwords.verify_password(request.new_password, user.password_hash):
        raise auth.password_policy_error("New password must differ from the current password.")

    user.password_hash = auth.passwords.hash_password(request.new_password)
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return {
        "access_token": auth.create_access_token(user, ["items:read", "items:write"]),
        "must_change_password": False,
    }


@app.get("/")
def read_root():
    return {"message": "Aplicação app_v2 a rodar com sucesso no container!"}


@app.post("/items/", response_model=schemas.ItemResponse)
def create_item(
    item: schemas.ItemCreate,
    _claims: dict = Depends(auth.require_scope("items:write")),
    db: Session = Depends(get_db),
):
    db_item = models.Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/items/", response_model=List[schemas.ItemResponse])
def read_items(
    _claims: dict = Depends(auth.require_scope("items:read")),
    db: Session = Depends(get_db),
):
    return db.query(models.Item).all()
