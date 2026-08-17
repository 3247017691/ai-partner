import logging
from datetime import datetime

from fastapi import Depends, APIRouter
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session, AiSession, AiMessage
from app.schemas import ApiResponse, CreateSessionRequest
from app.utils import generate_session_name

router = APIRouter(prefix='/api', tags=['会话管理'])

@router.post("/sessions", summary='创建会话', response_model=ApiResponse)
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


@router.get("/sessions", summary='获取所有会话列表', response_model=ApiResponse)
async def list_sessions(db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info("获取所有会话列表")
    result = await db_session.execute(select(AiSession.session_name).order_by(AiSession.session_name.desc()))
    ai_session_name_list = result.scalars().all()

    return ApiResponse(data=ai_session_name_list)


@router.get("/sessions/{session_name}", summary='获取指定会话的聊天记录', response_model=ApiResponse)
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


@router.delete("/sessions/{session_name}", summary='删除指定会话', response_model=ApiResponse)
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