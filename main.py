from datetime import datetime
from sqlalchemy import select, delete
from fastapi import FastAPI, Request, Depends
from fastapi.encoders import jsonable_encoder
from typing import Any
import os
import json
from openai import OpenAI
from pydantic import BaseModel
import logging

from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from db import AiPreset, get_db_session, AiSession, AiMessage
from starlette.responses import JSONResponse

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
    """
    通用 API 响应模型。

    该类为 API 响应提供统一的结构，包含状态码、提示信息
    和可选的数据负载。模型继承自 Pydantic 的 BaseModel，
    支持对响应数据进行校验和序列化。

    :ivar code: 表示操作结果的状态码。
    :ivar message: 描述操作结果的可读提示信息。
    :ivar data: API 返回的数据负载，可以是任意类型。
    """
    code: int = 200
    message: str = "操作成功"
    data: Any = None

class CreateSessionRequest(BaseModel):
    """
    表示创建会话的请求负载。

    该 Pydantic 模型用于校验和构造创建新会话所需的输入数据，
    继承自 ``pydantic.BaseModel``，确保字段按照类型标注
    进行解析和校验。

    :ivar nick_name: 与创建的会话关联的伴侣昵称。
    :ivar nature: 会话的性格或类型描述。
    """
    nick_name : str
    nature : str

class ChatRequest(BaseModel):
    """
    表示聊天请求负载的 Pydantic 模型。

    包含会话相关信息、消息内容、用户昵称
    以及额外的性格或上下文描述。

    :ivar session_name: 聊天会话的名称或标识。
    :ivar message: 聊天请求中发送的文本消息。
    :ivar nick_name: 发送请求的用户昵称。
    :ivar nature: 与请求关联的性格或类型描述。
    """
    session_name: str
    message: str
    nick_name: str
    nature: str

