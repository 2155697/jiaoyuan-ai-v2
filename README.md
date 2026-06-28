# 教员AI顾问

基于毛选思想的AI决策咨询系统。

## 快速开始

### 前置要求
- macOS 或 Linux
- Python 3.9+
- Ollama (本地AI模型运行环境)

### 安装 Ollama
```bash
brew install --cask ollama
```

### 一键部署
```bash
chmod +x setup.sh
./setup.sh
```

### 启动使用
```bash
./start.sh
```
浏览器自动打开 `http://localhost:7860`

## 项目结构
```
jiaoyuan-ai/
├── data/
│   └── maoxuan_articles.json    # 毛选知识库
├── src/
│   ├── system_prompt.py         # 核心Prompt(可编辑调整风格)
│   ├── extract_pdf.py           # 数据提取
│   ├── build_knowledge.py       # 知识库构建
│   └── chat_app.py              # 主程序
├── knowledge/
│   └── chroma_db/               # 向量数据库
├── setup.sh                     # 一键部署
└── start.sh                     # 启动脚本
```

## 调整教员风格
编辑 `src/system_prompt.py`，改完保存后刷新网页生效。

## 产品定位
基于毛选决策方法论的AI战略顾问，不是"聊天机器人"。
用户付费不是为了"和教员聊天"，而是"让教员帮我分析问题"。
