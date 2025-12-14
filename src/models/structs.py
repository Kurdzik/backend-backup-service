from pydantic import BaseModel


class UserInfo(BaseModel):
    user_id: int
    tenant_id: str
