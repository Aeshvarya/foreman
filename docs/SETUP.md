# Foreman — Local Setup

Written so someone who didn't build this can get it running.

## Requirements

- Python **3.11+**
- Docker (for Neo4j)
- Node 18+ (only if you're rebuilding the frontend)
- A Gemini API key (free tier) — optional; the engine runs without it, the
  agents don't

## 1. Install

```bash
git clone <repo> && cd foreman
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start Neo4j

```bash
docker compose up -d
```

Gives you:

```
Browser  http://localhost:7474      user: neo4j   pass: foreman123
Bolt     bolt://localhost:7687
```

Data persists in the `foreman_neo4j_data` volume. The compose file pins
`neo4j:5-community` with a 256M pagecache / 512M heap and a healthcheck.

## 3. Environment

Create `.env` in the repo root:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=foreman123
NEO4J_DATABASE=              # optional, defaults to the server default

GEMINI_API_KEY=your-key      # optional — agents are disabled without it
GEMINI_MODEL=gemini-flash-lite-latest

ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FOREMAN_NO_LLM_CACHE=        # set to any value to disable the disk cache
```

| Variable | Default | Notes |
|---|---|---|
| `NEO4J_URI` | *(unset)* | **If unset, Foreman runs from project JSON.** The engine works; the query agent doesn't |
| `NEO4J_USERNAME` / `NEO4J_USER` | — | either name is read |
| `NEO4J_PASSWORD` | `foreman123` | |
| `GEMINI_API_KEY` | *(unset)* | no key → `/api/ask` unavailable, everything deterministic still works |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | chosen over `gemini-2.5-flash`, which caps at 5 req/min and throttles a live demo |
| `ALLOWED_ORIGINS` | localhost:5173 | CORS |

## 4. Load the graph

```bash
python -m src.db --load      # wipes Neo4j, loads the active project
python -m src.db --verify    # node/edge counts + a sample query
```

Expect the demo project ("Sunrise DC-1"): **6 suppliers, 8 materials,
12 activities, 29 edges — 26 nodes.**

## 5. Run

```bash
uvicorn backend.main:app --reload --port 8000
```

- API → `http://localhost:8000/api/health`
- The app serves the built SPA at `/`

Frontend dev server (hot reload):

```bash
cd web && npm install && npm run dev     # http://localhost:5173
```

Legacy Streamlit UI (fallback, not the demo surface):

```bash
streamlit run app.py
```

Or use `./dev.sh`.

## 6. Verify it works

```bash
curl localhost:8000/api/health
# {"ok":true,"graph":"neo4j","graph_detail":"26 nodes","llm":true}
```

`"graph":"json"` means Neo4j isn't connected — check `NEO4J_URI`.

```bash
pytest tests/ -q          # test_mirror, test_money, test_montecarlo
```

All three suites should pass.

## 7. Check the published numbers are current

```bash
python scripts/verify_live_numbers.py --check
```

Re-reads the live deployment and **fails if `docs/NUMBERS.md` has gone stale.**
Standing rule: **if a number is not in `NUMBERS.md`, it is not claimed.**

---

## Deployment

`render.yaml` + root `Dockerfile`. The hosted instance runs on Render's free
tier, which cold-starts — worth warming before any live demo.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `"graph":"json"` in health | `NEO4J_URI` unset or unreachable |
| `/api/ask` fails | no `GEMINI_API_KEY` |
| Agent returns odd/empty text | Gemini 3.x returns content as a **list of parts** — always use `invoke_text()`, never `.content` raw |
| Empty alternate-supplier results | `category_of()` didn't match the material name (see `LIMITATIONS.md`) |
| `test_money` fails unexpectedly | stale project loaded in local Neo4j — re-run `python -m src.db --load` |
| Slow first request | Render cold start + LLM warm-up |
