import csv
import io
import math
import unicodedata
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.aufgabe import AfbNiveau, Aufgabe, AufgabeKompetenz
from app.models.klasse import Klasse, Notensystem
from app.models.kompetenz import Kompetenz
from app.models.muendliche_note import MuendlicheNote
from app.models.schueler import Schueler
from app.models.schueler_ergebnis import SchuelerErgebnis
from app.models.schriftliche_leistung import LeistungAufgabe, LeistungArt, SchriftlicheLeistung
from app.models.schuljahr import Schuljahr
from app.services import notenberechnung, notenschnitt
from app.services import kompetenzprofil as kp_service
from app.templates_config import templates

router = APIRouter(prefix="/ui", include_in_schema=False)

REDIRECT = lambda url: RedirectResponse(url=url, status_code=303)


def _radar(scores_by_kuerzel: dict, size: int = 220) -> dict:
    cx = cy = size / 2
    r = size / 2 - 35
    labels = ["K1", "K2", "K3", "K4", "K5", "K6"]
    n = 6
    grid, grid_half, axes, data, label_pos = [], [], [], [], []
    for i, lbl in enumerate(labels):
        a = -math.pi / 2 + 2 * math.pi * i / n
        ox, oy = cx + r * math.cos(a), cy + r * math.sin(a)
        hx, hy = cx + r * 0.5 * math.cos(a), cy + r * 0.5 * math.sin(a)
        grid.append(f"{ox:.1f},{oy:.1f}")
        grid_half.append(f"{hx:.1f},{hy:.1f}")
        axes.append({"x2": f"{ox:.1f}", "y2": f"{oy:.1f}"})
        pct = scores_by_kuerzel.get(lbl, 0) / 100
        dx, dy = cx + r * pct * math.cos(a), cy + r * pct * math.sin(a)
        data.append(f"{dx:.1f},{dy:.1f}")
        la = 1.3
        label_pos.append({
            "x": f"{cx + r * la * math.cos(a):.1f}",
            "y": f"{cy + r * la * math.sin(a):.1f}",
            "text": lbl,
            "pct": scores_by_kuerzel.get(lbl, 0),
        })
    return {
        "size": size, "cx": cx, "cy": cy,
        "grid": " ".join(grid), "grid_half": " ".join(grid_half),
        "data": " ".join(data), "axes": axes, "labels": label_pos,
    }


# ── Schuljahre ────────────────────────────────────────────────

