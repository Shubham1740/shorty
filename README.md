# Shorty — a tiny URL shortener

Flask + SQLite. Web form, JSON API, redirects, and click counts.

## Run

```
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## API

```
# create (alias is optional)
curl -X POST localhost:5000/api/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/long", "alias": "demo"}'

# stats
curl localhost:5000/api/stats/demo
```

Visiting `/<code>` redirects (302) and increments the click counter.

## Config

- `DB_PATH` — SQLite file (default `shortener.db`)
- `PORT` — default 5000
