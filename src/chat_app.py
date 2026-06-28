import gradio as gr
import requests
import chromadb
import os
import sys

sys.path.append(os.path.dirname(__file__))
from system_prompt import get_system_prompt

project_dir = os.path.join(os.path.dirname(__file__), "..")
chroma_path = os.path.join(project_dir, "knowledge", "chroma_db")

kr = False
try:
    chroma_client = chromadb.PersistentClient(path=chroma_path)
    collection = chroma_client.get_collection("maoxuan")
    kr = True
    print("OK: knowledge base connected")
except Exception as e:
    print("WARN: " + str(e))
    collection = None

def search(q, n=2):
    if not kr: return [], []
    try:
        r = collection.query(query_texts=[q], n_results=n)
        return r["documents"][0], r["metadatas"][0]
    except: return [], []

def respond(message, history):
    sp = get_system_prompt()
    docs, metas = search(message, 2)
    kt = ""
    if docs:
        parts = []
        for d, m in zip(docs, metas):
            parts.append("[" + m["title"] + "] " + d[:200])
        kt = "\n\nReference:\n" + "\n".join(parts)
    msgs = [{"role": "system", "content": sp}]
    for h in history:
        msgs.append({"role": "user", "content": h[0]})
        msgs.append({"role": "assistant", "content": h[1]})
    user_msg = message
    if kt: user_msg = message + "\n\n" + kt
    msgs.append({"role": "user", "content": user_msg})
    try:
        r = requests.post("http://localhost:11434/api/chat",
            json={"model": "qwen2.5:7b", "messages": msgs, "stream": False},
            timeout=120)
        if r.status_code == 200: return r.json()["message"]["content"]
        return "Error: " + str(r.status_code)
    except requests.exceptions.ConnectionError:
        return "Error: cannot connect to Ollama"
    except Exception as e:
        return "Error: " + str(e)

with gr.Blocks(title="JiaoYuan AI") as demo:
    gr.Markdown("# JiaoYuan AI Advisor")
    gr.Markdown("Analyze problems with strategic thinking")
    chatbot = gr.Chatbot(height=500)
    msg = gr.Textbox(placeholder="Ask your question...")
    btn = gr.Button("Send")
    clear = gr.Button("Clear")

    def on_submit(message, history):
        if not message.strip(): return "", history
        history = history + [[message, None]]
        response = respond(message, history[:-1])
        history[-1][1] = response
        return "", history

    def on_clear(): return None, []

    btn.click(on_submit, [msg, chatbot], [msg, chatbot])
    msg.submit(on_submit, [msg, chatbot], [msg, chatbot])
    clear.click(on_clear, None, [msg, chatbot], queue=False)

if __name__ == "__main__":
    print("=" * 50)
    print("  Starting...")
    print("  Open: http://localhost:7860")
    print("=" * 50)
    demo.launch(server_name="0.0.0.0", server_port=7860)
