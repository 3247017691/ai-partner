from fastapi import FastAPI
from typing import Any
import os
import json

from pydantic import BaseModel

app = FastAPI()

# ————————常量—————————————
PRESET_FILE_PATH = "data/companion_presets.json"

# --------数据相关类--------
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "操作成功"
    data: Any = None


@app.get("/api/presets", summary='取得所有AI伴侣预设数据，前端用于渲染选择下拉框')
async def presets():
    # 1.如果预设的json文件不存在，就直接返回响应，相应信息“找不到预设信息”
    if not os.path.exists(PRESET_FILE_PATH):
        return {"error": "找不到预设信息"}
    # 2.如果预设的json文件存在，就读取文件内容并返回
    with open(PRESET_FILE_PATH, 'r', encoding='utf-8') as f:
        presets_list = json.load(f)
    # 然后按每个预设信息的sort_order进行排序排列
    presets_list.sort(key=lambda x: x['sort_order'])
    return ApiResponse(data=presets_list)



if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000,)