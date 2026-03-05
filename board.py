#!/usr/bin/env python3
"""
board.py — Virtual Drawing Board (test server)

Serves a drawing canvas at http://localhost:8080.
Every stroke you draw is forwarded as normalized (0–1) events to
receiver.py's WebSocket server at ws://localhost:8765.

Requirements:
    pip install websockets   (only stdlib + websockets needed)

Start receiver.py first, then run this script.
"""

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HTTP_PORT = 8080
WS_RELAY  = "ws://localhost:8765"

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Virtual Board</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #1a1a2e;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100vh;
    font-family: 'Segoe UI', system-ui, sans-serif;
    color: #eee;
    user-select: none;
  }}
  header {{
    width: 100%;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 10px 20px;
    background: #16213e;
    border-bottom: 1px solid #0f3460;
    flex-wrap: wrap;
  }}
  header h1 {{ font-size: 1.1rem; font-weight: 600; color: #00ff88; margin-right: auto; }}
  .control {{ display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }}
  label {{ color: #aaa; }}
  input[type=color] {{ width: 32px; height: 28px; border: none; border-radius: 4px; cursor: pointer; padding: 0; background: none; }}
  input[type=range] {{ width: 80px; accent-color: #00ff88; }}
  button {{
    padding: 6px 14px;
    border: 1px solid #00ff88;
    background: transparent;
    color: #00ff88;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    transition: background 0.15s;
  }}
  button:hover {{ background: #00ff8820; }}
  #status {{
    font-size: 0.8rem;
    padding: 3px 10px;
    border-radius: 12px;
    background: #333;
    color: #aaa;
  }}
  #status.connected {{ background: #003320; color: #00ff88; }}
  #status.disconnected {{ background: #330000; color: #ff5555; }}
  #canvas-wrap {{
    flex: 1;
    width: 100%;
    position: relative;
    overflow: hidden;
  }}
  canvas {{
    display: block;
    width: 100%;
    height: 100%;
    cursor: crosshair;
    background: #fff;
  }}
</style>
</head>
<body>

<header>
  <h1>Virtual Board</h1>

  <div class="control">
    <label for="colorPicker">Color</label>
    <input type="color" id="colorPicker" value="#000000">
  </div>

  <div class="control">
    <label for="sizeSlider">Size</label>
    <input type="range" id="sizeSlider" min="1" max="40" value="4">
    <span id="sizeVal">4</span>
  </div>

  <button id="clearBtn">Clear</button>
  <div id="status" class="disconnected">Disconnected</div>
</header>

<div id="canvas-wrap">
  <canvas id="board"></canvas>
</div>

<script>
const canvas  = document.getElementById('board');
const ctx     = canvas.getContext('2d');
const colorEl = document.getElementById('colorPicker');
const sizeEl  = document.getElementById('sizeSlider');
const sizeVal = document.getElementById('sizeVal');
const statusEl= document.getElementById('status');
const clearBtn= document.getElementById('clearBtn');

// ── resize ─────────────────────────────────────────────────────────────────
function resize() {{
  const wrap = document.getElementById('canvas-wrap');
  canvas.width  = wrap.clientWidth;
  canvas.height = wrap.clientHeight;
}}
resize();
window.addEventListener('resize', resize);

// ── WebSocket ──────────────────────────────────────────────────────────────
let ws = null;
let reconnectTimer = null;

function connect() {{
  if (ws && ws.readyState <= 1) return;
  ws = new WebSocket('{WS_RELAY}');
  ws.onopen = () => {{
    statusEl.textContent = 'Connected';
    statusEl.className = 'connected';
  }};
  ws.onclose = () => {{
    statusEl.textContent = 'Disconnected — retrying…';
    statusEl.className = 'disconnected';
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 2000);
  }};
  ws.onerror = () => ws.close();
}}
connect();

function send(type, x, y) {{
  if (!ws || ws.readyState !== 1) return;
  const nx = x / canvas.width;
  const ny = y / canvas.height;
  ws.send(JSON.stringify({{ type, x: nx, y: ny }}));
}}

function sendClear() {{
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({{ type: 'clear' }}));
}}

// ── local drawing ──────────────────────────────────────────────────────────
let drawing = false;
let lastX = 0, lastY = 0;

function getColor() {{ return colorEl.value; }}
function getSize()  {{ return parseInt(sizeEl.value); }}

function startDraw(x, y) {{
  drawing = true;
  lastX = x; lastY = y;
  ctx.beginPath();
  ctx.arc(x, y, getSize() / 2, 0, Math.PI * 2);
  ctx.fillStyle = getColor();
  ctx.fill();
  send('mousedown', x, y);
}}

function moveDraw(x, y) {{
  if (!drawing) return;
  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(x, y);
  ctx.strokeStyle = getColor();
  ctx.lineWidth   = getSize();
  ctx.lineCap     = 'round';
  ctx.lineJoin    = 'round';
  ctx.stroke();
  lastX = x; lastY = y;
  send('mousemove', x, y);
}}

function endDraw(x, y) {{
  if (!drawing) return;
  drawing = false;
  send('mouseup', x, y);
}}

// ── mouse ──────────────────────────────────────────────────────────────────
canvas.addEventListener('mousedown', e => startDraw(e.offsetX, e.offsetY));
canvas.addEventListener('mousemove', e => moveDraw(e.offsetX, e.offsetY));
canvas.addEventListener('mouseup',   e => endDraw(e.offsetX, e.offsetY));
canvas.addEventListener('mouseleave',e => {{ if (drawing) endDraw(e.offsetX, e.offsetY); }});

// ── touch ──────────────────────────────────────────────────────────────────
function touchCoords(e) {{
  const t   = e.touches[0];
  const r   = canvas.getBoundingClientRect();
  const scaleX = canvas.width  / r.width;
  const scaleY = canvas.height / r.height;
  return [(t.clientX - r.left) * scaleX, (t.clientY - r.top) * scaleY];
}}
canvas.addEventListener('touchstart', e => {{ e.preventDefault(); startDraw(...touchCoords(e)); }}, {{passive: false}});
canvas.addEventListener('touchmove',  e => {{ e.preventDefault(); moveDraw(...touchCoords(e));  }}, {{passive: false}});
canvas.addEventListener('touchend',   e => {{ e.preventDefault(); endDraw(lastX, lastY);        }}, {{passive: false}});

// ── controls ───────────────────────────────────────────────────────────────
sizeEl.addEventListener('input', () => sizeVal.textContent = sizeEl.value);
clearBtn.addEventListener('click', () => {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  sendClear();
}});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # silence request logs


def main():
    print("=" * 55)
    print("  Virtual Board — Drawing Board")
    print("=" * 55)
    print(f"\nMake sure receiver.py is running first.\n")
    print(f"Opening board at http://localhost:{HTTP_PORT} …\n")

    server = HTTPServer(("localhost", HTTP_PORT), Handler)

    def open_browser():
        import time; time.sleep(0.4)
        webbrowser.open(f"http://localhost:{HTTP_PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBoard server stopped.")


if __name__ == "__main__":
    main()
