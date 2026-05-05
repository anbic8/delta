from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.klasse import Notensystem
from app.models.muendliche_note import MuendlicheNote
from app.models.schueler import Schueler
from app.schemas.muendliche_note import MuendlicheNoteCreate, MuendlicheNoteRead, MuendlicheNoteUpdate

router = APIRouter(prefix="/muendliche-noten", tags=["Mündliche Noten"])


def _note_validieren(note: float, notensystem: Notensystem) -> None:
    if notensystem == Notensystem.sechserskala and not (1 <= note <= 6):
        raise HTTPException(status_code=422, detail="Note muss zwischen 1 und 6 liegen (Sechserskala)")
    if notensystem == Notensystem.punkte and not (0 <= note <= 15):
        raise HTTPException(status_code=422, detail="Note muss zwischen 0 und 15 liegen (Punkteskala)")


@router.get("/", response_model=list[MuendlicheNoteRead])
def list_noten(schueler_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(MuendlicheNote).filter(MuendlicheNote.geloescht_am.is_(None))
    if schueler_id is not None:
        q = q.filter(MuendlicheNote.schueler_id == schueler_id)
    return q.all()


@router.get("/{note_id}", response_model=MuendlicheNoteRead)
def get_note(note_id: int, db: Session = Depends(get_db)):
    obj = db.get(MuendlicheNote, note_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Note nicht gefunden")
    return obj


@router.post("/", response_model=MuendlicheNoteRead, status_code=201)
def create_note(data: MuendlicheNoteCreate, db: Session = Depends(get_db)):
    schueler = db.get(Schueler, data.schueler_id)
    if not schueler:
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    if schueler.geloescht_am is not None:
        raise HTTPException(status_code=400, detail="Schüler ist gelöscht")
    notensystem = schueler.klasse.notensystem
    _note_validieren(data.note, notensystem)
    note = MuendlicheNote(
        schueler_id=data.schueler_id,
        datum=data.datum,
        note=data.note,
        notensystem=notensystem,
        gewichtung=data.gewichtung,
        beschreibung=data.beschreibung,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/{note_id}", response_model=MuendlicheNoteRead)
def update_note(note_id: int, data: MuendlicheNoteUpdate, db: Session = Depends(get_db)):
    obj = db.get(MuendlicheNote, note_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Note nicht gefunden")
    if obj.geloescht_am is not None:
        raise HTTPException(status_code=400, detail="Gelöschte Note kann nicht bearbeitet werden")
    if data.note is not None:
        _note_validieren(data.note, obj.notensystem)
        obj.note = data.note
    if data.datum is not None:
        obj.datum = data.datum
    if data.gewichtung is not None:
        obj.gewichtung = data.gewichtung
    if data.beschreibung is not None:
        obj.beschreibung = data.beschreibung
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    obj = db.get(MuendlicheNote, note_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Note nicht gefunden")
    if obj.geloescht_am is not None:
        raise HTTPException(status_code=400, detail="Note ist bereits gelöscht")
    obj.geloescht_am = datetime.now(timezone.utc)
    db.commit()
