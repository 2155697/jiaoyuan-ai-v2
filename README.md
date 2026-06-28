# 教员AI顾问

> 不是RAG问答，不是风格模仿。一个具备五层认知架构的AI系统，用教员的思维方式帮你分析问题。

---

## 这是什么

一个深度复刻教员（毛泽东）思维方式的AI咨询系统。核心不是检索毛选原文，而是**模拟教员的认知过程**——如何分析问题、如何提问引导、如何判断阶段、如何给出策略。

### 独特价值

**1. 苏格拉底式提问引导（非直接给答案）**

教员不是答题机器。这个系统继承的核心能力：通过层层递进的提问，引导你自己找到问题的答案。

- 澄清概念："你说的'资源'，具体指什么？"
- 挑战假设："你为什么认为这个方向不行？"
- 探索后果："如果按这个方案走，最坏会怎样？"
- 转换视角："如果换个位置看，会有什么不同？"

**2. 五层认知架构（非单层Prompt）**

```
感知层 → 理解层 → 推理层 → 记忆层 → 表达层
```

- **感知层**：语义解析 + 情感探测 + 意图分类（识别你的真实需求和情绪状态）
- **理解层**：问题类型判断 + 认知图谱检索（匹配教员的思维框架）
- **推理层**：思维链 + 矛盾分析 + 阶段判断（核心分析能力）
- **记忆层**：对话历史 + 用户画像 + 认知状态追踪（跨对话连续）
- **表达层**：教员语言DNA + 语气调节（短句、比喻、辩证句式）

**3. 认知图谱（非简单向量检索）**

36个节点构成的教员思维方法知识图谱：
- 方法论节点：矛盾分析法、调查研究、群众路线、集中优势兵力等
- 概念节点：主要矛盾、战略防御/相持/反攻、实事求是等
- 框架节点：五层分析框架、矛盾论框架、持久战框架等
- 案例节点：星星之火、四渡赤水、论持久战等

**4. 目标-路径-可行性评估循环**

系统内置的核心咨询逻辑：
```
目标识别 → 方案设计 → 环节定位 → 需求分析 → 因素评估 → 反馈调整
```

每次对话都在这个循环中推进，帮助你系统化地分析问题。

**5. 真正的流式思考展示**

不再是一个黑盒等10秒出答案。你能实时看到：
- 当前处于哪一步（感知/理解/推理/生成/完成）
- 教员的思考过程（thinking内容分段展示）
- 回复逐字流出（真正的流式输出）

---

## 快速开始

### 要求

- macOS / Linux
- Python 3.10+
- Ollama
- Node.js 18+（仅前端开发需要）

### 一键启动

```bash
# 1. 克隆仓库
git clone https://github.com/2155697/jiaoyuan-ai-v2.git
cd jiaoyuan-ai-v2

# 2. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 启动Ollama（确保Qwen3已下载）
ollama pull qwen3:8b

# 4. 启动后端
source .venv/bin/activate
python src/api/start_server.py

# 5. 启动前端（新终端）
cd frontend
npm install
npm run dev

# 6. 浏览器打开 http://localhost:5173
```

### 更简单的方式：只运行后端，用curl测试

```bash
# 启动后端
source .venv/bin/activate
python src/api/start_server.py

# 测试对话
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"我想创业但不知道做什么，很迷茫"}'
```

---

## 技术架构

### 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| API框架 | FastAPI | WebSocket流式输出 |
| LLM | Qwen3:8b (Ollama本地) | Thinking模式深度推理 |
| 向量检索 | ChromaDB + Sentence-Transformers | 毛选知识库语义检索 |
| 认知图谱 | NetworkX (内存图) | 教员思维方法结构化 |
| 记忆系统 | JSON持久化 | 跨对话用户画像+认知追踪 |

### 前端

| 组件 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| 样式 | Tailwind CSS |
| 通信 | WebSocket原生 |
| 图标 | Lucide React |

---

## 项目结构