# --------功能函数--------
def generate_session_name():
    """
    根据当前日期和时间生成会话名称。

    会话名称通过将当前本地日期时间格式化为
    ``YYYY-MM-DD_HH-MM-SS`` 生成。

    :return: 生成的会话名称字符串，格式为 ``YYYY-MM-DD_HH-MM-SS``。
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 保存为函数f"sessions/{session_name}.json"
def get_session_path(session_name):
    """
    构造会话 JSON 文件的存储路径。

    路径由全局 ``SESSIONS_DIR`` 目录与会话名称拼接而成，
    并追加 ``.json`` 文件扩展名。

    :param session_name: 需要生成路径的会话名称。
    :type session_name: str
    :return: 会话 JSON 文件的完整路径。
    :rtype: str
    """
    return f"{SESSIONS_DIR}/{session_name}.json"

@app.exception_handler(Exception)
def handle_exception(request: Request, exc: Exception):
    """
    处理 FastAPI 应用中的未捕获异常。

    记录异常信息，包括请求路径和异常详情，并返回统一的服务器内部错误响应。

    :param request: 触发异常的 HTTP 请求对象，包含请求的详细信息如 URL 等。
    :param exc: 被捕获的异常对象，包含异常的具体信息。
    :return: 包含状态码和错误信息的 JSON 响应，状态码为 500，错误信息为 "服务器内部错误"。
    """
    logging.error(f"处理异常, 请求路径: {request.url}, 异常信息: {exc}")
    return JSONResponse(content={"code": 500, "message": "服务器内部错误"})



# 初始化OpenAI客户端
client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),base_url="https://api.deepseek.com")

if not os.path.exists(SESSIONS_DIR):
    os.mkdir(SESSIONS_DIR)

@app.get("/", summary="根路径")
async def read_root():
    """
    根路径的异步处理器，返回包含问候消息的 JSON 对象。

    :return: 包含 ``"message"`` 键且值为 ``"Hello World"`` 的字典。
    :rtype: dict
    """
    return {"message": "Hello World"}

# 配置日志
logging.basicConfig(
     level=logging.INFO,
     format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)



@app.get('/api/presets', summary='伴侣预设信息预览')
async def load_presets(db_session:AsyncSession = Depends(get_db_session)) -> ApiResponse:
    """
    从数据库中获取所有 AI 伴侣预设，按排序顺序升序排列。

    该函数查询 AI 预设表，按 sort_order 字段升序获取所有记录，
    将其转换为可 JSON 序列化的格式后关闭数据库会话，
    最终将结果列表封装为统一 API 响应返回。

    :return: 包含 AI 预设信息列表的响应对象。
    """
    logging.info("获取伴侣预设信息列表")

    # 1.执行查询操作->查询ai_preset表中所有数据，根据sort_order排序升序
    result = await db_session.execute(select(AiPreset).order_by(AiPreset.sort_order.asc()))
    # 2.处理查询结果:jsonable_encoder(参数) 帮我们把参数转换为可JSON序列化的格式
    presets_list = jsonable_encoder(result.scalars().all())

    return ApiResponse(data=presets_list)


@app.post("/api/sessions", summary="新建会话")
async def create_session(request: CreateSessionRequest, db_session:AsyncSession = Depends(get_db_session)):
    """
    创建新的聊天会话。

    生成唯一的会话名称，并将初始会话数据保存为 JSON 文件到 sessions 目录。

    :param request: 包含伴侣昵称和性格描述的请求体。
    :return: 包含生成会话名称的 ApiResponse 对象。
    :rtype: ApiResponse
    :raises OSError: 会话文件无法创建或写入时抛出。
    """
    logging.info(f"新建会话: {request.nick_name}, {request.nature}")
    # 1.准备会话名称
    session_name = generate_session_name()

    # 2.将会话名称保存成SQL数据库
    now = datetime.now()
    await db_session.execute(insert(AiSession),
                             {"session_name": session_name, "nick_name": request.nick_name,
                              "nature": request.nature, "create_time": now, "update_time": now})
    await db_session.commit()

    # 3返回响应，数据为会话名称
    return ApiResponse(data=session_name)



@app.post('/api/chat', summary="AI伴侣聊天")
async def chat(request: ChatRequest) -> ApiResponse:
    """
    处理 AI 伴侣聊天请求。

    根据会话名称从 JSON 文件中加载会话数据。若会话不存在，
    返回状态码为 404 的响应；否则使用用户昵称和性格拼接系统提示词，
    追加历史消息与新的用户消息后调用 Deepseek API，
    将 AI 回复更新回会话并保存至文件，
    最后以统一响应格式返回 AI 回复。

    :param request: 包含会话名称、用户消息、昵称和性格的聊天请求。
    :return: 成功时包含 AI 回复的响应对象；会话文件不存在时返回状态码 404 的响应。
    """
    logging.info(f"与AI交互:{request.session_name} : {request.message}")
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
    logging.info(f"AI回复:{ai_response}")

    # 6. 更新消息列表中的消息
    messages.pop(0)
    messages.append({"role": "assistant", "content": ai_response})
    session_data["messages"] = messages
    logging.info(f"会话数据:{session_data}")

    # 7. 保存会话信息到json文件中
    with open(session_path, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=4)

    # 8.返回响应，数据为AI的回复内容
    return ApiResponse(data=ai_response)


@app.get("/api/sessions", summary="获取所有会话列表，按时间顺序降序排列（最新的会话排在最前）")
async def sessions(db_session:AsyncSession = Depends(get_db_session)):
    """
    获取所有会话列表，按时间顺序降序排列（最新的会话排在最前）。

    该函数遍历存储会话的目录，收集所有以 ``.json`` 结尾的文件名，去除扩展名后得到会话名称，
    并按降序排序，最后返回包含该列表的 ``ApiResponse`` 对象。

    :return: 包含会话名称列表的 ``ApiResponse`` 对象，列表按时间顺序降序排列。
    :rtype: ApiResponse
    """
    logging.info("获取所有会话列表")

    # 执行SQL得到结果
    result = await db_session.execute(select(AiSession.session_name).order_by(AiSession.session_name.desc()))
    one = result.scalars().all()
    # 返回响应结果
    return ApiResponse(data=one)

@app.get("/api/sessions/{session_name}", summary="获取指定会话数据", response_model=ApiResponse)
async def session_find(session_name: str, db_session:AsyncSession = Depends(get_db_session)):
    """
    根据会话名称从数据库中获取会话数据。

    先查询会话是否存在。若存在，返回会话基本信息及该会话下的
    全部聊天消息（按创建时间升序）；若不存在，
    返回状态码为 404 和错误信息的响应。

    :param session_name: 需要获取的会话名称。
    :return: 成功时包含会话数据（含消息列表）的 ApiResponse；会话不存在时返回状态码 404 的错误响应。
    """
    logging.info(f"获取指定会话数据: {session_name}")
    # 1.执行查询操作->查询ai_session表中session_name列等于session_name的记录
    result = await db_session.execute(select(AiSession).where(AiSession.session_name == session_name))
    session_data = result.scalars().first()
    # 2.验证会话数据是否存在
    if session_data is None:
        return ApiResponse(code=404, message="会话不存在")
    # 3.查询该会话下的所有聊天消息，按创建时间升序
    messages_result = await db_session.execute(
        select(AiMessage).where(AiMessage.session_id == session_data.id).order_by(AiMessage.create_time.asc())
    )
    messages_list = messages_result.scalars().all()
    # 4.封装会话数据（jsonable_encoder 将 ORM 对象转为可 JSON 序列化的字典，datetime 字段一并处理）
    session_data = jsonable_encoder(session_data)
    session_data["messages"] = jsonable_encoder(messages_list)
    # 5.返回响应，数据为会话数据（含消息列表）
    return ApiResponse(data=session_data)


@app.delete("/api/sessions/{session_name}", summary="删除指定会话", response_model=ApiResponse)
async def session_delete(session_name: str, db_session:AsyncSession = Depends(get_db_session)):
    """
    根据会话名称删除已存在的会话。

    先检查会话文件是否存在，若存在则删除并返回成功响应；
    若会话不存在，返回 404 响应。

    :param session_name: 需要删除的会话名称。
    :return: 表示删除结果的 ApiResponse 对象。
    """
    logging.info(f"删除指定会话: {session_name}")
    # 1.先获取会话ID
    result = await db_session.execute(select(AiSession).where(AiSession.session_name == session_name))
    session_data = result.scalars().first()

    # 2.先删除会话信息
    await db_session.execute(delete(AiMessage).where(AiMessage.session_id == session_data.id))

    # 3.再删除会话数据
    await db_session.execute(delete(AiSession).where(AiSession.id == session_data.id))

    # 4.返回响应，提示会话删除成功
    await db_session.commit()
    return ApiResponse(message="会话删除成功")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)

