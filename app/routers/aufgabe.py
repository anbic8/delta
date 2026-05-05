import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.aufgabe import AfbNiveau, Aufgabe, AufgabeKompetenz
from app.models.kompetenz import Kompetenz
from app.schemas.aufgabe import (
    AufgabeCreate, AufgabeKompetenzCreate, AufgabeKompetenzRead, AufgabeRead, AufgabeUpdate,
)

router = APIRouter(prefix="/aufgaben", tags=["Aufgaben"])


@router.get("/", response_model=list[AufgabeRead])
def list_aufgaben(
    suche: str | None = None,
    afb: AfbNiveau | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Aufgabe)
    if suche:
        term = f"%{suche}%"
        q = q.filter(
            sa.or_(
                Aufgabe.titel.ilike(term),
                Aufgabe.aufgabenstellung.ilike(term),
                Aufgabe.loesung.ilike(term),
                Aufgabe.tags.ilike(term),
            )
        )
    if afb:
        q = q.filter(Aufgabe.afb_niveau == afb)
    return q.all()


@router.get("/{aufgabe_id}", response_model=AufgabeRead)
def get_aufgabe(aufgabe_id: int, db: Session = Depends(get_db)):
    obj = db.get(Aufgabe, aufgabe_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    return obj


@router.post("/", response_model=AufgabeRead, status_code=201)
def create_aufgabe(data: AufgabeCreate, db: Session = Depends(get_db)):
    aufgabe = Aufgabe(**data.model_dump())
    db.add(aufgabe)
    db.commit()
    db.refresh(aufgabe)
    return aufgabe


@router.patch("/{aufgabe_id}", response_model=AufgabeRead)
def update_aufgabe(aufgabe_id: int, data: AufgabeUpdate, db: Session = Depends(get_db)):
    obj = db.get(Aufgabe, aufgabe_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{aufgabe_id}", status_code=204)
def delete_aufgabe(aufgabe_id: int, db: Session = Depends(get_db)):
    obj = db.get(Aufgabe, aufgabe_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    db.delete(obj)
    db.commit()


@router.get("/{aufgabe_id}/kompetenzen", response_model=list[AufgabeKompetenzRead])
def get_kompetenzen(aufgabe_id: int, db: Session = Depends(get_db)):
    if not db.get(Aufgabe, aufgabe_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    return db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == aufgabe_id).all()


@router.put("/{aufgabe_id}/kompetenzen", response_model=list[AufgabeKompetenzRead])
def set_kompetenzen(aufgabe_id: int, data: list[AufgabeKompetenzCreate], db: Session = Depends(get_db)):
    if not db.get(Aufgabe, aufgabe_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    if data:
        gesamt = sum(k.gewichtung for k in data)
        if abs(gesamt - 1.0) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Kompetenz-Gewichtungen müssen 1.0 ergeben (aktuell: {gesamt:.2f})",
            )
        for k in data:
            if not db.get(Kompetenz, k.kompetenz_id):
                raise HTTPException(status_code=404, detail=f"Kompetenz {k.kompetenz_id} nicht gefunden")
    db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == aufgabe_id).delete()
    for k in data:
        db.add(AufgabeKompetenz(aufgabe_id=aufgabe_id, kompetenz_id=k.kompetenz_id, gewichtung=k.gewichtung))
    db.commit()
    return db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == aufgabe_id).all()
