from fastapi import FastAPI
from typing import Any
import os
import json
from openai import OpenAI
from pydantic import BaseModel


app = FastAPI()

# --------常量--------
PRESET_FILE_PATH = "data/companion_presets.json"
SESSIONS_DIR = "sessions"
# 系统提示词模板
SYSTEM_PROMPT_TEMPLATE = """你叫 %s，现在是用户的真实伴侣，请完全代入伴侣角色。
    规则：
        1. 每次只回1条消息
        2. 禁止任何场景或状态描述性文字
        3. 匹配用户的语言
        4. 回复简短，像微信聊天一样
        5. 有需要的话可以用❤️🌸等emoji表情
        6. 用符合伴侣性格的方式对话
        7. 回复的内容, 要充分体现伴侣的性格特征
        8. 不要太肉麻（比如想你之类的，就日常聊天）
    伴侣性格：
        - %s
    你必须严格遵守上述规则来回复用户。
    """
# --------数据相关类--------
class ApiResponse(BaseModel):
    code: int = 200
    message: str = "操作成功"
    data: Any = None

class CreateSessionRequest(BaseModel):
    nick_name : str
    nature : str

class ChatRequest(BaseModel):
    session_name: str
    message: str
    nick_name: str
    nature: str

# --------功能函数--------
def generate_session_name():
    """生成会话名称"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 保存为函数f"sessions/{session_name}.json"
def get_session_path(session_name):
    return f"{SESSIONS_DIR}/{session_name}.json"



# 初始化OpenAI客户端
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),base_url="https://api.deepseek.com")

if not os.path.exists(SESSIONS_DIR):
    os.mkdir(SESSIONS_DIR)

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
        "messages": []
    }
    # 3.将会话名称保存成json文件，文件名称是.json，转存为session目录里
    with open(get_session_path(session_name), 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=4)
    # 4返回响应，数据为会话名称
    return ApiResponse(data=session_name)


@app.post('/api/chat')
async def chat(request: ChatRequest) -> ApiResponse:
    """AI伴侣聊天"""
    print(f"与AI交互:{request.session_name} : {request.message}")
    # 1.从会话session_name.json文件中读取会话数据
    session_path = get_session_path(request.session_name)
    if not os.path.exists(session_path):
        return ApiResponse(code=404, message="会话不存在")
    with open(session_path, 'r', encoding='utf-8') as f:
        session_data = json.load(f)

    # 2.拼接系统提示词
    system_prompt = SYSTEM_PROMPT_TEMPLATE % (request.nick_name, request.nature)

    # 3.构建消息列表
    history = session_data.get("messages", [])
    messages = [{"role": "system", "content": system_prompt}]
    for message in history:
        messages.append(message)
    messages.append({"role": "user", "content": request.message})

    # 4.调用Deepseek API进行聊天
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=messages,
        stream=False
    )
    # 5. 获取响应的数据
    ai_response = response.choices[0].message.content
    print(f"AI回复:{ai_response}")

    # 6. 更新消息列表中的消息
    messages.pop(0)
    messages.append({"role": "assistant", "content": ai_response})
    session_data["messages"] = messages
    print(f"会话数据:{session_data}")

    # 7. 保存会话信息到json文件中
    with open(session_path, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=4)

    # 8.返回响应，数据为AI的回复内容
    return ApiResponse(data=ai_response)


@app.get("/api/sessions", summary="获取所有会话列表，按时间顺序降序排列（最新的会话排在最前）")
async def sessions():
    """获取所有会话列表，按时间顺序降序排列（最新的会话排在最前）"""
    sessions_list = []
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith(".json"):
            session_name = filename[:-5]  # 去掉.json后缀
            sessions_list.append(session_name)
    sessions_list.sort(reverse=True)
    return ApiResponse(data=sessions_list)


@app.get("/api/sessions/{session_name}", summary="获取指定会话数据", response_model=ApiResponse)
async def session_find(session_name: str):
    """获取指定会话数据"""
    print(f"获取会话数据:{session_name}")
    session_path = get_session_path(session_name)
    # 1.验证会话文件是否存在
    if not os.path.exists(session_path):
        return ApiResponse(code=404, message="会话不存在")
    # 2.读取会话文件内容
    with open(session_path, 'r', encoding='utf-8') as f:
        session_data = json.load(f)
    # 3.返回响应，数据为会话数据
    return ApiResponse(data=session_data)


@app.delete("/api/sessions/{session_name}", summary="删除指定会话", response_model=ApiResponse)
def session_delete(session_name: str):
    """删除指定会话"""
    print(f"删除会话:{session_name}")
    # 1.先获取会话路径
    session_path = get_session_path(session_name)
    # 2.验证会话文件是否存在
    if not os.path.exists(session_path):
        return ApiResponse(code=404, message="会话不存在")
    # 3.删除会话文件
    os.remove(session_path)
    print(f"会话文件已删除:{session_path}")
    # 4.返回响应，提示会话删除成功
    return ApiResponse(message="会话删除成功")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000,)