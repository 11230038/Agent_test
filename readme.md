# 🤖 扫地机器人智能客服 Agent

基于 LangChain + Chroma + FastAPI + Vue 3 的扫地机器人智能客服系统。支持多轮对话、RAG 知识库检索、用户画像管理，并提供了管理后台用于维护知识库文档。

---

## 功能特性

### 客服对话

- **智能问答** — 基于 RAG 知识库 + LLM，回答产品功能、故障排除、选购建议等问题
- **纯聊天** — 无工具无知识库的闲聊模式
- **知识库检索** — 直接搜索知识库，查看匹配的文档片段及相关性分值
- **流式输出** — 对话采用 SSE 流式传输，逐字渲染
- **多轮对话** — 自动携带历史消息，上下文感知

### 管理后台

- 🔐 密码验证保护
- 📊 知识库结构树（分类 → 文件 → Chunk）
- 📤 上传 PDF/TXT 文档并自动索引
- 🗑️ 删除文档（磁盘 + 向量库同步清理）
- 📁 更改文档分类
- 🔍 按内容关键词检索 Chunk
- ✏️ 单独编辑任意 Chunk 内容

### 用户系统

- 对话持久化（按会话存储）
- 用户画像（城市/性别/年龄/偏好）
- 反馈收集（点赞/踩 + 备注统计）
- 自动画像提取（从对话中识别偏好和人口统计信息）

---

## 项目结构

```
Agent/
├── readme.md                     # 本文件
├── end/                          # 后端（Python FastAPI）
│   ├── main.py                   # 启动入口（uvicorn）
│   ├── api.py                    # API 路由（15 个端点）
│   ├── app.py                    # Streamlit 备选 UI
│   ├── test.py                   # CLI 测试工具
│   ├── agent/                    # Agent 层（ReAct + 9 工具 + 3 中间件）
│   ├── rag/                      # RAG 层（Chroma 向量库 + 检索 + 缓存）
│   ├── model/                    # 模型工厂（通义千问 + DashScope Embedding）
│   ├── utils/                    # 工具层（配置 / 文件 / 日志 / 会话）
│   ├── config/                   # YAML 配置文件
│   ├── prompts/                  # Prompt 模板
│   ├── data/                     # 知识库源文件 + 会话数据库
│   ├── logs/                     # 日志（按日切割）
│   ├── 接口文档.md               # 后端 API 完整文档
│   └── 项目结构.md               # 后端模块详细说明
├── front/                        # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── views/ChatView.vue    # 聊天页
│   │   ├── views/AdminView.vue   # 管理页
│   │   ├── router/index.js       # 路由
│   │   └── App.vue               # 顶层 Shell
│   ├── 接口文档.md               # 前端接口消费文档
│   └── 项目结构.md               # 前端架构说明
└── config/                       # 共享配置
```

---

## 快速开始

### 环境要求

- **Python** 3.10+
- **Node.js** 20.19+ / 22.12+
- **依赖包**：参见 `end/` 和 `front/package.json`

### 1. 安装依赖

```bash
# 后端（进入 end 目录）
cd end
pip install fastapi uvicorn langchain langchain-chroma langchain-community langchain-text-splitters dashscope pyyaml streamlit

# 前端
cd front
npm install
```

### 2. 配置 API Key

编辑 `end/config/api.yml`（或 `end/config/agent.yml`），填入 DashScope API Key。

### 3. 加载知识库

```bash
cd end
python -c "from rag.vector_store import VectorStoreService; VectorStoreService().load_document()"
```

`data/` 目录下的 PDF/TXT 文件会按子目录分类自动索引。

### 4. 启动服务

```bash
# 终端 1 — 后端（端口 8000）
cd end
python main.py

# 终端 2 — 前端（端口 5173 自动代理 API）
cd front
npm run dev
```

