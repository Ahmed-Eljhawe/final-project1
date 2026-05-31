# How to Run — AI Labor Market Simulation

A 20-year projection of global labor markets under three AI-adoption scenarios.
This guide takes you from a fresh machine to a running dashboard in under 5 minutes.

---

## 1. Prerequisites

You need **only Python** installed. Everything else is auto-installed in step 2.

| Tool | Version | Check with |
|------|---------|-----------|
| Python | 3.10 or newer | `python --version` |
| pip (comes with Python) | any | `python -m pip --version` |
| Internet connection | — | required for World Bank API calls |

> **Don't have Python?** Download it from <https://www.python.org/downloads/>.
> On Windows, **check "Add Python to PATH"** in the installer.

---

## 2. Install dependencies (one-time setup)

Open a terminal **inside the `full_project/` folder**, then run:

```powershell
python -m pip install -r requirements.txt
```

This installs FastAPI, scikit-learn, pandas, numpy, and the other libraries listed in `requirements.txt`.
It takes about 1–2 minutes.

---

## 3. Start the backend API (terminal 1)

In the same terminal (still inside `full_project/`), run:

```powershell
python -m uvicorn backend.app:app --reload --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**Leave this terminal open.** This is the backend.

---

## 4. Start the frontend (terminal 2)

Open a **second** terminal in the same `full_project/` folder, then run:

```powershell
python -m http.server 5500 --directory frontend
```

You should see:

```
Serving HTTP on :: port 5500 (http://[::]:5500/) ...
```

**Leave this terminal open too.**

---

## 5. Open the dashboard

Open a web browser and go to:

> **<http://localhost:5500/index.html>**

The Overview page should load with KPI cards and charts.

---

## 6. Verify everything works (smoke test)

In a **third** terminal (still inside `full_project/`), run:

```powershell
python test_smoke.py
```

This pings every API endpoint and confirms they all return valid data.
All checks should print `✓ ok`.

You can also manually verify the API by visiting:
- <http://localhost:8000/> — health check
- <http://localhost:8000/docs> — interactive Swagger API documentation
- <http://localhost:8000/api/simulate/moderate> — full simulation result

---

## 7. Using the dashboard

The dashboard has 6 pages, navigable from the sidebar:

| Page | What it shows |
|------|---------------|
| **Overview** | Headline KPIs + summary charts |
| **Scenarios** | Side-by-side comparison of slow / moderate / rapid AI adoption |
| **Macroeconomy** | GDP, wages by skill tier, Gini inequality, consumer spending |
| **Sector** | Per-sector jobs (Tech / Manufacturing / Healthcare / Services) |
| **AI Impact** | Adoption S-curve, productivity gains, Frey & Osborne occupation risk |
| **Validation** | Backtest against 2000–2020 World Bank data, Monte Carlo, AI-generated report |

**Controls in the sidebar:**
- **Scenario** dropdown — slow (3%), moderate (5%), or rapid (8%) annual automation
- **Country** dropdown — 30 World Bank countries supported (default: World aggregate)
- **AI Adoption Speed** slider — multiplier on the S-curve (0.5× = slower rollout, 2× = faster)
- **Horizon** slider — how many years to project (5–30, default 20)

After changing any control, click **Run Simulation** on the page to recompute.

---

## 8. Arabic AI Advisory Report — three engines

The Validation page generates a 6-section **Arabic economic advisory report** from the simulation numbers. Pick the engine from the dropdown next to the report panel:

### 8.1 Built-in (default — always works, no setup)

Deterministic Python report generator that plugs the actual simulation numbers into a structured Arabic template. **Zero setup.** Produces a coherent 6-section report every time.

Use this for demos — guarantees a working report no matter what.

### 8.2 Groq LLM (free cloud, varies every run)

Real cloud LLM (Llama 3.3 70B) via [Groq](https://groq.com). **Free, no credit card.** Each run produces different wording while staying faithful to the numbers.

**Setup (1 minute) — the project auto-loads a `.env` file in the root, so you only set this up once and it works for anyone who runs the project:**

1. Sign up at <https://console.groq.com> (Google login, no payment)
2. Go to **API Keys** → **Create API Key** → copy the `gsk_...` token
3. Open the `.env` file in the project root with any text editor
4. Paste your key on the `GROQ_API_KEY=` line:
   ```ini
   GROQ_API_KEY=gsk_paste_your_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```
5. Save the file
6. Restart the backend if it was running (Ctrl+C in terminal 1, then re-run `uvicorn`)
7. On the Validation page, select **Groq LLM** in the engine dropdown, then click **▸ Arabic AI Report**

Free tier: 30 req/min, 14,400/day — far more than a demo will use.

> **For sharing the project:** since the `.env` file lives inside the project folder, once you've put your key in it, anyone you give the zipped project to gets Groq working automatically — no setup on their side.

### 8.3 Ollama LLM (fully local)

Local LLM via [Ollama](https://ollama.com). Heavier setup but works offline.

```powershell
# Install once, then pull a model
ollama pull qwen3.5:9b              # 6.6 GB, fully local
# OR
ollama pull kimi-k2.6:cloud         # cloud-routed, faster
```

Override the model:
```powershell
$env:OLLAMA_MODEL = "qwen3.5:9b"
```

Then select **Ollama LLM** in the engine dropdown on the Validation page.

**Note:** any LLM failure (no API key, Ollama not running, network down) **automatically falls back to the Built-in engine** so the report panel is never empty.

---

## Quick-reference cheat sheet

```powershell
# One-time
python -m pip install -r requirements.txt

# Every run — open TWO terminals in full_project/
# Terminal 1 (backend):
python -m uvicorn backend.app:app --reload --port 8000

# Terminal 2 (frontend):
python -m http.server 5500 --directory frontend

# Browser:
# → http://localhost:5500/index.html
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python: command not found` | Python isn't installed or not on PATH. Reinstall and tick "Add to PATH". |
| `ModuleNotFoundError: No module named 'fastapi'` | You skipped step 2. Run `pip install -r requirements.txt` again. |
| `Address already in use` on port 8000 | Another program is using that port. Change `--port 8000` to `--port 8001` and update `API_BASE` in `frontend/app.js` to `http://localhost:8001`. |
| Charts don't load / page is blank | The backend isn't running. Check terminal 1. Also open the browser console (F12) for errors. |
| `CORS error` in browser console | The backend isn't running or the frontend is pointed at the wrong URL. Confirm `API_BASE = 'http://localhost:8000'` in `frontend/app.js`. |
| World Bank API timeout | Internet connectivity issue. The model falls back to built-in default values automatically. |
| Ollama report fails | Either Ollama isn't running (`ollama serve`) or no model is pulled. See section 8. |

---

## Project structure (for reference)

```
full_project/
├── README.md                  # Brief project overview
├── HOW_TO_RUN.md              # This file
├── requirements.txt           # Python dependencies
├── test_smoke.py              # End-to-end smoke test
├── backend/                   # FastAPI server
│   ├── app.py                 # 11 API endpoints
│   ├── simulation.py          # Core 20-year simulation engine
│   ├── forecast.py            # Random Forest unemployment forecaster
│   ├── llm.py                 # Ollama AI advisory report
│   └── data/
│       └── frey_osborne.csv   # Frey & Osborne 2013 automation data
└── frontend/                  # Vanilla JS dashboard (no build step)
    ├── index.html             # Overview page
    ├── scenarios.html         # 3-way scenario comparison
    ├── macroeconomy.html      # GDP / wages / Gini
    ├── sector.html            # Per-sector view
    ├── ai_impact.html         # Adoption S-curve / Oxford risk
    ├── validation.html        # Backtest / Monte Carlo / LLM
    ├── app.js                 # Shared API + chart helpers
    └── style.css              # Dashboard styles
```

---

## Stopping the project

In each open terminal, press **Ctrl+C**.
