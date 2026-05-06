from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.klasse import Klasse
from app.models.schueler import Schueler
from app.schemas.schueler import SchuelerCreate, SchuelerRead, SchuelerUpdate
from app.models.kompetenz import Kompetenz
from app.schemas.schnitt import SchuelerSchnittRead
from app.schemas.schueler_ergebnis import KompetenzprofilRead, KompetenzScore
from app.schemas.empfehlung import EmpfehlungRead
from app.services import kompetenzprofil as kp_service
from app.services import notenschnitt
from app.services import empfehlung as emp_service

router = APIRouter(prefix="/schueler", tags=["Schüler"])


@router.get("/{schueler_id}/schnitt", response_model=SchuelerSchnittRead)
def get_schnitt(schueler_id: int, db: Session = Depends(get_db)):
    if not db.get(Schueler, schueler_id):
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    return SchuelerSchnittRead(
        schueler_id=schueler_id,
        schnitt_kleine_ln=notenschnitt.schnitt_kleine_ln(schueler_id, db),
        schnitt_grosse_ln=notenschnitt.schnitt_grosse_ln(schueler_id, db),
        gesamtschnitt=notenschnitt.gesamtschnitt(schueler_id, db),
    )


@router.get("/{schueler_id}/empfehlung", response_model=list[EmpfehlungRead])
def get_empfehlung(schueler_id: int, anzahl: int = 5, db: Session = Depends(get_db)):
    if not db.get(Schueler, schueler_id):
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    return emp_service.empfehlungen(schueler_id, db, anzahl=anzahl)


@router.get("/{schueler_id}/kompetenzprofil", response_model=KompetenzprofilRead)
def get_kompetenzprofil(schueler_id: int, db: Session = Depends(get_db)):
    if not db.get(Schueler, schueler_id):
        raise HTTPException(status_code=404, detail="Schüler nicht gefunden")
    profil = kp_service.berechne_profil(schueler_id, db)
    meta = kp_service.metadaten(schueler_id, db)
    scores = []
    for k_id, prozent in profil.items():
        k = db.get(Kompetenz, k_id)
        if k:
            scores.append(KompetenzScore(kompetenz_id=k_id, kuerzel=k.kuerzel, bezeichnung=k.bezeichnung, prozent=prozent))
    scores.sort(key=lambda s: s.kuerzel)
    return KompetenzprofilRead(schueler_id=schueler_id, scores=scores, **meta)


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
