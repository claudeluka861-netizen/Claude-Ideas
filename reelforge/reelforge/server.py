"""Local review site. Standard library only — nothing to install, nothing exposed.

Binds to 127.0.0.1 so it is reachable from this machine and nowhere else.
"""
import html
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import generate, publish, render, store
from .config import OUT_DIR

PAGE = """<!doctype html><meta charset=utf-8>
<title>ReelForge</title>
<style>
:root{--bg:#11141B;--card:#171B24;--ink:#EDEAE2;--muted:#8C90A0;--accent:#E8A33D;--line:rgba(236,233,225,.1);--ok:#4C9A6A;--bad:#D8674F}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif;padding:32px}
header{display:flex;justify-content:space-between;align-items:center;max-width:1100px;margin:0 auto 24px}
h1{font-size:20px;margin:0;letter-spacing:-.01em}
.muted{color:var(--muted);font-size:13px}
.bar{display:flex;gap:8px;flex-wrap:wrap}
button,a.btn{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;
  padding:8px 14px;font:inherit;font-size:13px;cursor:pointer;text-decoration:none}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);color:#11141B;border-color:var(--accent);font-weight:600}
.wrap{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
.post{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}
.post h2{font-size:17px;margin:0 0 4px}
.meta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.tag{font-size:11px;letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
.tag.rendered{color:var(--accent);border-color:var(--accent)}
.tag.approved{color:var(--ok);border-color:var(--ok)}
.tag.published{background:var(--ok);color:#11141B;border-color:var(--ok)}
.tag.rejected{color:var(--bad);border-color:var(--bad)}
.strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px}
.strip img{height:230px;border-radius:8px;border:1px solid var(--line);flex:none}
.cap{white-space:pre-wrap;background:#11141B;border:1px solid var(--line);border-radius:8px;
  padding:12px;font-size:13px;color:var(--muted);margin:14px 0}
.empty{text-align:center;color:var(--muted);padding:60px 0}
</style>
<header>
  <div><h1>ReelForge</h1><div class="muted" id="count"></div></div>
  <div class="bar">
    <button onclick="act('/api/generate?count=1')">Generate 1</button>
    <button onclick="act('/api/generate?count=3')">Generate 3</button>
    <button class="primary" onclick="act('/api/render')">Render pending</button>
  </div>
</header>
<div class="wrap" id="list"></div>
<script>
async function act(url){
  const bar = document.querySelector('.bar');
  bar.style.opacity = .5;
  try { await fetch(url, {method:'POST'}); } finally { bar.style.opacity = 1; load(); }
}
function esc(s){ return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
async function load(){
  const posts = await (await fetch('/api/posts')).json();
  document.getElementById('count').textContent =
    posts.length + ' posts \\u00b7 ' + posts.filter(p=>p.status==='published').length + ' published';
  document.getElementById('list').innerHTML = posts.length ? posts.map(p => `
    <div class="post">
      <div class="meta">
        <span class="tag ${esc(p.status)}">${esc(p.status)}</span>
        <span class="muted">${esc(p.id)} \\u00b7 ${esc(p.theme)}</span>
      </div>
      <h2>${esc(p.hook)}</h2>
      <div class="muted">${esc(p.subhook||'')}</div>
      <div class="strip">${(p.slide_urls||[]).map(u=>`<img src="${u}" loading=lazy>`).join('')}</div>
      <div class="cap">${esc(p.caption)}\n\n${(p.hashtags||[]).map(t=>'#'+t).join(' ')}</div>
      <div class="bar">
        <button onclick="act('/api/approve?id=${p.id}')">Approve</button>
        <button onclick="act('/api/reject?id=${p.id}')">Reject</button>
        <button class="primary" onclick="act('/api/publish?id=${p.id}')">Publish now</button>
      </div>
    </div>`).join('') : '<div class="empty">Nothing yet. Hit Generate.</div>';
}
load();
</script>
"""


class Handler(BaseHTTPRequestHandler):
    cfg = None

    def log_message(self, *args):
        pass  # quiet

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/posts":
            posts = store.all_posts()
            for post in posts:
                post["slide_urls"] = [
                    f"/slides/{post['id']}/{Path(p).name}" for p in post.get("images", [])
                ]
            return self._send(200, json.dumps(posts))
        if path.startswith("/slides/"):
            rel = path[len("/slides/") :]
            target = (OUT_DIR / rel).resolve()
            if OUT_DIR.resolve() not in target.parents or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            return self._send(200, target.read_bytes(), "image/png")
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        query = self._query()
        try:
            if path == "/api/generate":
                count = int(query.get("count", ["1"])[0])
                generate.generate(self.cfg, count)
            elif path == "/api/render":
                pending = store.by_status("draft")
                if pending:
                    render.render_all(self.cfg, pending)
            elif path == "/api/approve":
                post = store.get(query["id"][0])
                post["status"] = "approved"
                store.save(post)
            elif path == "/api/reject":
                post = store.get(query["id"][0])
                post["status"] = "rejected"
                store.save(post)
            elif path == "/api/publish":
                publish.publish_post(store.get(query["id"][0]), self.cfg)
            else:
                return self._send(404, json.dumps({"error": "unknown endpoint"}))
        except Exception as exc:
            return self._send(500, json.dumps({"error": str(exc)}))
        return self._send(200, json.dumps({"ok": True}))


def serve(cfg, port=8765):
    Handler.cfg = cfg
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"ReelForge review site: http://127.0.0.1:{port}")
    print("Ctrl+C to stop.")
    server.serve_forever()
