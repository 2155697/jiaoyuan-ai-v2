# JiaoYuan AI Advisor

AI strategic consultant based on Mao Zedong's decision-making methodology.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/2155697/jiaoyuan-ai-v2.git
cd jiaoyuan-ai-v2

# 2. Setup (install deps, download model)
chmod +x setup.sh && ./setup.sh

# 3. Build knowledge base
python3 src/build_knowledge.py

# 4. Start
./start.sh
```

Open browser: http://localhost:7861

## Files
- `src/chat_app.py` - Main app (Flask + HTML)
- `src/system_prompt.py` - Core personality prompt
- `src/extract_pdf.py` - Data extraction
- `src/build_knowledge.py` - Knowledge base builder
- `data/maoxuan_articles.json` - Mao's selected works knowledge
- `setup.sh` - One-click setup
- `start.sh` - Start server
