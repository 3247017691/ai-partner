import logging
from datetime import datetime

from fastapi import Depends, APIRouter
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import SYSTEM_PROMPT_TEMPLATE, client
from app.db import get_db_session, AiSession, AiMessage
from app.schemas import ApiResponse, ChatRequest

router = APIRouter(prefix='/api', tags=['AI聊天'])

@router.post("/chat", summary='与AI聊天', response_model=ApiResponse)
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