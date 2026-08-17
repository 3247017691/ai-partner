import logging
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import ApiResponse
from app.db import get_db_session, AiPreset


router = APIRouter(prefix='/api', tags=['预设信息'])

@router.get("/presets", summary='加载预设信息列表', response_model=ApiResponse)
async def presets(db_session: AsyncSession = Depends(get_db_session)) -> ApiResponse:
    logging.info('加载预设信息')
    # 1.利用session对象执行查询: 前边加await
    result = await db_session.execute(select(AiPreset).order_by(AiPreset.sort_order.asc()))
    # 2.处理查询的结果:转换成json
    preset_list = jsonable_encoder(result.scalars().all())
    return ApiResponse(data=preset_list)