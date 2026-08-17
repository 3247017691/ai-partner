# AI 伴侣（ai-partner）

一个基于 **FastAPI + DeepSeek 大模型** 的 AI 伴侣聊天服务后端。你可以为会话指定一个「伴侣」（昵称 + 性格），AI 会完全代入伴侣角色，像微信聊天一样与你对话，支持多会话管理、历史消息持久化与预设角色列表。

## 功能特性

- 💬 **伴侣角色扮演**：通过系统提示词让 AI 完全代入指定性格的伴侣角色，回复简短自然、可带 emoji，像微信聊天
- 👥 **伴侣预设**：内置预设信息列表接口（`ai_preset` 表），可按排序展示可选角色
- 📝 **多会话管理**：支持创建、查询、删除多个会话，会话以创建时间命名
- 🧠 **上下文记忆**：每次对话自动携带该会话的历史记录，AI 不会“失忆”
- 🗄️ **数据库持久化**：会话与聊天记录存储在 MySQL 中（SQLAlchemy 2.0 异步驱动），服务重启不丢失
- 🌐 **标准 REST API**：统一 `{code, message, data}` 响应格式，易于前端对接

## 技术栈

| 组件 | 说明 |
| --- | --- |
| 语言 | Python ≥ 3.14 |
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | MySQL（异步驱动 `aiomysql`） |
| ORM | SQLAlchemy 2.0（async） |
| LLM | DeepSeek API（`deepseek-v4-flash`，兼容 OpenAI SDK） |
| 数据校验 | Pydantic v2 |
| 包管理 | uv（`uv.lock`） |

## 目录结构

```
ai-partner/
├── main.py                 # FastAPI 入口：路由、聊天业务逻辑
├── pyproject.toml          # 项目配置与依赖声明（uv）
├── uv.lock                 # 依赖锁文件
├── test_main.http          # HTTP 接口测试文件（IDEA 可直接运行）
└── app/
    ├── ai/                 # AI 配置层
    │   ├── config.py       # DeepSeek 客户端与系统提示词模板
    │   └── __init__.py
    ├── db/                 # 数据库层
    │   ├── database.py     # 异步引擎 / 会话工厂（连接串在此配置）
    │   ├── models.py       # ORM 模型：AiPreset / AiSession / AiMessage
    │   └── __init__.py
    ├── schemas/            # 数据模型层
    │   ├── schemas.py      # Pydantic 请求/响应模型
    │   └── __init__.py
    └── utils/              # 工具函数层
        ├── utils.py        # 会话名称生成等通用工具
        └── __init__.py
```

## 快速开始

### 1. 环境要求

- Python ≥ 3.14
- MySQL（建议 8.x，字符集 `utf8mb4`）
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）
- 推荐使用 [uv](https://docs.astral.sh/uv/) 管理依赖

### 2. 准备数据库

```sql
CREATE DATABASE ai_partner_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

建表：

```sql
-- 伴侣预设表
CREATE TABLE ai_preset (
    id          INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    name        VARCHAR(50)  NOT NULL COMMENT '预设名称',
    nick_name   VARCHAR(50)  NOT NULL COMMENT '伴侣昵称',
    nature      VARCHAR(500) NOT NULL COMMENT '伴侣性格描述',
    sort_order  INT          NOT NULL COMMENT '排序顺序',
    create_time DATETIME     NOT NULL COMMENT '创建时间'
) COMMENT '伴侣预设表';

-- 会话表
CREATE TABLE ai_session (
    id           INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    session_name VARCHAR(50)  NOT NULL UNIQUE COMMENT '会话名称',
    nick_name    VARCHAR(50)  NOT NULL DEFAULT '小甜甜' COMMENT '伴侣昵称',
    nature       VARCHAR(500) NOT NULL DEFAULT '活泼开朗的东北姑娘' COMMENT '伴侣性格',
    create_time  DATETIME     NOT NULL COMMENT '创建时间',
    update_time  DATETIME     NOT NULL COMMENT '更新时间'
) COMMENT '会话表';

-- 消息表
CREATE TABLE ai_message (
    id          INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    session_id  INT          NOT NULL COMMENT '会话ID',
    role        VARCHAR(20)  NOT NULL COMMENT '消息角色：user-用户，assistant-AI',
    content     VARCHAR(500) NOT NULL COMMENT '消息内容',
    create_time DATETIME     NOT NULL COMMENT '创建时间'
) COMMENT '消息表';
```

可选：插入预设角色数据，供 `GET /api/presets` 返回：

```sql
INSERT INTO ai_preset (name, nick_name, nature, sort_order, create_time) VALUES
('小甜甜', '小甜甜', '活泼开朗的东北姑娘', 1, NOW()),
('御姐',   '若曦',   '成熟稳重、温柔体贴的御姐', 2, NOW());
```

### 3. 配置数据库连接

数据库连接串位于 `app/db/database.py`，默认配置为：

```
mysql+aiomysql://root:123456@localhost:3306/ai_partner_db?charset=utf8mb4
```

请按实际账号密码修改。

### 4. 安装依赖

```bash
# 方式一：uv（推荐）
uv sync

# 方式二：pip
pip install -e .
```

### 5. 配置环境变量

设置 DeepSeek API Key（服务启动时从环境变量读取）：

```bash
# Windows (PowerShell)
$env:DEEPSEEK_API_KEY = "sk-xxxx"

# Linux / macOS
export DEEPSEEK_API_KEY="sk-xxxx"
```

### 6. 启动服务

```bash
# 方式一：直接运行
python main.py

# 方式二：uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后访问 <http://127.0.0.1:8000/docs> 查看 Swagger 接口文档。

## API 接口

所有接口统一返回格式：

```json
{ "code": 200, "message": "操作成功", "data": null }
```

| 方法 | 路径 | 说明 | 请求参数 |
| --- | --- | --- | --- |
| GET | `/api/presets` | 加载伴侣预设列表 | 无 |
| POST | `/api/sessions` | 创建会话 | `nick_name`、`nature` |
| GET | `/api/sessions` | 获取所有会话名称列表 | 无 |
| GET | `/api/sessions/{session_name}` | 获取指定会话及聊天记录 | 路径参数 |
| DELETE | `/api/sessions/{session_name}` | 删除指定会话及消息 | 路径参数 |
| POST | `/api/chat` | 与 AI 伴侣聊天 | 见下方示例 |

### 聊天请求示例

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "2025-01-01_12-00-00",
    "message": "今天工作好累呀",
    "nick_name": "小甜甜",
    "nature": "活泼开朗的东北姑娘"
  }'
```

响应 `data` 字段即 AI 的回复内容；对话会连同你的提问一起持久化到 `ai_message` 表。

## 系统提示词说明

服务内置了伴侣角色扮演的系统提示词模板（见 `app/ai/config.py` 中 `SYSTEM_PROMPT_TEMPLATE`），核心规则包括：

- 完全代入伴侣角色，每次只回 1 条消息
- 回复简短，像微信聊天一样，可适当使用 emoji
- 匹配用户语言，充分体现伴侣性格，但不要太肉麻
- 禁止任何场景或状态描述性文字

提示词会拼接「系统提示词 → 历史聊天记录 → 用户本轮提问」后调用 DeepSeek 接口（关闭思考模式，`thinking.type = disabled`）。

## License

本项目代码仅用于学习交流。
