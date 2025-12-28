from pydantic import BaseModel
from typing import Optional

class Credentials(BaseModel):
    url: str
    login: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None


class BackupDetails(BaseModel):
    name: str
    path: str
    source: str
    source_id: int
    size: float
    modified: str


class UserInfo(BaseModel):
    user_id: int
    tenant_id: str
