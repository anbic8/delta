from datetime import datetime
from pydantic import BaseModel


class SchuelerCreate(BaseModel):
    vorname: str
    nachname: str
    klasse_id: int


class SchuelerRead(BaseModel):
    id: int
    vorname: str
    nachname: str
    pseudonym_id: str
    klasse_id: int
    geloescht_am: datetime | None

    model_config = {"from_attributes": True}


class SchuelerUpdate(BaseModel):
    vorname: str | None = None
    nachname: str | None = None
