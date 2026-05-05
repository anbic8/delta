from pydantic import BaseModel, field_validator
from app.models.klasse import Notensystem


class KlasseCreate(BaseModel):
    jahrgangsstufe: int
    buchstabe: str
    schuljahr_id: int

    @field_validator("jahrgangsstufe")
    @classmethod
    def jahrgangsstufe_range(cls, v: int) -> int:
        if not (5 <= v <= 13):
            raise ValueError("Jahrgangsstufe muss zwischen 5 und 13 liegen")
        return v

    @field_validator("buchstabe")
    @classmethod
    def buchstabe_format(cls, v: str) -> str:
        if len(v) != 1 or not v.isalpha():
            raise ValueError("Buchstabe muss ein einzelner Buchstabe sein")
        return v.lower()


class KlasseRead(BaseModel):
    id: int
    jahrgangsstufe: int
    buchstabe: str
    name: str
    fach: str
    notensystem: Notensystem
    schuljahr_id: int

    model_config = {"from_attributes": True}


class KlasseUpdate(BaseModel):
    buchstabe: str | None = None

    @field_validator("buchstabe")
    @classmethod
    def buchstabe_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 1 or not v.isalpha():
            raise ValueError("Buchstabe muss ein einzelner Buchstabe sein")
        return v.lower()
