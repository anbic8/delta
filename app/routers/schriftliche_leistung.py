from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.aufgabe import Aufgabe
from app.models.klasse import Klasse
from app.models.schueler import Schueler
from app.models.schueler_ergebnis import SchuelerErgebnis
from app.models.schriftliche_leistung import LeistungAufgabe, LeistungArt, SchriftlicheLeistung
from app.schemas.schriftliche_leistung import (
    LeistungAufgabeCreate, LeistungAufgabeRead,
    SchriftlicheLeistungCreate, SchriftlicheLeistungRead, SchriftlicheLeistungUpdate,
)
from app.schemas.schueler_ergebnis import (
    DetailliertEintrag, PauschalEintrag, SAKlassenauswertung,
    AufgabeSpalte, SchuelerZeile, NoteStats,
)
from app.services import notenberechnung

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


# --- Ergebnisse eintragen ---

@router.put("/{leistung_id}/ergebnisse/detailliert", status_code=204)
def set_ergebnisse_detailliert(
    leistung_id: int, eintraege: list[DetailliertEintrag], db: Session = Depends(get_db)
):
    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if not leistung:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    if not leistung.detailliert:
        raise HTTPException(status_code=400, detail="Leistung ist pauschal – bitte /ergebnisse/pauschal verwenden")
    if not leistung.leistung_aufgaben:
        raise HTTPException(status_code=400, detail="Keine Aufgaben vorhanden – zuerst Aufgaben zuordnen")

    la_map = {la.id: la for la in leistung.leistung_aufgaben}
    la_ids_der_leistung = set(la_map.keys())

    for e in eintraege:
        if e.leistung_aufgabe_id not in la_ids_der_leistung:
            raise HTTPException(status_code=400, detail=f"LeistungAufgabe {e.leistung_aufgabe_id} gehört nicht zu dieser Leistung")
        max_p = la_map[e.leistung_aufgabe_id].aufgabe.max_punkte
        if e.erreichte_punkte < 0 or e.erreichte_punkte > max_p:
            raise HTTPException(status_code=422, detail=f"Punkte {e.erreichte_punkte} außerhalb [0, {max_p}]")

    # Bestehende Einträge dieser Leistung löschen und neu schreiben
    db.query(SchuelerErgebnis).filter(
        SchuelerErgebnis.leistung_aufgabe_id.in_(la_ids_der_leistung)
    ).delete(synchronize_session=False)

    for e in eintraege:
        db.add(SchuelerErgebnis(
            schueler_id=e.schueler_id,
            leistung_aufgabe_id=e.leistung_aufgabe_id,
            erreichte_punkte=e.erreichte_punkte,
        ))
    db.commit()


@router.put("/{leistung_id}/ergebnisse/pauschal", status_code=204)
def set_ergebnisse_pauschal(
    leistung_id: int, eintraege: list[PauschalEintrag], db: Session = Depends(get_db)
):
    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if not leistung:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    if leistung.detailliert:
        raise HTTPException(status_code=400, detail="Leistung ist detailliert – bitte /ergebnisse/detailliert verwenden")

    notensystem = leistung.klasse.notensystem
    from app.models.klasse import Notensystem
    for e in eintraege:
        if notensystem == Notensystem.sechserskala and not (1 <= e.pauschalnote <= 6):
            raise HTTPException(status_code=422, detail="Note muss zwischen 1 und 6 liegen (Sechserskala)")
        if notensystem == Notensystem.punkte and not (0 <= e.pauschalnote <= 15):
            raise HTTPException(status_code=422, detail="Note muss zwischen 0 und 15 liegen (Punkteskala)")

    db.query(SchuelerErgebnis).filter(
        SchuelerErgebnis.schriftliche_leistung_id == leistung_id
    ).delete(synchronize_session=False)

    for e in eintraege:
        db.add(SchuelerErgebnis(
            schueler_id=e.schueler_id,
            schriftliche_leistung_id=leistung_id,
            pauschalnote=e.pauschalnote,
        ))
    db.commit()


# --- SA-Klassenauswertung ---

@router.get("/{leistung_id}/auswertung", response_model=SAKlassenauswertung)
def auswertung(leistung_id: int, db: Session = Depends(get_db)):
    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if not leistung:
        raise HTTPException(status_code=404, detail="Schriftliche Leistung nicht gefunden")
    if not leistung.detailliert:
        raise HTTPException(status_code=400, detail="Auswertung nur für detaillierte Leistungen verfügbar")
    if not leistung.leistung_aufgaben:
        raise HTTPException(status_code=400, detail="Keine Aufgaben vorhanden")

    aufgaben_sorted = sorted(leistung.leistung_aufgaben, key=lambda la: la.reihenfolge)
    max_punkte_gesamt = sum(la.aufgabe.max_punkte for la in aufgaben_sorted)

    schueler_liste = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )

    schueler_zeilen = []
    for s in schueler_liste:
        punkte_map: dict[str, float | None] = {}
        summe = 0.0
        alle_eingetragen = True
        for la in aufgaben_sorted:
            ergebnis = db.query(SchuelerErgebnis).filter(
                SchuelerErgebnis.schueler_id == s.id,
                SchuelerErgebnis.leistung_aufgabe_id == la.id,
            ).first()
            p = ergebnis.erreichte_punkte if ergebnis else None
            punkte_map[la.aufgabennummer] = p
            if p is None:
                alle_eingetragen = False
            else:
                summe += p

        if alle_eingetragen:
            note = notenberechnung.punkte_zu_note(summe, max_punkte_gesamt)
            grenzfall = notenberechnung.ist_grenzfall(summe, max_punkte_gesamt)
            prozent = round(summe / max_punkte_gesamt * 100, 1)
        else:
            note, grenzfall, prozent = None, False, None
            summe = None  # type: ignore

        schueler_zeilen.append(SchuelerZeile(
            schueler_id=s.id,
            name=f"{s.nachname}, {s.vorname}",
            punkte_pro_aufgabe=punkte_map,
            summe=summe,
            prozent=prozent,
            note=note,
            grenzfall=grenzfall,
        ))

    noten = [z.note for z in schueler_zeilen if z.note is not None]
    notenverteilung = {
        str(i): NoteStats(
            anzahl=(c := noten.count(i)),
            prozent=round(c / len(noten) * 100, 1) if noten else 0.0,
        )
        for i in range(1, 7)
    }
    klassendurchschnitt = round(sum(noten) / len(noten), 2) if noten else None

    return SAKlassenauswertung(
        leistung_id=leistung_id,
        titel=leistung.titel,
        aufgaben=[AufgabeSpalte(aufgabennummer=la.aufgabennummer, max_punkte=la.aufgabe.max_punkte) for la in aufgaben_sorted],
        max_punkte_gesamt=max_punkte_gesamt,
        schueler=schueler_zeilen,
        notenverteilung=notenverteilung,
        klassendurchschnitt=klassendurchschnitt,
    )
