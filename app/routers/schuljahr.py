from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schuljahr import Schuljahr
from app.schemas.schuljahr import SchuljahreCreate, SchuljahreRead, SchuljahreUpdate

router = APIRouter(prefix="/schuljahre", tags=["Schuljahre"])


@router.get("/", response_model=list[SchuljahreRead])
def list_schuljahre(db: Session = Depends(get_db)):
    return db.query(Schuljahr).all()


@router.get("/{schuljahr_id}", response_model=SchuljahreRead)
def get_schuljahr(schuljahr_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schuljahr, schuljahr_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schuljahr nicht gefunden")
    return obj


@router.post("/", response_model=SchuljahreRead, status_code=201)
def create_schuljahr(data: SchuljahreCreate, db: Session = Depends(get_db)):
    schuljahr = Schuljahr(name=data.name)
    db.add(schuljahr)
    db.commit()
    db.refresh(schuljahr)
    return schuljahr


@router.patch("/{schuljahr_id}", response_model=SchuljahreRead)
def update_schuljahr(schuljahr_id: int, data: SchuljahreUpdate, db: Session = Depends(get_db)):
    obj = db.get(Schuljahr, schuljahr_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schuljahr nicht gefunden")
    if data.name is not None:
        obj.name = data.name
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{schuljahr_id}", status_code=204)
def delete_schuljahr(schuljahr_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schuljahr, schuljahr_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schuljahr nicht gefunden")
    try:
        db.delete(obj)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Schuljahr kann nicht gelöscht werden (hat noch Klassen)")