```
jiaoyuan-ai-v2/
├── src/
│   ├── core/                    # 五层认知引擎
│   │   ├── engine.py            # 主引擎（5步进度流式）
│   │   ├── perception.py        # 感知层
│   │   ├── understanding.py     # 理解层
│   │   ├── reasoning.py         # 推理层（思维链+苏格拉底+矛盾分析）
│   │   ├── memory.py            # 记忆层
│   │   ├── expression.py        # 表达层（教员语言DNA）
│   │   ├── llm_client.py        # Ollama客户端（流式）
│   │   ├── cognitive_graph.py   # 认知图谱（36节点）
│   │   ├── maoxuan_retriever.py # 毛选向量检索
│   │   └── models.py            # 数据模型
│   └── api/                     # FastAPI后端
│       ├── main.py              # 主应用
│       ├── routes.py            # 路由
│       ├── websocket_manager.py # WebSocket管理
│       └── dependencies.py      # 依赖注入
├── frontend/                    # React前端
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── MessageBubble.tsx    # 消息气泡（含思考进度条）
│       │   ├── ChatContainer.tsx    # 聊天容器
│       │   ├── Header.tsx           # 顶部栏
│       │   ├── InputArea.tsx        # 输入区
│       │   └── Sidebar.tsx          # 侧边栏
│       ├── hooks/
│       │   └── useWebSocket.ts      # WebSocket Hook（流式处理）
│       └── types.ts                 # 类型定义
├── .env                         # 配置（模型名等）
└── requirements.txt
```

---

## 配置

`.env` 文件：

```env
MODEL_NAME=qwen3:8b        # 模型名称
OLLAMA_HOST=localhost      # Ollama主机
API_PORT=8000              # API端口
LOG_LEVEL=INFO             # 日志级别
```

### 推荐模型选择

| 你的Mac | 推荐模型 | 命令 |
|---------|---------|------|
| 16GB (M2/M3) | Qwen3:8b | `ollama pull qwen3:8b` |
| 24GB (M3) | Qwen3:14b | `ollama pull qwen3:14b` |
| 36GB+ (M4 Pro/Max) | Qwen3:30b-a3b | `ollama pull qwen3:30b-a3b` |

---

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 普通对话 |
| WebSocket | `/api/chat/ws` | 流式对话（推荐） |
| GET | `/api/health` | 健康检查 |
| GET | `/api/stats` | 系统统计 |

### WebSocket消息格式

**发送：**
```json
{"message": "你的问题", "session_id": "s1", "user_id": "u1"}
```

**接收（流式）：**
```json
{"type": "progress", "step": 1, "total": 5, "label": "感知分析", "detail": "主题：创业，情绪：迷茫"}
{"type": "progress", "step": 2, "total": 5, "label": "理解问题", "detail": "问题类型：阶段判断"}
{"type": "progress", "step": 3, "total": 5, "label": "深度推理", "detail": "识别3个关键问题"}
{"type": "thinking_chunk", "content": "用户面临的核心矛盾是..."}
{"type": "progress", "step": 4, "total": 5, "label": "生成回复"}
{"type": "content", "content": "先"}
{"type": "content", "content": "不要"}
{"type": "content", "content": "急"}
...
{"type": "done"}
```

---

## 开发说明

### 为什么不用LangChain/LlamaIndex

这个项目刻意保持轻量，不依赖重型框架：
- **LangChain**：过度抽象，调试困难，对本项目的五层架构是束缚而非帮助
- **LlamaIndex**：主要面向文档检索RAG，不适合认知建模
- **自研架构**：五层认知架构是核心创新点，需要完全掌控数据流

### 为什么是本地模型（Ollama）而非API

- **数据隐私**：用户咨询内容不上传云端
- **成本控制**：本地运行零API费用
- **速度可控**：MacBook本地运行延迟<10s
- **离线可用**：不依赖网络连接

### 为什么是Qwen3

- **Thinking模式**：Qwen3支持`<think>`标签内部推理，对模拟教员思维至关重要
- **中文能力**：在中文理解和生成上优于同规模Llama/Mistral
- **本地友好**：8B参数在MacBook上流畅运行

---

## License

MIT License

---

> "没有调查就没有发言权。" —— 用教员的思维方式，帮你分析问题、找到出路。
