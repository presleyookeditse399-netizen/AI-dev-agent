import os, subprocess, json, openai
from flask import Flask, request, send_from_directory
from pathlib import Path

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
PROJECT_DIR = Path("sandbox")
PROJECT_DIR.mkdir(exist_ok=True)

def write_file(path, content):
    p = PROJECT_DIR / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Created {path}"

def run_cmd(cmd):
    r = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=90)
    return r.stdout + r.stderr

tools = {"write_file": write_file, "run_cmd": run_cmd}

tool_schemas = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a file with content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path like index.html"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_cmd",
            "description": "Run bash command to test the app",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Command to run"}
                },
                "required": ["cmd"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are an AI coding agent. Build web apps from 1 prompt.
Rules:
1. First use write_file to create index.html, style.css, script.js
2. Then use run_cmd with 'python -m http.server 8000 --bind 0.0.0.0' to test
3. Keep HTML+CSS+JS simple so it runs on Render free tier"""

@app.route("/")
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>AI Dev Agent</title></head>
    <body style="font-family:Arial;padding:20px">
    <h2>🤖 AI Dev Agent v1 - Render</h2>
    <textarea id="q" rows="4" style="width:100%;font-size:14px">Make me a calculator app with HTML CSS JS</textarea><br><br>
    <button onclick="go()" style="padding:10px 20px;font-size:16px">Build App</button>
    <h3>Agent Log:</h3>
    <pre id="log" style="background:#f4f4f4;padding:10px;min-height:150px"></pre>
    <h3>Live Preview:</h3>
    <iframe id="preview" style="width:100%;height:500px;border:2px solid #ccc"></iframe>
    <script>
    async function go(){
      document.getElementById("log").textContent = "Agent is building...";
      let res = await fetch("/build", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({prompt:document.getElementById("q").value})
      });
      let text = await res.text();
      document.getElementById("log").textContent = text;
      document.getElementById("preview").src = "/preview/index.html?t=" + Date.now();
    }
    </script>
    </body>
    </html>
    '''

@app.route("/build", methods=["POST"])
def build():
    prompt = request.json["prompt"]
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    log = []

    for step in range(8):
        log.append(f"--- Step {step+1} ---")
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=msgs,
            tools=tool_schemas,
            tool_choice="auto"
        )
        msg = resp.choices[0].message
        msgs.append(msg)

        if msg.content:
            log.append("Agent: " + msg.content)

        if not msg.tool_calls:
            log.append("\n✅ Done! Check preview below")
            break

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = tools[tc.function.name](**args)
            log.append(f"Tool {tc.function.name}: {result[:200]}")
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "\n".join(log)

@app.route("/preview/<path:filename>")
def preview(filename):
    return send_from_directory(PROJECT_DIR, filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
