from datetime import datetime

from pydantic import BaseModel


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    oidc_sub: str
    created_at: datetime
