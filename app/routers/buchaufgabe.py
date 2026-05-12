import csv
import io

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.aufgabe import AfbNiveau
from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
from app.models.kompetenz import Kompetenz
from app.schemas.buchaufgabe import BuchaufgabeImportErgebnis, BuchaufgabeRead

router = APIRouter(prefix="/buchaufgaben", tags=["Buchaufgaben"])

_KOMPETENZEN = ["K1", "K2", "K3", "K4", "K5", "K6"]


@router.get("/", response_model=list[BuchaufgabeRead])
def list_buchaufgaben(
    buch: str | None = None,
    kapitel: str | None = None,
    kompetenz_id: int | None = None,
    afb: AfbNiveau | None = None,
    suche: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Buchaufgabe)
    if buch:
        q = q.filter(Buchaufgabe.buch.ilike(f"%{buch}%"))
    if kapitel:
        q = q.filter(Buchaufgabe.kapitel.ilike(f"%{kapitel}%"))
    if afb:
        q = q.filter(Buchaufgabe.afb_niveau == afb)
    if suche:
        term = f"%{suche}%"
        q = q.filter(sa.or_(Buchaufgabe.beschreibung.ilike(term), Buchaufgabe.buch.ilike(term)))
    if kompetenz_id:
        q = q.join(BuchaufgabeKompetenz).filter(BuchaufgabeKompetenz.kompetenz_id == kompetenz_id)
    return q.order_by(Buchaufgabe.buch, Buchaufgabe.kapitel, Buchaufgabe.aufgabennummer).all()


@router.get("/{ba_id}", response_model=BuchaufgabeRead)
def get_buchaufgabe(ba_id: int, db: Session = Depends(get_db)):
    obj = db.get(Buchaufgabe, ba_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Buchaufgabe nicht gefunden")
    return obj


@router.delete("/{ba_id}", status_code=204)
def delete_buchaufgabe(ba_id: int, db: Session = Depends(get_db)):
    obj = db.get(Buchaufgabe, ba_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Buchaufgabe nicht gefunden")
    db.delete(obj)
    db.commit()


@router.post("/import", response_model=BuchaufgabeImportErgebnis)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    CSV-Format (Kopfzeile erforderlich):
    Buch,Kapitel,Seite,Aufgabennummer,Beschreibung,AFB,Wichtigkeit,Kompetenz

    Kompetenz: K1–K6 (optional). Idempotent: (Buch+Kapitel+Aufgabennummer) als Schlüssel.
    """
    raw = await file.read()
    content = raw.decode("utf-8", errors="replace").lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(content)))

    importiert = aktualisiert = fehler = 0
    fehler_details: list[str] = []

    # Kompetenz-Kuerzel → ID mapping
    k_map = {k.kuerzel: k.id for k in db.query(Kompetenz).all()}

    for i, row in enumerate(rows, 2):
        try:
            # Buch: entweder direktes "Buch"-Feld oder aus "Jahrgangsstufe" ableiten
            buch = row.get("Buch", "").strip()
            if not buch:
                js = row.get("Jahrgangsstufe", "").strip()
                if js.isdigit():
                    buch = f"Lambacher Schweizer {js} Bayern"
            kapitel = row.get("Kapitel", "").strip()
            # "Aufgabe" und "Aufgabennummer" beide akzeptieren
            aufgnr = (row.get("Aufgabennummer") or row.get("Aufgabe") or "").strip()
            if not buch or not kapitel or not aufgnr:
                raise ValueError("Buch/Jahrgangsstufe, Kapitel und Aufgabe sind Pflichtfelder")

            afb_raw = row.get("AFB", "AFB_II").strip().upper().replace("-", "_")
            if not afb_raw.startswith("AFB_"):
                afb_raw = f"AFB_{afb_raw}"
            afb = AfbNiveau(afb_raw)

            wichtigkeit = max(1, min(3, int(row.get("Wichtigkeit", "2").strip() or "2")))
            seite_raw = row.get("Seite", "").strip()
            seite = int(seite_raw) if seite_raw.isdigit() else None
            beschreibung = row.get("Beschreibung", "").strip() or None
            unterkapitel = row.get("Unterkapitel", "").strip()
            kompetenz_kuerzel = row.get("Kompetenz", "").strip().upper() or None
            mfp_raw = row.get("Minimalfahrplan", "").strip().lower()
            minimalfahrplan = mfp_raw in ("ja", "true", "1", "x", "yes")

            existing = db.query(Buchaufgabe).filter(
                Buchaufgabe.buch == buch,
                Buchaufgabe.kapitel == kapitel,
                Buchaufgabe.unterkapitel == unterkapitel,
                Buchaufgabe.aufgabennummer == aufgnr,
            ).first()

            if existing:
                existing.seite = seite
                existing.beschreibung = beschreibung
                existing.afb_niveau = afb
                existing.wichtigkeit = wichtigkeit
                existing.unterkapitel = unterkapitel
                existing.minimalfahrplan = minimalfahrplan
                ba = existing
                aktualisiert += 1
            else:
                ba = Buchaufgabe(
                    buch=buch, kapitel=kapitel, unterkapitel=unterkapitel,
                    seite=seite, aufgabennummer=aufgnr, beschreibung=beschreibung,
                    afb_niveau=afb, wichtigkeit=wichtigkeit,
                    minimalfahrplan=minimalfahrplan,
                )
                db.add(ba)
                db.flush()
                importiert += 1

            # Kompetenzen zuweisen (Leerzeichen- oder Semikolon-getrennte Liste, z.B. "K1 K5")
            import re as _re
            kuerzel_liste = [k for k in _re.split(r'[\s;,]+', row.get("Kompetenz", "").strip().upper()) if k in k_map]
            if kuerzel_liste:
                db.query(BuchaufgabeKompetenz).filter(BuchaufgabeKompetenz.buchaufgabe_id == ba.id).delete()
                gewichtung = round(1.0 / len(kuerzel_liste), 4)
                for kuerzel in kuerzel_liste:
                    db.add(BuchaufgabeKompetenz(buchaufgabe_id=ba.id, kompetenz_id=k_map[kuerzel], gewichtung=gewichtung))

        except Exception as e:
            fehler += 1
            fehler_details.append(f"Zeile {i}: {e}")
            db.rollback()
            continue

    db.commit()
    return BuchaufgabeImportErgebnis(
        importiert=importiert, aktualisiert=aktualisiert,
        fehler=fehler, fehler_details=fehler_details[:10],
    )
