from datetime import datetime
from sqlalchemy import Integer, String, DateTime, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from typing import Any
import os
import json
from openai import OpenAI
from pydantic import BaseModel
import logging

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
    Generic API response model.

    This class provides a standardized structure for API responses. It includes
    a status code, a message, and an optional data payload. The model inherits
    from Pydantic's BaseModel, enabling validation and serialization of the
    response data.

    :ivar code: Status code indicating the result of the operation.
    :ivar message: Human-readable message describing the operation result.
    :ivar data: Data payload returned by the API, which can be of any type.
    """
    code: int = 200
    message: str = "操作成功"
    data: Any = None

class CreateSessionRequest(BaseModel):
    """
    Represents a request payload for creating a session.

    This Pydantic model validates and structures the input data required to
    create a new session. It inherits from ``pydantic.BaseModel``, ensuring
    that the fields are parsed and validated according to their type hints.

    :ivar nick_name: The nickname to associate with the created session.
    :ivar nature: The nature or category of the session.
    """
    nick_name : str
    nature : str

class ChatRequest(BaseModel):
    """
    Summary of the ChatRequest model.

    ChatRequest is a Pydantic model representing a chat request payload,
    containing session-related information, the message content, a user's
    nickname, and an additional nature or context descriptor.

    :ivar session_name: Name or identifier of the chat session.
    :ivar message: The text message sent in the chat request.
    :ivar nick_name: Nickname of the user sending the request.
    :ivar nature: Additional nature or category associated with the request.
    """
    session_name: str
    message: str
    nick_name: str
    nature: str

# --------功能函数--------
def generate_session_name():
    """
    Generate a session name based on the current date and time.

    The session name is created by formatting the current local date and
    time as ``YYYY-MM-DD_HH-MM-SS``.

    :return: The generated session name as a string in the format
        ``YYYY-MM-DD_HH-MM-SS``.
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 保存为函数f"sessions/{session_name}.json"
def get_session_path(session_name):
    """
    Constructs a file path for a session's JSON file.

    The path is built by joining the global ``SESSIONS_DIR`` directory with
    the provided session name and appending the ``.json`` file extension.

    :param session_name: The name of the session for which to generate the path.
    :type session_name: str
    :return: The full file path to the session's JSON file.
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


# --------数据库相关--------
# 1. 创建引擎(支持异步操作)
engine = create_async_engine("mysql+aiomysql://root:1234@localhost:3306/ai_partner_db", echo=True)

# 2. 声明模型类
class Base(DeclarativeBase):
    """
    Base class for declarative models.

    This class inherits from DeclarativeBase and serves as the base class
    for all ORM models. Subclass this class to define mapped classes that
    represent database tables.
    """
    pass

class AiPreset(Base):
    """
    Represents an AI preset configuration stored in the database.

    The AiPreset class is a SQLAlchemy model that maps to the ``ai_preset`` table.
    It holds information about presets used to define AI companion behavior, such as
    names, personality descriptions, and ordering.

    :ivar id: Unique identifier for the preset.
    :ivar name: Name of the preset.
    :ivar nick_name: Nickname assigned to the companion.
    :ivar nature: Description of the companion's personality.
    :ivar sort_order: Position used for ordering presets.
    :ivar create_time: Timestamp indicating when the preset was created.
    """
    __tablename__ = "ai_preset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="预设名称")
    nick_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="伴侣昵称")
    nature: Mapped[str] = mapped_column(String(500), nullable=False, comment="伴侣性格描述")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, comment="排序顺序")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"AiPreset(id={self.id}, name={self.name}, nick_name={self.nick_name}, nature={self.nature}, sort_order={self.sort_order}, create_time={self.create_time})"


class AiSession(Base):
    """
    SQLAlchemy model representing an AI session.

    Represents a record in the ``ai_session`` table, storing configuration and
    metadata for an AI conversational session, including its unique name, the
    partner's nickname and personality description, and timestamps for creation
    and last update.

    :ivar id: Primary key, auto-incrementing integer.
    :type id: int
    :ivar session_name: Unique name of the session.
    :type session_name: str
    :ivar nick_name: Nickname of the AI partner.
    :type nick_name: str
    :ivar nature: Personality description of the AI partner.
    :type nature: str
    :ivar create_time: Timestamp when the record was created.
    :type create_time: datetime
    :ivar update_time: Timestamp when the record was last updated.
    :type update_time: datetime
    """
    __tablename__ = "ai_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    session_name: Mapped[str]= mapped_column(String(50), unique=True, nullable=False, comment="会话名称")
    nick_name: Mapped[str] = mapped_column(String(50), nullable=False, default="小甜甜", comment="伴侣昵称")
    nature: Mapped[str] = mapped_column(String(500), nullable=False, default="活泼开朗的东北姑娘", comment="伴侣性格")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"AiSession(id={self.id}, session_id={self.session_name}, nick_name={self.nick_name}, nature={self.nature}, create_time={self.create_time}, update_time={self.update_time})"


class AiMessage(Base):
    """
    SQLAlchemy model representing an AI chat message.

    Maps to the ``ai_message`` table and stores individual messages exchanged
    between users and the AI assistant within a chat session.

    :ivar id: Primary key.
    :type id: int
    :ivar session_id: Identifier of the chat session to which the message belongs.
    :type session_id: int
    :ivar role: Role of the message sender, either ``user`` or ``assistant``.
    :type role: str
    :ivar content: Text content of the message.
    :type content: str
    :ivar create_time: Timestamp when the message was created.
    :type create_time: datetime
    """
    __tablename__ = "ai_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    session_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="会话ID")
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="消息角色：user-用户，assistant-AI")
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="消息内容")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"AiMessage(id={self.id}, session_id={self.session_id}, role={self.role}, content={self.content}, create_time={self.create_time})"

# 3. 会话工厂(支持异步操作)
session_factory = async_sessionmaker(engine)


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
async def load_presets() -> ApiResponse:
    """
    Retrieve all AI presets from the database, ordered by sort order in ascending order.

    This function queries the AI preset table, retrieves all records ordered by
    the sort_order field, converts them to a JSON-compatible format, and closes
    the database session. The resulting list is then wrapped in an API response.

    :return: Response containing the list of AI preset information.
    """
    logging.info("获取伴侣预设信息列表")
    # 获取session（使用async with自动释放资源）
    session = session_factory()

    # 执行查询操作->查询ai_preset表中所有数据，根据sort_order排序升序
    result = await session.execute(select(AiPreset).order_by(AiPreset.sort_order.asc()))
    presets_list = jsonable_encoder(result.scalars().all())

    # 释放资源
    await session.close()
    return ApiResponse(data=presets_list)


@app.post("/api/sessions", summary="新建会话")
async def create_session(request: CreateSessionRequest):
    """
    Create a new chat session.

    Generates a unique session name and saves an initial session JSON file to the sessions
    directory.

    :param request: The request body containing the nick name and nature for the session.
    :return: An ApiResponse containing the generated session name.
    :rtype: ApiResponse
    :raises OSError: If the session file cannot be created or written.
    """
    logging.info(f"新建会话: {request.nick_name}, {request.nature}")
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



@app.post('/api/chat', summary="AI伴侣聊天")
async def chat(request: ChatRequest) -> ApiResponse:
    """
    Handle AI companion chat requests.

    Loads session data from a JSON file for the given session name. If the session
    does not exist, returns a response with code 404. Otherwise, constructs a
    system prompt using the user's nick name and nature, appends the chat history
    and the new user message, sends them to the Deepseek API, updates the session
    with the assistant's reply, saves it back to the file, and returns the AI
    response in a standard API response object.

    :param request: The chat request containing the session name, user message,
        nick name, and nature.
    :return: A response object containing the AI's reply on success, or a response
        with code 404 if the session file does not exist.
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
async def sessions():
    """
    获取所有会话列表，按时间顺序降序排列（最新的会话排在最前）。

    该函数遍历存储会话的目录，收集所有以 ``.json`` 结尾的文件名，去除扩展名后得到会话名称，
    并按降序排序，最后返回包含该列表的 ``ApiResponse`` 对象。

    :return: 包含会话名称列表的 ``ApiResponse`` 对象，列表按时间顺序降序排列。
    :rtype: ApiResponse
    """
    logging.info("获取所有会话列表")
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
    """
    Retrieves session data for a given session name from the filesystem.

    Checks whether the session file exists. If it does, reads the file as JSON
    and returns a successful ApiResponse with the session data as payload. If the
    file does not exist, returns an ApiResponse with a 404 status code and an
    error message.

    :param session_name: Name of the session to retrieve.
    :return: ApiResponse containing the session data on success, or an error
        response with status code 404 if the session file is missing.
    """
    logging.info(f"获取指定会话数据: {session_name}")
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
    """
    Delete an existing session by its name.

    Checks whether the session file exists, removes it, and returns a success
    response. If the session does not exist, a 404 response is returned.

    :param session_name: Name of the session to delete.
    :return: ApiResponse indicating deletion result.
    """
    logging.info(f"删除指定会话: {session_name}")
    # 1.先获取会话路径
    session_path = get_session_path(session_name)
    # 2.验证会话文件是否存在
    if not os.path.exists(session_path):
        return ApiResponse(code=404, message="会话不存在")
    # 3.删除会话文件
    os.remove(session_path)
    logging.info(f"会话文件已删除: {session_path}")
    # 4.返回响应，提示会话删除成功
    return ApiResponse(message="会话删除成功")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)