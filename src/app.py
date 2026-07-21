from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.database import get_db

app = FastAPI(title="API Insper Jr - BANCAS", version="0.1.0")


@app.get("/")
def root():
    return {"message": "BANCAS API no ar"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "ok"}
