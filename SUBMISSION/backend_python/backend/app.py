"""FastAPI surface for the AI Labor Market Simulation."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.simulation import (
    compare_scenarios,
    export_csv,
    get_country_baseline,
    monte_carlo,
    run_scenario,
    sensitivity,
    validate,
)
from backend.forecast import forecast_unemployment
from backend.llm import (analyze_with_local_llm, list_available_models,
                         generate_builtin_summary, analyze_with_groq,
                         list_groq_models)

DATA_DIR = Path(__file__).parent / "data"


app = FastAPI(
    title="AI Labor Market Impact Simulation API",
    description="20-year labor-market simulation under AI adoption scenarios.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Curated 10-category grouping inspired by Frey & Osborne 2013 (Oxford Martin
# School). Kept here as the single source of truth — the frontend fetches it
# from this endpoint instead of hardcoding the values.
OXFORD_RISK_DATA = {
    "jobs": [
        "Clerical", "Transport", "Manufacturing", "Retail", "Food Service",
        "Healthcare Support", "Education", "Management", "Engineering", "Creative",
    ],
    "risk": [0.96, 0.89, 0.85, 0.77, 0.72, 0.35, 0.22, 0.18, 0.12, 0.08],
    "source": "Frey & Osborne 2013 (Oxford Martin School) — 10-category simplification",
}


class AnalyzeRequest(BaseModel):
    scenario:       Optional[str]   = "moderate"
    horizon:        Optional[int]   = 20
    adoption_speed: Optional[float] = 1.0
    country:        Optional[str]   = "WLD"
    model:          Optional[str]   = None
    # engine: "builtin" (default, deterministic, always works) or "ollama" (requires Ollama)
    engine:         Optional[str]   = "builtin"


# 30 most-relevant World Bank country codes for the frontend dropdown.
COUNTRIES = [
    {"code": "WLD", "name": "World"},
    {"code": "USA", "name": "United States"},
    {"code": "CHN", "name": "China"},
    {"code": "IND", "name": "India"},
    {"code": "JPN", "name": "Japan"},
    {"code": "DEU", "name": "Germany"},
    {"code": "GBR", "name": "United Kingdom"},
    {"code": "FRA", "name": "France"},
    {"code": "BRA", "name": "Brazil"},
    {"code": "ITA", "name": "Italy"},
    {"code": "CAN", "name": "Canada"},
    {"code": "KOR", "name": "South Korea"},
    {"code": "AUS", "name": "Australia"},
    {"code": "ESP", "name": "Spain"},
    {"code": "MEX", "name": "Mexico"},
    {"code": "IDN", "name": "Indonesia"},
    {"code": "NLD", "name": "Netherlands"},
    {"code": "SAU", "name": "Saudi Arabia"},
    {"code": "TUR", "name": "Türkiye"},
    {"code": "CHE", "name": "Switzerland"},
    {"code": "POL", "name": "Poland"},
    {"code": "SWE", "name": "Sweden"},
    {"code": "BEL", "name": "Belgium"},
    {"code": "ARE", "name": "United Arab Emirates"},
    {"code": "ARG", "name": "Argentina"},
    {"code": "ZAF", "name": "South Africa"},
    {"code": "EGY", "name": "Egypt"},
    {"code": "ISR", "name": "Israel"},
    {"code": "SGP", "name": "Singapore"},
    {"code": "NOR", "name": "Norway"},
]


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "AI Labor Market Simulation API", "version": app.version}


@app.get("/api/simulate/{scenario}")
def simulate(scenario: str, horizon: int = 20,
             adoption_speed: float = 1.0, country: str = "WLD", export: bool = False):
    if scenario not in {"slow", "moderate", "rapid"}:
        raise HTTPException(400, f"Invalid scenario '{scenario}'. Use slow|moderate|rapid.")
    try:
        results = run_scenario(scenario, horizon=horizon,
                               adoption_speed=adoption_speed, country=country)
        try:
            results["ml_forecast"] = forecast_unemployment(2025, 2025 + horizon - 1)
        except Exception:
            results["ml_forecast"] = None
        if export:
            results["csv_path"] = export_csv(results, f"simulation_{scenario}_{country}.csv")
        return results
    except Exception as e:
        raise HTTPException(500, f"Simulation error: {e}")


@app.get("/api/compare")
def compare(horizon: int = 20, adoption_speed: float = 1.0, country: str = "WLD"):
    try:
        return compare_scenarios(horizon=horizon, adoption_speed=adoption_speed, country=country)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/baseline")
def baseline(country: str = "WLD"):
    """Show the live-data baseline (employment, workforce, GDP, sector splits) for a country."""
    try:
        return get_country_baseline(country)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/countries")
def countries():
    """List of supported countries for the frontend dropdown."""
    return {"countries": COUNTRIES}


@app.get("/api/monte-carlo")
def monte_carlo_endpoint(n_simulations: int = 1000, horizon: int = 20):
    n_simulations = min(max(n_simulations, 100), 5000)
    try:
        return monte_carlo(n_simulations=n_simulations, horizon=horizon)
    except Exception as e:
        raise HTTPException(500, f"Monte Carlo error: {e}")


@app.get("/api/sensitivity")
def sensitivity_endpoint(scenario: str = "moderate", country: str = "WLD"):
    try:
        return sensitivity(scenario, country=country)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/validate")
def validate_endpoint():
    try:
        return validate(2000, 2020)
    except Exception as e:
        raise HTTPException(500, f"Validation error: {e}")


@app.post("/api/analyze")
def analyze(body: AnalyzeRequest = Body(...)):
    """Generate an Arabic economic advisory report from the simulation results.

    Three engines available:
      - "builtin" (default): deterministic Python report generator. No external
        service needed. Always works. Recommended for demos and presentations.
      - "groq":     real cloud LLM via Groq (free API, llama-3.3-70b).
                    Gives variable, contextual output each time.
                    Requires GROQ_API_KEY env var.
      - "ollama":   uses the locally-installed Ollama LLM.
                    Requires Ollama running on localhost:11434.

    Any LLM failure falls back to the built-in so the user never sees an empty
    response.
    """
    try:
        results = run_scenario(body.scenario, horizon=body.horizon,
                               adoption_speed=body.adoption_speed,
                               country=body.country or "WLD")
        engine = (body.engine or "builtin").lower()

        if engine == "groq":
            try:
                resp = analyze_with_groq(results, model=body.model)
                if resp.get("success"):
                    return resp
                # Key missing or API error → keep the error message so user knows
                return resp
            except Exception as e:
                fallback = generate_builtin_summary(results)
                fallback["model"] = fallback["model"] + f" (Groq error — fallback: {e})"
                return fallback

        if engine == "ollama":
            try:
                resp = analyze_with_local_llm(results, model=body.model)
                if resp.get("success"):
                    return resp
            except Exception:
                pass
            fallback = generate_builtin_summary(results)
            fallback["model"] = fallback["model"] + " (Ollama unavailable — fallback)"
            return fallback

        # Default: built-in
        return generate_builtin_summary(results)
    except Exception as e:
        raise HTTPException(500, f"Analysis error: {e}")


@app.get("/api/groq-models")
def groq_models():
    """List Groq models (if GROQ_API_KEY is set)."""
    return list_groq_models()


@app.get("/api/models")
def models():
    return list_available_models()


@app.get("/api/oxford-risk")
def oxford_risk():
    """Static automation-risk reference table for the AI Impact chart."""
    return OXFORD_RISK_DATA


@app.get("/api/oxford-full")
def oxford_full():
    """Curated subset of the Frey & Osborne (2013) 702-occupation dataset.

    Returns ~50 occupations spanning the full automation-probability range.
    Source: Appendix A of Frey, C. B., & Osborne, M. A. (2013). "The Future
    of Employment." Oxford Martin School.
    """
    csv_path = DATA_DIR / "frey_osborne.csv"
    occupations = []
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            occupations.append({
                "rank":        int(row["rank"]),
                "probability": float(row["probability"]),
                "soc_code":    row["soc_code"],
                "occupation":  row["occupation"],
            })
    return {
        "occupations": occupations,
        "count":       len(occupations),
        "source":      "Frey & Osborne 2013 — Appendix A (curated subset)",
        "full_dataset_note": "Full 702-row dataset is in the original paper's Appendix A.",
    }