@router.get("/schuljahre")
def schuljahre_liste(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "schuljahre.html", {
        "schuljahre": db.query(Schuljahr).order_by(Schuljahr.name.desc()).all(),
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


@router.post("/schuljahre")
def schuljahr_erstellen(name: str = Form(...), db: Session = Depends(get_db)):
    import re
    if not re.match(r"^\d{4}/\d{2}$", name):
        return REDIRECT("/ui/schuljahre?err=Ungültiges+Format+(z.B.+2025/26)")
    existing = db.query(Schuljahr).filter(Schuljahr.name == name).first()
    if existing:
        return REDIRECT("/ui/schuljahre?err=Schuljahr+existiert+bereits")
    db.add(Schuljahr(name=name))
    db.commit()
    return REDIRECT("/ui/schuljahre?msg=Schuljahr+angelegt")


@router.post("/schuljahre/{sj_id}/loeschen")
def schuljahr_loeschen(sj_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schuljahr, sj_id)
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT("/ui/schuljahre?msg=Schuljahr+gelöscht")


# ── Klassen ───────────────────────────────────────────────────

@router.get("/klassen")
def klassen_liste(request: Request, schuljahr_id: int, db: Session = Depends(get_db)):
    sj = db.get(Schuljahr, schuljahr_id)
    klassen = db.query(Klasse).filter(Klasse.schuljahr_id == schuljahr_id).order_by(Klasse.jahrgangsstufe, Klasse.buchstabe).all()
    return templates.TemplateResponse(request, "klassen_liste.html", {
        "schuljahr": sj, "klassen": klassen,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


@router.post("/klassen")
def klasse_erstellen(schuljahr_id: int = Form(...), jahrgangsstufe: int = Form(...), buchstabe: str = Form(...), db: Session = Depends(get_db)):
    if not (5 <= jahrgangsstufe <= 13):
        return REDIRECT(f"/ui/klassen?schuljahr_id={schuljahr_id}&err=Jahrgangsstufe+muss+5-13+sein")
    notensys = Notensystem.sechserskala if jahrgangsstufe <= 11 else Notensystem.punkte
    db.add(Klasse(jahrgangsstufe=jahrgangsstufe, buchstabe=buchstabe.lower(), schuljahr_id=schuljahr_id, notensystem=notensys))
    db.commit()
    return REDIRECT(f"/ui/klassen?schuljahr_id={schuljahr_id}&msg=Klasse+angelegt")


@router.post("/klassen/{kl_id}/loeschen")
def klasse_loeschen(kl_id: int, db: Session = Depends(get_db)):
    kl = db.get(Klasse, kl_id)
    sj_id = kl.schuljahr_id if kl else 0
    if kl:
        db.delete(kl)
        db.commit()
    return REDIRECT(f"/ui/klassen?schuljahr_id={sj_id}&msg=Klasse+gelöscht")


@router.get("/klassen/{kl_id}")
def klasse_detail(kl_id: int, request: Request, db: Session = Depends(get_db)):
    kl = db.get(Klasse, kl_id)
    sj = db.get(Schuljahr, kl.schuljahr_id)
    schueler = db.query(Schueler).filter(Schueler.klasse_id == kl_id).order_by(Schueler.nachname, Schueler.vorname).all()
    leistungen = db.query(SchriftlicheLeistung).filter(SchriftlicheLeistung.klasse_id == kl_id).order_by(SchriftlicheLeistung.datum.desc()).all()
    return templates.TemplateResponse(request, "klasse_detail.html", {
        "klasse": kl, "schuljahr": sj,
        "schueler": schueler, "leistungen": leistungen,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


# ── Schüler ───────────────────────────────────────────────────

@router.post("/schueler")
def schueler_erstellen(klasse_id: int = Form(...), vorname: str = Form(...), nachname: str = Form(...), db: Session = Depends(get_db)):
    db.add(Schueler(vorname=vorname, nachname=nachname, klasse_id=klasse_id))
    db.commit()
    return REDIRECT(f"/ui/klassen/{klasse_id}?msg=Schüler+hinzugefügt")


@router.post("/schueler/{s_id}/loeschen")
def schueler_loeschen(s_id: int, db: Session = Depends(get_db)):
    s = db.get(Schueler, s_id)
    kl_id = s.klasse_id if s else 0
    if s and not s.geloescht_am:
        s.geloescht_am = datetime.utcnow()
        db.commit()
    return REDIRECT(f"/ui/klassen/{kl_id}?msg=Schüler+entfernt")


@router.get("/schueler/{s_id}")
def schueler_dashboard(s_id: int, request: Request, db: Session = Depends(get_db)):
    s = db.get(Schueler, s_id)
    kl = db.get(Klasse, s.klasse_id)
    noten = db.query(MuendlicheNote).filter(MuendlicheNote.schueler_id == s_id, MuendlicheNote.geloescht_am.is_(None)).order_by(MuendlicheNote.datum.desc()).all()

    schnitt_data = type("S", (), {
        "schnitt_kleine_ln": notenschnitt.schnitt_kleine_ln(s_id, db),
        "schnitt_grosse_ln": notenschnitt.schnitt_grosse_ln(s_id, db),
        "gesamtschnitt": notenschnitt.gesamtschnitt(s_id, db),
    })()

    profil_data = kp_service.berechne_profil(s_id, db)
    meta = kp_service.metadaten(s_id, db)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    scores_by_kuerzel = {}
    profil_scores = []
    for k in alle_k:
        pct = profil_data.get(k.id, 0)
        scores_by_kuerzel[k.kuerzel] = pct
        if k.id in profil_data:
            profil_scores.append(type("Sc", (), {"kompetenz_id": k.id, "kuerzel": k.kuerzel, "bezeichnung": k.bezeichnung, "prozent": pct})())

    profil = type("P", (), {
        "scores": profil_scores,
        "leistungen_mit_daten": meta["leistungen_mit_daten"],
        "leistungen_gesamt": meta["leistungen_gesamt"],
    })()

    return templates.TemplateResponse(request, "schueler_dashboard.html", {
        "schueler": s, "klasse": kl,
        "muendliche_noten": noten, "schnitt": schnitt_data,
        "profil": profil, "radar": _radar(scores_by_kuerzel),
        "msg": request.query_params.get("msg"),
    })


@router.post("/schueler/{s_id}/muendliche-note")
def muendliche_note_erstellen(s_id: int, datum: str = Form(...), note: float = Form(...), gewichtung: float = Form(...), beschreibung: str = Form(""), db: Session = Depends(get_db)):
    s = db.get(Schueler, s_id)
    notensys = s.klasse.notensystem
    if notensys == Notensystem.sechserskala and not (1 <= note <= 6):
        return REDIRECT(f"/ui/schueler/{s_id}?msg=Note+außerhalb+Bereich")
    if notensys == Notensystem.punkte and not (0 <= note <= 15):
        return REDIRECT(f"/ui/schueler/{s_id}?msg=Note+außerhalb+Bereich")
    from datetime import date
    db.add(MuendlicheNote(schueler_id=s_id, datum=date.fromisoformat(datum), note=note, notensystem=notensys, gewichtung=gewichtung, beschreibung=beschreibung or None))
    db.commit()
    return REDIRECT(f"/ui/schueler/{s_id}")


@router.post("/muendliche-noten/{n_id}/loeschen")
def muendliche_note_loeschen(n_id: int, db: Session = Depends(get_db)):
    n = db.get(MuendlicheNote, n_id)
    s_id = n.schueler_id if n else 0
    if n and not n.geloescht_am:
        n.geloescht_am = datetime.utcnow()
        db.commit()
    return REDIRECT(f"/ui/schueler/{s_id}")


# ── Schriftliche Leistungen ───────────────────────────────────

@router.get("/leistung-neu")
def leistung_neu_form(klasse_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "leistung_neu.html", {
        "klasse": db.get(Klasse, klasse_id),
    })


@router.post("/schriftliche-leistungen")
def leistung_erstellen(
    klasse_id: int = Form(...), datum: str = Form(...), titel: str = Form(...),
    art: str = Form(...), detailliert: str = Form(""), gewichtung: float = Form(1.0),
    db: Session = Depends(get_db),
):
    from datetime import date
    ist_detailliert = (art == "schulaufgabe") or (detailliert == "true")
    l = SchriftlicheLeistung(
        klasse_id=klasse_id, datum=date.fromisoformat(datum), titel=titel,
        art=LeistungArt(art), detailliert=ist_detailliert, gewichtung=gewichtung,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return REDIRECT(f"/ui/schriftliche-leistungen/{l.id}")


@router.get("/schriftliche-leistungen/{lid}")
def leistung_detail(lid: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(SchriftlicheLeistung, lid)
    las = sorted(l.leistung_aufgaben, key=lambda x: x.reihenfolge)
    max_p = sum(la.aufgabe.max_punkte for la in las)
    la_ids = [la.id for la in las]
    has_ergebnisse = bool(la_ids and db.query(SchuelerErgebnis).filter(SchuelerErgebnis.leistung_aufgabe_id.in_(la_ids)).count() > 0) or \
                     bool(db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schriftliche_leistung_id == lid).count() > 0)
    aufgaben_pool = db.query(Aufgabe).order_by(Aufgabe.titel).all()
    return templates.TemplateResponse(request, "leistung_detail.html", {
        "leistung": l, "leistung_aufgaben": las,
        "max_punkte_gesamt": max_p, "has_ergebnisse": has_ergebnisse,
        "aufgaben_pool": aufgaben_pool,
        "msg": request.query_params.get("msg"),
    })


@router.post("/schriftliche-leistungen/{lid}/aufgaben")
def aufgabe_zuordnen(lid: int, aufgabe_id: int = Form(...), aufgabennummer: str = Form(...), reihenfolge: int = Form(1), db: Session = Depends(get_db)):
    db.add(LeistungAufgabe(leistung_id=lid, aufgabe_id=aufgabe_id, aufgabennummer=aufgabennummer, reihenfolge=reihenfolge))
    db.commit()
    return REDIRECT(f"/ui/schriftliche-leistungen/{lid}")


@router.post("/schriftliche-leistungen/{lid}/aufgaben/{la_id}/entfernen")
def aufgabe_entfernen(lid: int, la_id: int, db: Session = Depends(get_db)):
    obj = db.query(LeistungAufgabe).filter(LeistungAufgabe.id == la_id, LeistungAufgabe.leistung_id == lid).first()
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT(f"/ui/schriftliche-leistungen/{lid}")


@router.get("/schriftliche-leistungen/{lid}/punkte")
def punkte_matrix_form(lid: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(SchriftlicheLeistung, lid)
    las = sorted(l.leistung_aufgaben, key=lambda x: x.reihenfolge)
    schueler = db.query(Schueler).filter(Schueler.klasse_id == l.klasse_id, Schueler.geloescht_am.is_(None)).order_by(Schueler.nachname, Schueler.vorname).all()
    punkte_map: dict = {}
    noten_map: dict = {}
    max_p = sum(la.aufgabe.max_punkte for la in las)
    for s in schueler:
        punkte_map[s.id] = {}
        for la in las:
            e = db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schueler_id == s.id, SchuelerErgebnis.leistung_aufgabe_id == la.id).first()
            punkte_map[s.id][la.id] = e.erreichte_punkte if e else None
        summe = sum(v for v in punkte_map[s.id].values() if v is not None)
        if all(v is not None for v in punkte_map[s.id].values()) and las:
            noten_map[s.id] = notenberechnung.punkte_zu_note(summe, max_p)
    return templates.TemplateResponse(request, "punkte_matrix.html", {
        "leistung": l, "leistung_aufgaben": las,
        "schueler": schueler, "punkte_map": punkte_map, "noten_map": noten_map,
        "max_punkte_gesamt": max_p, "notensystem": l.klasse.notensystem,
    })


@router.post("/schriftliche-leistungen/{lid}/zelle")
def punkte_zelle_speichern(lid: int, schueler_id: int = Form(...), la_id: int = Form(...), punkte: float = Form(...), db: Session = Depends(get_db)):
    existing = db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schueler_id == schueler_id, SchuelerErgebnis.leistung_aufgabe_id == la_id).first()
    if existing:
        existing.erreichte_punkte = punkte
    else:
        db.add(SchuelerErgebnis(schueler_id=schueler_id, leistung_aufgabe_id=la_id, erreichte_punkte=punkte))
    db.commit()
    return ""  # HTMX hx-swap="none"


@router.get("/schriftliche-leistungen/{lid}/pauschal")
def pauschal_form(lid: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(SchriftlicheLeistung, lid)
    schueler = db.query(Schueler).filter(Schueler.klasse_id == l.klasse_id, Schueler.geloescht_am.is_(None)).order_by(Schueler.nachname, Schueler.vorname).all()
    noten_map = {}
    for s in schueler:
        e = db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schueler_id == s.id, SchuelerErgebnis.schriftliche_leistung_id == lid).first()
        noten_map[s.id] = e.pauschalnote if e else None
    return templates.TemplateResponse(request, "pauschal_form.html", {
        "leistung": l, "schueler": schueler,
        "noten_map": noten_map, "notensystem": l.klasse.notensystem,
    })


@router.post("/schriftliche-leistungen/{lid}/pauschal")
async def pauschal_speichern(lid: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    l = db.get(SchriftlicheLeistung, lid)
    db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schriftliche_leistung_id == lid).delete()
    for key, val in form.items():
        if key.startswith("note_") and val:
            s_id = int(key.split("_")[1])
            db.add(SchuelerErgebnis(schueler_id=s_id, schriftliche_leistung_id=lid, pauschalnote=float(val)))
    db.commit()
    return REDIRECT(f"/ui/klassen/{l.klasse_id}?msg=Noten+gespeichert")


@router.get("/schriftliche-leistungen/{lid}/auswertung")
def auswertung_view(lid: int, request: Request, db: Session = Depends(get_db)):
    from app.routers.schriftliche_leistung import auswertung as api_auswertung
    data = api_auswertung(lid, db)
    return templates.TemplateResponse(request, "auswertung.html", {"auswertung": data})


# ── Aufgabenpool ──────────────────────────────────────────────

@router.get("/aufgaben")
def aufgaben_pool(request: Request, db: Session = Depends(get_db)):
    aufgaben = db.query(Aufgabe).order_by(Aufgabe.erstellt_am.desc()).all()
    return templates.TemplateResponse(request, "aufgaben_pool.html", {
        "aufgaben": aufgaben,
        "msg": request.query_params.get("msg"),
    })


@router.get("/aufgaben/suche")
def aufgaben_suche(request: Request, q: str = "", afb: str = "", db: Session = Depends(get_db)):
    import sqlalchemy as sa
    query = db.query(Aufgabe)
    if q:
        term = f"%{q}%"
        query = query.filter(sa.or_(Aufgabe.titel.ilike(term), Aufgabe.aufgabenstellung.ilike(term), Aufgabe.tags.ilike(term)))
    if afb:
        query = query.filter(Aufgabe.afb_niveau == AfbNiveau(afb))
    return templates.TemplateResponse(request, "htmx_aufgaben.html", {
        "aufgaben": query.order_by(Aufgabe.erstellt_am.desc()).all(),
    })


@router.get("/aufgaben/neu")
def aufgabe_neu_form(request: Request):
    return templates.TemplateResponse(request, "aufgabe_neu.html")


@router.post("/aufgaben")
def aufgabe_erstellen(
    titel: str = Form(...), aufgabenstellung: str = Form(...), loesung: str = Form(""),
    max_punkte: float = Form(...), afb_niveau: str = Form(...), tags: str = Form(""),
    db: Session = Depends(get_db),
):
    a = Aufgabe(titel=titel, aufgabenstellung=aufgabenstellung, loesung=loesung or None,
                max_punkte=max_punkte, afb_niveau=AfbNiveau(afb_niveau), tags=tags or None)
    db.add(a)
    db.commit()
    db.refresh(a)
    return REDIRECT(f"/ui/aufgaben/{a.id}?msg=Aufgabe+angelegt")


@router.post("/aufgaben/{a_id}/loeschen")
def aufgabe_loeschen(a_id: int, db: Session = Depends(get_db)):
    obj = db.get(Aufgabe, a_id)
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT("/ui/aufgaben?msg=Aufgabe+gelöscht")


@router.get("/aufgaben/{a_id}")
def aufgabe_detail(a_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.get(Aufgabe, a_id)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    aks = db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == a_id).all()
    kompetenzen_map = {ak.kompetenz_id: ak.gewichtung for ak in aks}
    return templates.TemplateResponse(request, "aufgabe_detail.html", {
        "aufgabe": a,
        "kompetenzen_aktuell": aks, "alle_kompetenzen": alle_k,
        "kompetenzen_map": kompetenzen_map,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


@router.post("/aufgaben/{a_id}/bearbeiten")
def aufgabe_bearbeiten(
    a_id: int, titel: str = Form(...), aufgabenstellung: str = Form(...),
    loesung: str = Form(""), max_punkte: float = Form(...),
    afb_niveau: str = Form(...), tags: str = Form(""), db: Session = Depends(get_db),
):
    a = db.get(Aufgabe, a_id)
    a.titel = titel; a.aufgabenstellung = aufgabenstellung
    a.loesung = loesung or None; a.max_punkte = max_punkte
    a.afb_niveau = AfbNiveau(afb_niveau); a.tags = tags or None
    db.commit()
    return REDIRECT(f"/ui/aufgaben/{a_id}?msg=Gespeichert")


@router.post("/aufgaben/{a_id}/kompetenzen")
async def aufgabe_kompetenzen_setzen(a_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    alle_k = db.query(Kompetenz).all()
    eintraege = []
    for k in alle_k:
        val = form.get(f"gew_{k.id}", "")
        if val:
            try:
                gew = float(val)
                if gew > 0:
                    eintraege.append((k.id, gew))
            except ValueError:
                pass
    if eintraege:
        gesamt = sum(g for _, g in eintraege)
        if abs(gesamt - 1.0) > 0.01:
            return REDIRECT(f"/ui/aufgaben/{a_id}?err=Gewichtungen+müssen+1.0+ergeben+(aktuell+{gesamt:.2f})")
    db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == a_id).delete()
    for k_id, gew in eintraege:
        db.add(AufgabeKompetenz(aufgabe_id=a_id, kompetenz_id=k_id, gewichtung=gew))
    db.commit()
    return REDIRECT(f"/ui/aufgaben/{a_id}?msg=Kompetenzen+gespeichert")


# ── CSV-Import ────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip().lower())


@router.post("/klassen/{kl_id}/schueler-import")
async def schueler_csv_import(kl_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    content = raw.decode("utf-8", errors="replace").lstrip("﻿")
    reader = csv.reader(io.StringIO(content))
    hinzugefuegt = uebersprungen = 0
    for row in reader:
        if len(row) < 2:
            continue
        nachname, vorname = row[0].strip(), row[1].strip()
        if not nachname or not vorname:
            continue
        if _normalize(nachname) in ("nachname", "name", "familienname"):
            continue
        existing = db.query(Schueler).filter(
            Schueler.klasse_id == kl_id,
            Schueler.nachname.ilike(nachname),
            Schueler.vorname.ilike(vorname),
            Schueler.geloescht_am.is_(None),
        ).first()
        if existing:
            uebersprungen += 1
        else:
            db.add(Schueler(vorname=vorname, nachname=nachname, klasse_id=kl_id))
            hinzugefuegt += 1
    db.commit()
    msg = f"{hinzugefuegt}+Schüler+hinzugefügt"
    if uebersprungen:
        msg += f",+{uebersprungen}+übersprungen"
    return REDIRECT(f"/ui/klassen/{kl_id}?msg={msg}")


@router.post("/schriftliche-leistungen/{lid}/punkte-import")
async def punkte_csv_import_vorschau(lid: int, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    leistung = db.get(SchriftlicheLeistung, lid)
    if not leistung or not leistung.detailliert:
        return REDIRECT(f"/ui/schriftliche-leistungen/{lid}")

    las = sorted(leistung.leistung_aufgaben, key=lambda x: x.reihenfolge)
    la_by_nr = {la.aufgabennummer.lower(): la for la in las}

    raw = await file.read()
    content = raw.decode("utf-8", errors="replace").lstrip("﻿")
    rows = list(csv.reader(io.StringIO(content)))
    if not rows:
        return REDIRECT(f"/ui/schriftliche-leistungen/{lid}?err=Leere+CSV")

    header = [c.strip().lower() for c in rows[0]]
    aufgaben_cols = {i: la_by_nr[h] for i, h in enumerate(header) if h in la_by_nr}

    schueler_liste = db.query(Schueler).filter(
        Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None)
    ).all()
    schueler_by_name = {(_normalize(s.nachname), _normalize(s.vorname)): s for s in schueler_liste}

    gematchte, nicht_gefunden = [], []
    for row in rows[1:]:
        if len(row) < 2 or not row[0].strip():
            continue
        nachname, vorname = row[0].strip(), row[1].strip()
        schueler = schueler_by_name.get((_normalize(nachname), _normalize(vorname)))
        punkte_row, la_ids_row = {}, {}
        for col_idx, la in aufgaben_cols.items():
            raw = row[col_idx].strip().replace(",", ".") if col_idx < len(row) else ""
            try:
                punkte_row[la.aufgabennummer] = float(raw) if raw else None
            except ValueError:
                punkte_row[la.aufgabennummer] = None
            la_ids_row[la.aufgabennummer] = la.id
        if schueler:
            gematchte.append({"schueler": schueler, "punkte": punkte_row, "la_ids": la_ids_row})
        else:
            nicht_gefunden.append(f"{nachname}, {vorname}")

    return templates.TemplateResponse(request, "punkte_import_vorschau.html", {
        "leistung": leistung, "aufgaben": las,
        "gematchte": gematchte, "nicht_gefunden": nicht_gefunden,
    })


@router.post("/schriftliche-leistungen/{lid}/punkte-import/bestaetigen")
async def punkte_import_bestaetigen(lid: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    count = 0
    for key, val in form.items():
        if not key.startswith("s_") or not val:
            continue
        parts = key.split("_")
        if len(parts) != 3:
            continue
        try:
            s_id, la_id, punkte = int(parts[1]), int(parts[2]), float(str(val).replace(",", "."))
        except ValueError:
            continue
        existing = db.query(SchuelerErgebnis).filter(
            SchuelerErgebnis.schueler_id == s_id,
            SchuelerErgebnis.leistung_aufgabe_id == la_id,
        ).first()
        if existing:
            existing.erreichte_punkte = punkte
        else:
            db.add(SchuelerErgebnis(schueler_id=s_id, leistung_aufgabe_id=la_id, erreichte_punkte=punkte))
        count += 1
    db.commit()
    return REDIRECT(f"/ui/schriftliche-leistungen/{lid}/auswertung?msg={count}+Einträge+importiert")


# ── Buchaufgaben ──────────────────────────────────────────────

@router.get("/buchaufgaben")
def buchaufgaben_liste(
    request: Request,
    buch: str = "", kompetenz_id: str = "", afb: str = "", suche: str = "",
    db: Session = Depends(get_db),
):
    from app.models.buchaufgabe import Buchaufgabe
    import sqlalchemy as sa_mod
    buecher = [r[0] for r in db.query(Buchaufgabe.buch).distinct().order_by(Buchaufgabe.buch).all()]
    gesamt = db.query(Buchaufgabe).count()
    return templates.TemplateResponse(request, "buchaufgaben.html", {
        "buecher": buecher, "kompetenzen": db.query(Kompetenz).order_by(Kompetenz.kuerzel).all(),
        "gesamt": gesamt,
        "filter_buch": buch, "filter_kompetenz_id": kompetenz_id,
        "filter_afb": afb, "filter_suche": suche,
        "buchaufgaben": _buchaufgaben_gefiltert(buch, kompetenz_id, afb, suche, db),
        "msg": request.query_params.get("msg"),
    })


@router.get("/buchaufgaben/suche")
def buchaufgaben_suche(
    request: Request,
    buch: str = "", kompetenz_id: str = "", afb: str = "", suche: str = "",
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(request, "htmx_buchaufgaben.html", {
        "buchaufgaben": _buchaufgaben_gefiltert(buch, kompetenz_id, afb, suche, db),
    })


def _buchaufgaben_gefiltert(buch, kompetenz_id, afb, suche, db):
    from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
    import sqlalchemy as sa_mod
    q = db.query(Buchaufgabe)
    if buch:
        q = q.filter(Buchaufgabe.buch == buch)
    if afb:
        q = q.filter(Buchaufgabe.afb_niveau == afb)
    if suche:
        term = f"%{suche}%"
        q = q.filter(sa_mod.or_(Buchaufgabe.beschreibung.ilike(term), Buchaufgabe.buch.ilike(term), Buchaufgabe.kapitel.ilike(term)))
    if kompetenz_id:
        try:
            q = q.join(BuchaufgabeKompetenz).filter(BuchaufgabeKompetenz.kompetenz_id == int(kompetenz_id))
        except ValueError:
            pass
    return q.order_by(Buchaufgabe.buch, Buchaufgabe.kapitel, Buchaufgabe.aufgabennummer).all()


@router.post("/buchaufgaben/import")
async def buchaufgaben_import_ui(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    from app.routers.buchaufgabe import import_csv
    ergebnis = await import_csv(file, db)
    msg = f"{ergebnis.importiert}+neu,+{ergebnis.aktualisiert}+aktualisiert"
    if ergebnis.fehler:
        msg += f",+{ergebnis.fehler}+Fehler"
    return REDIRECT(f"/ui/buchaufgaben?msg={msg}")


@router.post("/buchaufgaben/{ba_id}/loeschen")
def buchaufgabe_loeschen(ba_id: int, db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    obj = db.get(Buchaufgabe, ba_id)
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT("/ui/buchaufgaben?msg=Aufgabe+gelöscht")
