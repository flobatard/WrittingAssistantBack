from pydantic import BaseModel


class SpellCheckRequest(BaseModel):
    text: str
    language: str = "auto"
    disabled_rules: list[str] = []
    enabled_only: bool = False
