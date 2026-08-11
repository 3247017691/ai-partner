from fastapi import FastAPI
from typing import Any
import os
import json

from pydantic import BaseModel

app = FastAPI()

# --------常量--------
PRESET_FILE_PATH = "data/companion_presets.json"

# --------数据相关类--------
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "操作成功"
    data: Any = None

class CreateSessionRequest(BaseModel):
    nick_name : str
    nature : str


# --------功能函数--------
def generate_session_name():
    """生成会话名称"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 保存为函数f"session/{session_name}.json"
def save_session(session_name):
    return f"session/{session_name}.json"

# --------路由函数--------

@app.get("/", summary="根路径")
async def read_root():
    return {"message": "Hello World"}



@app.get("/api/presets", summary='取得所有AI伴侣预设数据，前端用于渲染选择下拉框')
async def presets():
    # 1.如果预设的json文件不存在，就直接返回响应，相应信息“找不到预设信息”
    if not os.path.exists(PRESET_FILE_PATH):
        return {"error": "找不到预设信息"}
    # 2.如果预设的json文件存在，就读取文件内容并返回
    with open(PRESET_FILE_PATH, 'r', encoding='utf-8') as f:
        presets_list = json.load(f)
    # 3然后按每个预设信息的sort_order进行排序排列
    presets_list.sort(key=lambda x: x['sort_order'])
    # 4返回响应，数据为排序后的预设信息列表
    return ApiResponse(data=presets_list)


@app.post("/api/sessions", summary="新建会话")
async def create_session(request: CreateSessionRequest):
    # 1.准备会话名称
    session_name = generate_session_name()
    # 2.封装会话数据
    session_data = {
        "session_name": session_name,
        "nick_name": request.nick_name,
        "nature": request.nature,
        "message": []
    }
    # 3.将会话名称保存成json文件，文件名称是.json，转存为session目录里
    with open(save_session(session_name), 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=4)
    # 4返回响应，数据为会话名称
    return ApiResponse(data=session_name)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000,)