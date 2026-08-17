from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

# 创建引擎(支持异步操作)
engine = create_async_engine("mysql+aiomysql://root:123456@localhost:3306/ai_partner_db?charset=utf8mb4", echo=False)
# 会话工厂(支持异步操作)
session_factory = async_sessionmaker(engine)
# 管理会话
async def get_db_session():
    db_session = session_factory()
    try:
        yield db_session  # 暂停函数,返回session
    except:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()