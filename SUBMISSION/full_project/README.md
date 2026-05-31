# AI Labor Market Simulation

A 20-year projection of global labor markets under three AI-adoption scenarios
(slow, moderate, rapid). FastAPI backend + vanilla-JS frontend, no build step.

## Architecture

```
┌──────────────┐    HTTP/JSON    ┌──────────────────────┐
│   Browser    │ ◄────────────►  │  FastAPI (port 8000) │
│  6 HTML pgs  │                 │  ┌────────────────┐  │
└──────────────┘                 │  │  simulation.py │  │  ← core model
                                 │  │  forecast.py   │  │  ← RF unemployment
                                 │  │  llm.py        │  │  ← Ollama (Arabic)
                                 │  └────────────────┘  │
                                 └──────────┬───────────┘
                                            │
                                ┌───────────┴───────────┐
                                │   World Bank API      │
                                │   Ollama (localhost)  │
                                └───────────────────────┘
```

## Running locally

```powershell
# 1. Install backend dependencies
python -m pip install -r requirements.txt

# 2. Start the API (terminal 1)
python -m uvicorn backend.app:app --reload --port 8000

# 3. Serve the frontend (terminal 2)
python -m http.server 5500 --directory frontend

# 4. Open the dashboard
start http://localhost:5500/index.html
```

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/`                            | Health check |
| GET  | `/api/simulate/{scenario}`     | Run a full 20-year simulation (`slow`/`moderate`/`rapid`) |
| GET  | `/api/compare`                 | Run all 3 scenarios in one call |
| GET  | `/api/monte-carlo`             | 1000 random futures, returns 95% CI band |
| GET  | `/api/sensitivity`             | ±20% perturbation impact on final unemployment |
| GET  | `/api/validate`                | Backtest against World Bank 2000–2020 |
| POST | `/api/analyze`                 | Arabic economic advisory report (Ollama) |
| GET  | `/api/models`                  | List installed Ollama models |
| GET  | `/api/oxford-risk`             | 10-category automation risk reference |

## Project layout

```
MODEL-SIMULATION-CLEAN/
├── .gitignore
├── README.md
├── requirements.txt
├── backend/
│   ├── __init__.py
│   ├── simulation.py   ← core math, scenarios, monte carlo, sensitivity, validate
│   ├── forecast.py     ← RandomForest unemployment forecaster
│   ├── llm.py          ← Ollama-driven Arabic advisory report
│   └── app.py          ← FastAPI surface
└── frontend/
    ├── style.css
    ├── app.js
    ├── index.html       ← Overview dashboard
    ├── scenarios.html   ← Compare slow / moderate / rapid
    ├── macroeconomy.html← GDP · wages · Gini · spending
    ├── sector.html      ← Per-sector breakdown
    ├── ai_impact.html   ← S-curve · productivity · Oxford risk
    └── validation.html  ← Backtest · Monte Carlo · sensitivity · Arabic LLM report
```

## Optional: Ollama LLM

`/api/analyze` generates the Arabic advisory report via [Ollama](https://ollama.com).

```powershell
# Install once, then pull a model
ollama pull qwen3.5:9b              # 6.6 GB, fully local
# OR  ollama pull kimi-k2.6:cloud   # cloud-routed, faster
```

By default the API uses `kimi-k2.6:cloud`, falling back to `qwen3.5:9b`.
Override via env var:

```powershell
$env:OLLAMA_MODEL = "qwen3.5:9b"
$env:OLLAMA_HOST  = "http://localhost:11434"   # default
```

The frontend `validation.html` page also shows a model dropdown populated from
`/api/models` — pick any installed model at request time.
