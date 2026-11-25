import os
import secrets
import sqlite3
import string
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, render_template_string, request

DB_PATH = os.environ.get("DB_PATH", "shortener.db")
ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 6

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                code TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def valid_url(url):
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def new_code(db):
    for _ in range(10):
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if not db.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone():
            return code
    raise RuntimeError("could not generate a unique code")


def create_link(url, custom=None):
    """Returns (code, error)."""
    url = (url or "").strip()
    if not valid_url(url):
        return None, "Enter a valid http(s) URL."
    db = get_db()
    if custom:
        custom = custom.strip()
        if not (3 <= len(custom) <= 32) or not all(c in ALPHABET + "-_" for c in custom):
            return None, "Custom alias must be 3-32 chars: letters, digits, - or _."
        if custom in ("api", "stats", "static"):
            return None, "That alias is reserved."
        if db.execute("SELECT 1 FROM links WHERE code = ?", (custom,)).fetchone():
            return None, "That alias is already taken."
        code = custom
    else:
        code = new_code(db)
    db.execute("INSERT INTO links (code, url) VALUES (?, ?)", (code, url))
    db.commit()
    return code, None


PAGE = """
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shorty</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 560px; margin: 48px auto; padding: 0 16px; }
  input { width: 100%; padding: 10px; margin: 6px 0; box-sizing: border-box; font-size: 16px; }
  button { padding: 10px 18px; font-size: 16px; cursor: pointer; }
  .msg { margin-top: 16px; padding: 12px; background: #eef; border-radius: 6px; word-break: break-all; }
  .err { background: #fee; }
  table { width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 14px; }
  td, th { text-align: left; padding: 6px 4px; border-bottom: 1px solid #ddd; word-break: break-all; }
</style>
<h1>Shorty</h1>
<form method="post" action="/">
  <input name="url" type="url" placeholder="https://example.com/very/long/link" required>
  <input name="custom" placeholder="Custom alias (optional)">
  <button>Shorten</button>
</form>
{% if short %}<div class="msg">Short URL: <a href="{{ short }}">{{ short }}</a></div>{% endif %}
{% if error %}<div class="msg err">{{ error }}</div>{% endif %}
{% if links %}
<table>
  <tr><th>Short</th><th>Destination</th><th>Clicks</th></tr>
  {% for l in links %}
  <tr><td><a href="/{{ l.code }}">/{{ l.code }}</a></td><td>{{ l.url }}</td><td>{{ l.clicks }}</td></tr>
  {% endfor %}
</table>
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def index():
    short = error = None
    if request.method == "POST":
        code, error = create_link(request.form.get("url"), request.form.get("custom"))
        if code:
            short = request.host_url + code
    links = get_db().execute(
        "SELECT code, url, clicks FROM links ORDER BY created_at DESC, rowid DESC LIMIT 20"
    ).fetchall()
    return render_template_string(PAGE, short=short, error=error, links=links)


@app.post("/api/shorten")
def api_shorten():
    data = request.get_json(silent=True) or {}
    code, error = create_link(data.get("url"), data.get("alias"))
    if error:
        return jsonify(error=error), 400
    return jsonify(code=code, short_url=request.host_url + code), 201


@app.get("/api/stats/<code>")
def api_stats(code):
    row = get_db().execute(
        "SELECT code, url, clicks, created_at FROM links WHERE code = ?", (code,)
    ).fetchone()
    if not row:
        return jsonify(error="Not found"), 404
    return jsonify(dict(row))


@app.get("/<code>")
def follow(code):
    db = get_db()
    row = db.execute("SELECT url FROM links WHERE code = ?", (code,)).fetchone()
    if not row:
        return "Link not found", 404
    db.execute("UPDATE links SET clicks = clicks + 1 WHERE code = ?", (code,))
    db.commit()
    return redirect(row["url"], code=302)


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
