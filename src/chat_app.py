import gradio as gr
import requests
import chromadb
import os
import sys

sys.path.append(os.path.dirname(__file__))
from system_prompt import get_system_prompt

project_dir = os.path.join(os.path.dirname(__file__), '..')
chroma_path = os.path.join(project_dir, 'knowledge', 'chroma_db')

kr = False
try:
    chroma_client = chromadb.PersistentClient(path=chroma_path)
    collection = chroma_client.get_collection("maoxuan")
    kr = True
    print("知识库已连接")
except Exception as e:
    print(f"知识库未连接({e}), 基础模式运行")
    collection = None

def search(q, n=2):
    if not kr:
        return [], []
    try:
        r = collection.query(query_texts=[q], n_results=n)
        return r['documents'][0], r['metadatas'][0]
    except:
        return [], []

def chat(msg, hist):
    sp = get_system_prompt()
    docs, metas = search(msg, n_results=2)
    kt = ""
    if docs:
        kt = "\n\n相关思想参考:\n" + "\n".join([f"【{m['title']}】{d[:200]}..." for d, m in zip(docs, metas)])

    msgs = [{"role": "system", "content": sp}]
    for h, a in hist:
        msgs.append({"role": "user", "content": h})
        msgs.append({"role": "assistant", "content": a})

    user_msg = msg
    if kt:
        user_msg = f"{msg}\n\n{kt}"
    msgs.append({"role": "user", "content": user_msg})

    try:
        r = requests.post(
            'http://localhost:11434/api/chat',
            json={"model": "qwen2.5:7b", "messages": msgs, "stream": False},
            timeout=120
        )
        if r.status_code == 200:
            return r.json()["message"]["content"]
        return f"服务不可用({r.status_code})"
    except requests.exceptions.ConnectionError:
        return "无法连接Ollama。另一个终端执行: ollama serve"
    except Exception as e:
        return f"出错了: {str(e)}"

demo = gr.ChatInterface(
    chat,
    title="教员AI顾问",
    description="用教员的思维方式, 帮你分析问题、找到出路",
    examples=[
        "我想创业但不知道怎么开始",
        "我和合伙人意见不一致",
        "我的项目做了半年还没盈利, 是不是该放弃了",
        "竞争对手比我强很多, 我该怎么办",
        "现在大环境不好, 我该保守还是进攻?"
    ],
    submit_btn="发送",
    retry_btn="重新生成",
    undo_btn="撤回",
    clear_btn="清空对话"
)

if __name__ == "__main__":
    print("=" * 50)
    print("  教员AI顾问 启动中...")
    print(f"  模式: {'知识增强版' if kr else '基础对话版'}")
    print("  浏览器打开: http://localhost:7860")
    print("=" * 50)
    demo.launch(server_name="0.0.0.0", server_port=7860)
