from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.kompetenz import Kompetenz
from app.schemas.kompetenz import KompetenzRead

router = APIRouter(prefix="/kompetenzen", tags=["Kompetenzen"])


@router.get("/", response_model=list[KompetenzRead])
def list_kompetenzen(db: Session = Depends(get_db)):
    return db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
