"""数据库相关模块：引擎、ORM 模型基类、表模型、会话工厂"""
from datetime import datetime

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

# --------数据库相关--------
# 1. 创建引擎(支持异步操作)
engine = create_async_engine("mysql+aiomysql://root:123456@localhost:3306/ai_partner_db", echo=True)


# 2. 声明模型类
class Base(DeclarativeBase):
    """
    声明式模型的基类。

    该类继承自 DeclarativeBase，作为所有 ORM 模型的基类。
    通过继承该类来定义映射到数据库表的模型类。
    """
    pass


class AiPreset(Base):
    """
    表示存储在数据库中的 AI 伴侣预设配置。

    AiPreset 是一个 SQLAlchemy 模型，映射到 ``ai_preset`` 表。
    它保存用于定义 AI 伴侣行为的预设信息，
    例如名称、性格描述和排序顺序。

    :ivar id: 预设的唯一标识。
    :ivar name: 预设名称。
    :ivar nick_name: 分配给伴侣的昵称。
    :ivar nature: 伴侣的性格描述。
    :ivar sort_order: 用于预设排序的顺序值。
    :ivar create_time: 预设创建时间戳。
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
    表示 AI 会话的 SQLAlchemy 模型。

    对应 ``ai_session`` 表中的一条记录，存储 AI 对话会话的配置与元数据，
    包括唯一的会话名称、伴侣的昵称与性格描述，
    以及创建时间和最后更新时间。

    :ivar id: 主键，自增整数。
    :type id: int
    :ivar session_name: 会话的唯一名称。
    :type session_name: str
    :ivar nick_name: AI 伴侣的昵称。
    :type nick_name: str
    :ivar nature: AI 伴侣的性格描述。
    :type nature: str
    :ivar create_time: 记录创建时间戳。
    :type create_time: datetime
    :ivar update_time: 记录最后更新时间戳。
    :type update_time: datetime
    """
    __tablename__ = "ai_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键")
    session_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="会话名称")
    nick_name: Mapped[str] = mapped_column(String(50), nullable=False, default="小甜甜", comment="伴侣昵称")
    nature: Mapped[str] = mapped_column(String(500), nullable=False, default="活泼开朗的东北姑娘", comment="伴侣性格")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"AiSession(id={self.id}, session_id={self.session_name}, nick_name={self.nick_name}, nature={self.nature}, create_time={self.create_time}, update_time={self.update_time})"


class AiMessage(Base):
    """
    表示 AI 聊天消息的 SQLAlchemy 模型。

    映射到 ``ai_message`` 表，存储聊天会话中
    用户与 AI 助手之间交互的单条消息。

    :ivar id: 主键。
    :type id: int
    :ivar session_id: 消息所属聊天会话的标识。
    :type session_id: int
    :ivar role: 消息发送者角色，取值为 ``user`` 或 ``assistant``。
    :type role: str
    :ivar content: 消息的文本内容。
    :type content: str
    :ivar create_time: 消息创建时间戳。
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


async def get_db_session():
    db_session = session_factory()
    try:
        yield db_session
    except:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()