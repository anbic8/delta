from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.klasse import Klasse, Notensystem
from app.models.schueler import Schueler
from app.models.schuljahr import Schuljahr
from app.schemas.klasse import KlasseCreate, KlasseRead, KlasseUpdate
from app.schemas.schueler import SchuelerRead

router = APIRouter(prefix="/klassen", tags=["Klassen"])


def _notensystem(jahrgangsstufe: int) -> Notensystem:
    return Notensystem.sechserskala if jahrgangsstufe <= 11 else Notensystem.punkte


@router.get("/", response_model=list[KlasseRead])
def list_klassen(schuljahr_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Klasse)
    if schuljahr_id is not None:
        q = q.filter(Klasse.schuljahr_id == schuljahr_id)
    return q.all()


@router.get("/{klasse_id}", response_model=KlasseRead)
def get_klasse(klasse_id: int, db: Session = Depends(get_db)):
    obj = db.get(Klasse, klasse_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    return obj


@router.post("/", response_model=KlasseRead, status_code=201)
def create_klasse(data: KlasseCreate, db: Session = Depends(get_db)):
    if not db.get(Schuljahr, data.schuljahr_id):
        raise HTTPException(status_code=404, detail="Schuljahr nicht gefunden")
    klasse = Klasse(
        jahrgangsstufe=data.jahrgangsstufe,
        buchstabe=data.buchstabe,
        schuljahr_id=data.schuljahr_id,
        notensystem=_notensystem(data.jahrgangsstufe),
    )
    db.add(klasse)
    db.commit()
    db.refresh(klasse)
    return klasse


@router.patch("/{klasse_id}", response_model=KlasseRead)
def update_klasse(klasse_id: int, data: KlasseUpdate, db: Session = Depends(get_db)):
    obj = db.get(Klasse, klasse_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    if data.buchstabe is not None:
        obj.buchstabe = data.buchstabe
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{klasse_id}", status_code=204)
def delete_klasse(klasse_id: int, db: Session = Depends(get_db)):
    obj = db.get(Klasse, klasse_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    try:
        db.delete(obj)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Klasse kann nicht gelöscht werden (hat noch Schüler)")


@router.get("/{klasse_id}/schueler", response_model=list[SchuelerRead])
def list_schueler(klasse_id: int, db: Session = Depends(get_db)):
    if not db.get(Klasse, klasse_id):
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    return (
        db.query(Schueler)
        .filter(Schueler.klasse_id == klasse_id, Schueler.geloescht_am.is_(None))
        .all()
    )
