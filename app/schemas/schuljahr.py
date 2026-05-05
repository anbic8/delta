import re
from pydantic import BaseModel, field_validator


def _validate_name(v: str) -> str:
    if not re.match(r"^\d{4}/\d{2}$", v):
        raise ValueError("Format muss 'YYYY/YY' sein, z.B. '2025/26'")
    return v


class SchuljahreCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_format(cls, v: str) -> str:
        return _validate_name(v)


class SchuljahreRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class SchuljahreUpdate(BaseModel):
    name: str | None = None

    @field_validator("name")
    @classmethod
    def name_format(cls, v: str | None) -> str | None:
        return _validate_name(v) if v is not None else v
