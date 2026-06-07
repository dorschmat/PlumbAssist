#!/usr/bin/env python3
"""
PlumbAssist local server - uses Google Gemini API (free tier available).
Usage:
  1. Get a free API key at: https://aistudio.google.com/app/apikey
  2. In PyCharm: Edit Configurations > Environment Variables
     Add: GEMINI_API_KEY = your_key_here
  3. Run this file in PyCharm
  4. Open: http://localhost:8000
"""

import os, json, http.server, urllib.request, urllib.error
from pathlib import Path

PORT = int(os.environ.get("PORT", 8000))
_parent = Path(__file__).parent
HTML_FILE = _parent / "plumbassist.html" if (_parent / "plumbassist.html").exists() else _parent / "plumbassist"

MODELS_TO_TRY = [
    "gemini-2.5-flash",
]

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} - {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(HTML_FILE, "text/html; charset=utf-8")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/chat":
            self._proxy_gemini()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, path, content_type):
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_cors()
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"plumbassist.html not found - place it next to plumbassist_server.py")

    def _proxy_gemini(self):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            self._json_error(500, "GEMINI_API_KEY not set. Add it in PyCharm Edit Configurations > Environment Variables.")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except Exception:
            self._json_error(400, "Invalid JSON")
            return

        # Convert Anthropic-style messages to Gemini format
        messages = payload.get("messages", [])
        system = payload.get("system", "")

        gemini_contents = []

        if system:
            gemini_contents.append({
                "role": "user",
                "parts": [{"text": "[SYSTEM INSTRUCTIONS]\n" + system}]
            })
            gemini_contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow these instructions."}]
            })

        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        gemini_payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 400
            }
        }

        print(f"  Gemini request: {len(messages)} message(s) - trying models...")

        # Try each model until one works
        for model_name in MODELS_TO_TRY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(gemini_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    result = json.loads(resp.read())

                # Success! Extract text and return
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"  OK using {model_name}: {len(text)} chars")

                out = json.dumps({"content": [{"type": "text", "text": text}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(out)
                return

            except urllib.error.HTTPError as e:
                err_body = e.read()
                print(f"  {model_name} -> {e.code}, trying next...")
                last_err_code = e.code
                last_err_body = err_body
                continue
            except Exception as e:
                print(f"  {model_name} exception: {e}, trying next...")
                last_err_code = 502
                last_err_body = str(e).encode()
                continue

        # All models failed
        print(f"  All models failed. Last error: {last_err_code}")
        self.send_response(last_err_code)
        self.send_header("Content-Type", "application/json")
        self.send_cors()
        self.end_headers()
        self.wfile.write(last_err_body)

    def _json_error(self, code, msg):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    key_set = bool(os.environ.get("GEMINI_API_KEY"))
    print()
    print("  ==========================================")
    print("   PlumbAssist local server (Gemini AI)")
    print("  ==========================================")
    print()
    if not key_set:
        print("  WARNING: GEMINI_API_KEY is not set!")
        print()
        print("  1. Go to: https://aistudio.google.com/app/apikey")
        print("  2. Click Create API Key")
        print("  3. In PyCharm: Edit Configurations > Environment Variables")
        print("     Add: GEMINI_API_KEY = your_key_here")
        print("  4. Stop and re-run this server")
        print()
    else:
        print("  API key found")
    print(f"  Server running on port {PORT}")
    print("  Press Ctrl+C to stop")
    print()

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
