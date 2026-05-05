from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.aufgabe import Aufgabe
from app.models.klasse import Klasse
from app.models.schriftliche_leistung import LeistungAufgabe, LeistungArt, SchriftlicheLeistung
from app.schemas.schriftliche_leistung import (
    LeistungAufgabeCreate, LeistungAufgabeRead,
    SchriftlicheLeistungCreate, SchriftlicheLeistungRead, SchriftlicheLeistungUpdate,
)

router = APIRouter(prefix="/schriftliche-leistungen", tags=["Schriftliche Leistungen"])


@router.get("/", response_model=list[SchriftlicheLeistungRead])
def list_leistungen(klasse_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(SchriftlicheLeistung)
    if klasse_id is not None:
        q = q.filter(SchriftlicheLeistung.klasse_id == klasse_id)
    return q.all()


@router.get("/{leistung_id}", response_model=SchriftlicheLeistungRead)
def get_leistung(leistung_id: int, db: Session = Depends(get_db)):
    obj = db.get(SchriftlicheLeistung, leistung_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    return obj


@router.post("/", response_model=SchriftlicheLeistungRead, status_code=201)
def create_leistung(data: SchriftlicheLeistungCreate, db: Session = Depends(get_db)):
    if not db.get(Klasse, data.klasse_id):
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    leistung = SchriftlicheLeistung(**data.model_dump())
    db.add(leistung)
    db.commit()
    db.refresh(leistung)
    return leistung


@router.patch("/{leistung_id}", response_model=SchriftlicheLeistungRead)
def update_leistung(leistung_id: int, data: SchriftlicheLeistungUpdate, db: Session = Depends(get_db)):
    obj = db.get(SchriftlicheLeistung, leistung_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{leistung_id}", status_code=204)
def delete_leistung(leistung_id: int, db: Session = Depends(get_db)):
    obj = db.get(SchriftlicheLeistung, leistung_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    db.delete(obj)
    db.commit()


@router.get("/{leistung_id}/aufgaben", response_model=list[LeistungAufgabeRead])
def list_aufgaben(leistung_id: int, db: Session = Depends(get_db)):
    if not db.get(SchriftlicheLeistung, leistung_id):
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    return (
        db.query(LeistungAufgabe)
        .filter(LeistungAufgabe.leistung_id == leistung_id)
        .order_by(LeistungAufgabe.reihenfolge)
        .all()
    )


@router.post("/{leistung_id}/aufgaben", response_model=LeistungAufgabeRead, status_code=201)
def add_aufgabe(leistung_id: int, data: LeistungAufgabeCreate, db: Session = Depends(get_db)):
    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if not leistung:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    if not leistung.detailliert:
        raise HTTPException(status_code=400, detail="Pauschale Leistungen haben keine Aufgaben")
    if not db.get(Aufgabe, data.aufgabe_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    la = LeistungAufgabe(
        leistung_id=leistung_id,
        aufgabe_id=data.aufgabe_id,
        aufgabennummer=data.aufgabennummer,
        reihenfolge=data.reihenfolge,
    )
    db.add(la)
    db.commit()
    db.refresh(la)
    return la


@router.delete("/{leistung_id}/aufgaben/{la_id}", status_code=204)
def remove_aufgabe(leistung_id: int, la_id: int, db: Session = Depends(get_db)):
    obj = db.query(LeistungAufgabe).filter(
        LeistungAufgabe.id == la_id, LeistungAufgabe.leistung_id == leistung_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Aufgabe nicht in dieser Leistung")
    db.delete(obj)
    db.commit()
