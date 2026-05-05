from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.klasse import Klasse
from app.models.schueler import Schueler
from app.schemas.schueler import SchuelerCreate, SchuelerRead, SchuelerUpdate

router = APIRouter(prefix="/schueler", tags=["Schüler"])


@router.get("/{schueler_id}", response_model=SchuelerRead)
def get_schueler(schueler_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schueler, schueler_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    return obj


@router.post("/", response_model=SchuelerRead, status_code=201)
def create_schueler(data: SchuelerCreate, db: Session = Depends(get_db)):
    if not db.get(Klasse, data.klasse_id):
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    schueler = Schueler(vorname=data.vorname, nachname=data.nachname, klasse_id=data.klasse_id)
    db.add(schueler)
    db.commit()
    db.refresh(schueler)
    return schueler


@router.patch("/{schueler_id}", response_model=SchuelerRead)
def update_schueler(schueler_id: int, data: SchuelerUpdate, db: Session = Depends(get_db)):
    obj = db.get(Schueler, schueler_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    if data.vorname is not None:
        obj.vorname = data.vorname
    if data.nachname is not None:
        obj.nachname = data.nachname
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{schueler_id}", status_code=204)
def delete_schueler(schueler_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schueler, schueler_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    if obj.geloescht_am is not None:
        raise HTTPException(status_code=400, detail="Schüler ist bereits gelöscht")
    obj.geloescht_am = datetime.now(timezone.utc)
    db.commit()