访问：`http://localhost:5173`

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue 3 前端                        │
│  ┌──────────────┐  ┌──────────────┐                │
│  │  ChatView    │  │  AdminView   │                │
│  └──────┬───────┘  └──────┬───────┘                │
│         │                 │                         │
│  ┌──────┴─────────────────┴───────┐                │
│  │        Vue Router              │                │
│  └────────────────────────────────┘                │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP / SSE (Vite Proxy)
┌─────────────────────┴───────────────────────────────┐
│                 FastAPI 后端                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  15 API  │  │  Session │  │  Admin   │          │
│  │  Routes  │  │  Store   │  │  APIs    │          │
│  └────┬─────┘  └──────────┘  └──────────┘          │
│       │                                              │
│  ┌────┴─────────────────────────────────┐          │
│  │           ReactAgent                 │          │
│  │  ┌─────────┐ 9 Tools ┌────────────┐ │          │
│  │  │  Chat   │─────────│  RAG Tool  │ │          │
│  │  │  Agent  │         │  Weather...│ │          │
│  │  └─────────┘         └────────────┘ │          │
│  └─────────────────────────────────────┘          │
│       │                         │                   │
│  ┌────┴──────┐          ┌──────┴──────┐           │
│  │ DashScope │          │RagSummarize │           │
│  │  (LLM)    │          │  Service    │           │
│  └───────────┘          └──────┬──────┘           │
│                                │                    │
│                          ┌─────┴─────┐            │
│                          │  Chroma   │            │
│                          │ Vector DB │            │
│                          └───────────┘            │
└─────────────────────────────────────────────────────┘
```

---

## API 概览

| 分组 | 端点 | 方法 | 说明 |
|---|---|---|---|
| 系统 | `/health` | GET | 存活检查 |
| 系统 | `/ready` | GET | 依赖就绪检查 |
| 对话 | `/api/chat` | POST | 非流式对话 |
| 对话 | `/api/chat/stream` | POST | SSE 流式对话 |
| 知识库 | `/api/rag/search` | POST | 关键词检索 |
| 知识库 | `/api/rag/status` | GET | 知识库状态 |
| 会话 | `/api/sessions` | GET | 列出会话 |
| 会话 | `/api/session/{id}` | GET / DELETE | 获取/删除会话 |
| 画像 | `/api/profile` | POST | 保存画像 |
| 画像 | `/api/profile/{id}` | GET | 获取画像 |
| 反馈 | `/api/feedback` | POST | 提交反馈 |
| 反馈 | `/api/feedback/stats` | GET | 反馈统计 |
| 管理 | `/api/admin/knowledge` | POST | 🔐 知识库结构 |
| 管理 | `/api/admin/upload` | POST | 🔐 上传文档 |
| 管理 | `/api/admin/delete` | POST | 🔐 删除文档 |
| 管理 | `/api/admin/category` | POST | 🔐 改分类 |
| 管理 | `/api/admin/chunk/update` | POST | 🔐 编辑 Chunk |

> 详细文档见：[end/接口文档.md](end/接口文档.md) / [front/接口文档.md](front/接口文档.md)

---

## 知识库配置

编辑 `end/config/chroma.yml`：

```yaml
collection_name: agent
persist_directory: rag/chroma_db
k: 3
data_path: data
allow_knowledge_file_type: [".pdf", ".txt"]

# 默认分块
chunk_size: 200
chunk_overlap: 20

# 按分类差异化分块
chunk_strategies:
  产品FAQ:
    chunk_size: 300
  故障排除:
    chunk_size: 400
```

知识库文件按子目录自动分类，例如 `data/产品FAQ/xxx.pdf` 会自动归类为"产品FAQ"。

---

## 相关文档

| 文档 | 内容 |
|---|---|
| [end/接口文档.md](end/接口文档.md) | 后端全部 17 个 API 的请求/响应示例 |
| [end/项目结构.md](end/项目结构.md) | 后端模块详解 |
| [front/接口文档.md](front/接口文档.md) | 前端如何调用后端接口 |
| [front/项目结构.md](front/项目结构.md) | 前端架构说明 |
| [end/CLAUDE.md](end/CLAUDE.md) | AI 助手的项目指南 |
