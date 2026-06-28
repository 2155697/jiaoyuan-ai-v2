# 教员AI顾问 v3.0

> **不是RAG问答，不是风格模仿，而是"教员在你身边帮你分析问题"**

五层认知架构深度复刻教员思维：感知 → 理解 → 推理 → 记忆 → 表达

---

## 核心技术升级

| 维度 | v2.0 (旧版) | v3.0 (新版) |
|------|------------|------------|
| 交互模式 | 直接给答案 | **苏格拉底式提问引导思考** |
| 知识类型 | 30篇人工摘要 | **认知图谱 + 向量检索双引擎** |
| 对话能力 | 无状态单轮 | **五层认知 + 记忆 + 用户画像** |
| 语言风格 | LLM默认 | **教员语言DNA + 情绪调节** |
| 分析深度 | 硬编码Prompt | **思维链推理 + 矛盾分析 + 阶段判断** |
| 模型 | Qwen2.5:7b | **Qwen3:8b (Thinking模式)** |
| 代码量 | ~200行 | **9000+行，模块化架构** |

---

## 五层认知架构

```
用户输入
   │
   ├── 感知层 (Perception)
   │      语义解析 + 情感探测 + 意图分类
   │
   ├── 理解层 (Understanding)
   │      问题类型判断 + 认知图谱检索 + 框架匹配
   │
   ├── 推理层 (Reasoning) ← 核心
   │      思维链引擎 + 苏格拉底提问 + 矛盾分析 + 阶段判断
   │
   ├── 记忆层 (Memory)
   │      对话历史 + 用户画像 + 认知状态追踪
   │
   └── 表达层 (Expression)
          教员语言DNA + 语气调节 + 格式控制
```

---

## 快速开始

### 要求
- macOS (Apple Silicon M2/M3/M4, 16GB+)
- Python 3.10+
- Ollama
- Node.js 18+ (前端开发)

### 一键部署
```bash
./setup.sh
```

### 启动
```bash
# 方式1: 一键启动
./start.sh

# 方式2: 分别启动
ollama serve                               # 终端1: LLM服务
source .venv/bin/activate && python src/api/start_server.py  # 终端2: API服务
cd frontend && npm run dev                 # 终端3: 前端开发
```

### 访问
- **前端界面**: http://localhost:5173
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/health

---

## 项目结构

```
jiaoyuan-v3/
├── src/
│   ├── core/                    # 五层认知引擎
│   │   ├── engine.py            # 主引擎编排
│   │   ├── perception.py        # 感知层
│   │   ├── understanding.py     # 理解层
│   │   ├── reasoning.py         # 推理层（核心）
│   │   ├── memory.py            # 记忆层
│   │   ├── expression.py        # 表达层
│   │   ├── llm_client.py        # Ollama客户端
│   │   ├── cognitive_graph.py   # 认知图谱
│   │   ├── maoxuan_retriever.py # 毛选检索
│   │   └── models.py            # 数据模型
│   └── api/                     # FastAPI后端
│       ├── main.py              # 主应用
│       ├── routes.py            # 路由
│       ├── websocket_manager.py # WebSocket管理
│       ├── models.py            # API模型
│       ├── dependencies.py      # 依赖注入
│       └── start_server.py      # 启动脚本
├── frontend/                    # React前端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── InputArea.tsx
│   │   │   └── Sidebar.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   ├── package.json
│   └── vite.config.ts
├── setup.sh                     # 一键部署
├── start.sh                     # 启动脚本
└── requirements.txt
```

---

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 普通对话 |
| WebSocket | `/api/chat/ws` | 流式实时对话 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/sessions/{id}` | 会话历史 |
| DELETE | `/api/sessions/{id}` | 重置会话 |
| GET | `/api/stats` | 系统统计 |

---

## 核心能力

### 苏格拉底式提问
不直接给答案，通过层层递进的提问引导用户自己思考：
- **澄清概念**: "你说的'资源'，具体指什么？"
- **挑战假设**: "你为什么认为这个方向不行？"
- **探索后果**: "如果按这个方案走，最坏会怎样？"
- **寻找证据**: "你的判断依据是什么？做过哪些调研？"
- **转换视角**: "如果换个位置看，会有什么不同？"

### 矛盾分析
- 识别主要矛盾（当前最紧迫的）
- 识别次要矛盾（暂时搁置但要关注）
- 分析矛盾的两个方面（利弊两面）

### 阶段判断
评估用户所处阶段：
- **战略防御**: 生存第一，保存实力
- **战略相持**: 积蓄力量，等待时机
- **战略反攻**: 主动出击，扩大战果

### 五层分析框架
目标 → 方案 → 环节 → 需求 → 因素 → 评估（含难度评分1-10）

---

## 模型配置

默认使用 Qwen3:8b，可通过环境变量修改：

```bash
export MODEL_NAME="qwen3:8b"        # 模型名称
export OLLAMA_HOST="localhost"       # Ollama主机
export LOG_LEVEL="INFO"              # 日志级别
```

### 推荐模型选择

| 你的Mac | 推荐模型 | 命令 |
|---------|---------|------|
| 16GB (M2/M3) | Qwen3:8b | `ollama pull qwen3:8b` |
| 24GB (M3) | Qwen3:14b | `ollama pull qwen3:14b` |
| 32GB+ (M4 Pro) | Qwen3:30b-a3b | `ollama pull qwen3:30b-a3b` |

---

## 技术栈

- **模型**: Qwen3:8b (Ollama本地运行)
- **后端**: FastAPI + WebSocket + uvicorn
- **前端**: React 18 + TypeScript + Vite + Tailwind CSS
- **向量检索**: ChromaDB + Sentence-Transformers
- **认知图谱**: NetworkX (内存图)
- **数据模型**: Pydantic

---

## License

MIT License

---

> "没有调查就没有发言权。" — 用教员的思维方式，帮你分析问题、找到出路。
