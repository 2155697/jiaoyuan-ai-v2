import sys
import os
sys.path.append(os.path.dirname(__file__))
from system_prompt import get_system_prompt

def search_knowledge(q, collection, n=2):
    try:
        r = collection.query(query_texts=[q], n_results=n)
        return r["documents"][0], r["metadatas"][0]
    except:
        return [], []

def get_response(message, history, collection=None):
    import requests
    sp = get_system_prompt()
    kt = ""
    if collection:
        docs, metas = search_knowledge(message, collection, 2)
        if docs:
            parts = []
            for d, m in zip(docs, metas):
                parts.append("[%s] %s" % (m["title"], d[:200]))
            kt = "\n\nReference:\n" + "\n".join(parts)
    msgs = [{"role": "system", "content": sp}]
    for h in history:
        msgs.append({"role": "user", "content": h[0]})
        msgs.append({"role": "assistant", "content": h[1]})
    user_msg = message
    if kt:
        user_msg = message + "\n\n" + kt
    msgs.append({"role": "user", "content": user_msg})
    try:
        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": "qwen2.5:7b", "messages": msgs, "stream": False},
            timeout=120
        )
        if r.status_code == 200:
            return r.json()["message"]["content"]
        return "Error: %s" % r.status_code
    except requests.exceptions.ConnectionError:
        return "Error: cannot connect to Ollama. Run 'ollama serve' in another terminal."
    except Exception as e:
        return "Error: %s" % str(e)

def main():
    import chromadb
    from flask import Flask, request, jsonify, render_template_string
    
    project_dir = os.path.join(os.path.dirname(__file__), "..")
    chroma_path = os.path.join(project_dir, "knowledge", "chroma_db")
    
    kr = False
    collection = None
    try:
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_collection("maoxuan")
        kr = True
        print("OK: knowledge base connected")
    except Exception as e:
        print("WARN: %s" % e)
    
    app = Flask(__name__)
    
    HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>教员AI顾问</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }
        .header h1 { font-size: 24px; }
        .header p { font-size: 14px; opacity: 0.9; margin-top: 5px; }
        .chat { max-width: 800px; margin: 20px auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }
        .messages { height: 500px; overflow-y: auto; padding: 20px; }
        .msg { margin-bottom: 15px; display: flex; }
        .msg.user { justify-content: flex-end; }
        .msg.assistant { justify-content: flex-start; }
        .bubble { max-width: 70%; padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.6; }
        .msg.user .bubble { background: #667eea; color: white; border-bottom-right-radius: 4px; }
        .msg.assistant .bubble { background: #f0f0f0; color: #333; border-bottom-left-radius: 4px; white-space: pre-wrap; }
        .input-area { padding: 15px 20px; border-top: 1px solid #eee; display: flex; gap: 10px; }
        .input-area input { flex: 1; padding: 12px 16px; border: 1px solid #ddd; border-radius: 25px; font-size: 14px; outline: none; }
        .input-area input:focus { border-color: #667eea; }
        .input-area button { padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 14px; }
        .input-area button:hover { opacity: 0.9; }
        .input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
        .status { padding: 5px 20px; font-size: 12px; color: #999; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>教员AI顾问</h1>
        <p>用教员的思维方式，帮你分析问题、找到出路</p>
    </div>
    <div class="chat">
        <div class="messages" id="messages"></div>
        <div class="status" id="status"></div>
        <div class="input-area">
            <input type="text" id="input" placeholder="输入你的问题..." onkeypress="if(event.key==='Enter')send()">
            <button id="sendBtn" onclick="send()">发送</button>
        </div>
    </div>
    <script>
        let history = [];
        const status = document.getElementById("status");
        const messages = document.getElementById("messages");
        const input = document.getElementById("input");
        const sendBtn = document.getElementById("sendBtn");
        
        status.textContent = "{{ mode }}";
        
        function addMsg(role, text) {
            const div = document.createElement("div");
            div.className = "msg " + role;
            const bubble = document.createElement("div");
            bubble.className = "bubble";
            bubble.textContent = text;
            div.appendChild(bubble);
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }
        
        async function send() {
            const text = input.value.trim();
            if (!text) return;
            input.value = "";
            addMsg("user", text);
            sendBtn.disabled = true;
            
            try {
                const res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({message: text, history: history})
                });
                const data = await res.json();
                addMsg("assistant", data.response);
                history.push([text, data.response]);
            } catch(e) {
                addMsg("assistant", "请求失败: " + e.message);
            }
            sendBtn.disabled = false;
        }
    </script>
</body>
</html>
    """
    
    @app.route("/")
    def index():
        mode = "Mode: Knowledge Enhanced" if kr else "Mode: Basic Chat"
        return render_template_string(HTML, mode=mode)
    
    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json()
        message = data.get("message", "")
        hist = data.get("history", [])
        response = get_response(message, hist, collection)
        return jsonify({"response": response})
    
    print("=" * 50)
    print("  JiaoYuan AI Advisor Starting...")
    print("  Open: http://localhost:7861")
    print("=" * 50)
    app.run(host="0.0.0.0", port=7861, debug=False)

if __name__ == "__main__":
    main()
