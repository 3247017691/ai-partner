# -----------数据模型类-------
from typing import Any
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 200
    message: str = '操作成功'
    data: Any = None  # data允许任意类型的数据, 且有默认值为None


class CreateSessionRequest(BaseModel):
    nick_name: str
    nature: str


class ChatRequest(BaseModel):
    session_name: str
    message: str
    nick_name: str
    nature: str
