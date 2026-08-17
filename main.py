import logging
import os
from datetime import datetime

from fastapi import FastAPI, Depends
from fastapi.encoders import jsonable_encoder
from openai import OpenAI
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from starlette.requests import Request

from ai import SYSTEM_PROMPT_TEMPLATE, client
from app.db import AiPreset, get_db_session, AiSession, AiMessage
from schemas import ApiResponse, CreateSessionRequest, ChatRequest
from utils import generate_session_name

app = FastAPI()


# -----------全局设置-----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
logging.getLogger("sqlalchemy.engine").propagate = False


@app.exception_handler(Exception)
def handle_exception(request: Request, e: Exception):
    logging.error(f"Exception on {request.method} {request.url}: {e}")
    return JSONResponse(content={"code": 500, "message": "系统正在维护,请重试或联系管理员"})




@app.get("/api/presets", summary='加载预设信息列表', response_model=ApiResponse)
async def presets(db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info('加载预设信息')
    # 1.利用session对象执行查询: 前边加await
    result = await db_session.execute(select(AiPreset).order_by(AiPreset.sort_order.asc()))
    # 2.处理查询的结果:转换成json
    preset_list = jsonable_encoder(result.scalars().all())
    return ApiResponse(data=preset_list)


@app.post("/api/sessions", summary='创建会话', response_model=ApiResponse)
async def create_session(request: CreateSessionRequest,
                         db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info(f'创建会话: {request}')
    # 1. 准备会话名称: 年-月-日_时-分-秒
    session_name = generate_session_name()
    # 2. 保存会话数据到ai_session表里
    await db_session.execute(
        insert(AiSession)
        .values(session_name=session_name, nick_name=request.nick_name, nature=request.nature,
                create_time=datetime.now(), update_time=datetime.now()))
    await db_session.commit()
    # 4. 返回响应结果: 要求将会话名称响应给客户端
    return ApiResponse(data=session_name)


@app.post("/api/chat", summary='与AI聊天', response_model=ApiResponse)
async def chat(request: ChatRequest, db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info(f'与AI聊天: {request}')
    # 1. 加载会话基本信息
    result = await db_session.execute(select(AiSession).where(AiSession.session_name == request.session_name))
    ai_session = result.scalars().one()
    # 2. 加载此会话的聊天记录
    result = await db_session.execute(
        select(AiMessage.role, AiMessage.content).where(AiMessage.session_id == ai_session.id).order_by(
            AiMessage.create_time.asc()))
    ai_history_msg_list = result.mappings().all()

    # 2. 拼接提示词
    # 2.1 先拼接系统提示词
    system_prompt = SYSTEM_PROMPT_TEMPLATE % (request.nick_name, request.nature)
    message_list = [{'role': 'system', 'content': system_prompt}]
    # 2.2 再拼接历史聊天记录
    message_list += ai_history_msg_list
    # 2.3 再拼接用户本轮的提问
    message_list.append({'role': 'user', 'content': request.message})

    # 3. 调用DeepSeek,发送提示词得到回答
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=message_list,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}}
    )
    ai_content = response.choices[0].message.content

    # 4. 持久化保存聊天记录到会话文件中
    # 4.1 更新昵称和性格
    ai_session.nick_name = request.nick_name
    ai_session.nature = request.nature
    # 4.2 保存 用户本轮的提问, 及模型本轮的回答
    await db_session.execute(insert(AiMessage), [
        {'session_id': ai_session.id, 'role': 'user', 'content': request.message, 'create_time': datetime.now()},
        {'session_id': ai_session.id, 'role': 'assistant', 'content': ai_content, 'create_time': datetime.now()}
    ])

    await db_session.commit()

    # 5. 返回响应
    return ApiResponse(data=ai_content)


@app.get("/api/sessions", summary='获取所有会话列表', response_model=ApiResponse)
async def list_sessions(db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info("获取所有会话列表")
    result = await db_session.execute(select(AiSession.session_name).order_by(AiSession.session_name.desc()))
    ai_session_name_list = result.scalars().all()

    return ApiResponse(data=ai_session_name_list)


@app.get("/api/sessions/{session_name}", summary='获取指定会话的聊天记录', response_model=ApiResponse)
async def get_session(session_name: str, db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info(f'加载会话信息:{session_name}')

    # 1. 查询会话信息
    result = await db_session.execute(select(AiSession).where(AiSession.session_name == session_name))
    ai_session = result.scalars().one()

    # 2. 查询会话里的消息列表
    result = await db_session.execute(
        select(AiMessage).where(AiMessage.session_id == ai_session.id).order_by(AiMessage.create_time.asc()))
    ai_message_list = result.scalars().all()

    # 3. 组装返回结果
    session_data = {
        'session_name': session_name,
        'nick_name': ai_session.nick_name,
        'nature': ai_session.nature,
        'messages': [{'role': ai_message.role, 'content': ai_message.content} for ai_message in ai_message_list]
    }
    return ApiResponse(data=session_data)


@app.delete("/api/sessions/{session_name}", summary='删除指定会话', response_model=ApiResponse)
async def delete_session(session_name: str, db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info(f'删除会话:{session_name}')
    # 1. 根据会话名称查询会话, 可以得到会话的id
    result = await db_session.execute(select(AiSession).where(AiSession.session_name == session_name))
    ai_session = result.scalars().one()
    # 2. 删除会话
    await db_session.execute(delete(AiSession).where(AiSession.id == ai_session.id))
    # 3. 根据会话id 删除会话里的聊天记录
    await db_session.execute(delete(AiMessage).where(AiMessage.session_id == ai_session.id))

    await db_session.commit()

    return ApiResponse(message='会话删除成功')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000, reload=False, access_log=False)
