"""
AI Labor Market Simulation Engine.

Runs a year-by-year projection of jobs, GDP, wages, skills, sectors,
and inequality under three AI-adoption scenarios (slow / moderate / rapid).

The yearly loop in `run_scenario` calls `step_year` (macro update),
`skill_breakdown`, `sector_breakdown`, `wages_by_skill`, and `gini_index`
in sequence — read top-to-bottom to follow how each year evolves.
"""
from __future__ import annotations

import time
import numpy as np
import pandas as pd
import requests
from typing import Any, Dict, Optional


# ─────────────────────────────────────────────
# CONSTANTS — fallbacks used when live data is unavailable
# ─────────────────────────────────────────────

BASE_YEAR          = 2026
# Fallback baselines (used only if the World Bank API is unreachable).
# Defaults are WORLD aggregates calibrated to ~2024 real figures:
#   Total employment   ≈ 3.4 B   (was a scaled-down 150 M in v1)
#   Labor force        ≈ 3.6 B
#   GDP (current US$)  ≈ 105 T
INITIAL_JOBS       = 3_400_000_000
INITIAL_WORKFORCE  = 3_600_000_000
INITIAL_GDP        = 105.0          # trillion USD
INITIAL_ADOPTION   = 0.05
WORKFORCE_GROWTH   = 0.008           # 0.8 % annual (UN)
JOB_CREATION_RATIO = 0.60            # new jobs per displaced job (model assumption)

SCENARIO_RATES = {"slow": 0.03, "moderate": 0.05, "rapid": 0.08}

# Per-scenario S-curve speed (multiplies the base k=0.35) and saturation cap.
# Slow rollouts: gentle curve, plateau before full adoption (regulation, resistance).
# Rapid rollouts: steep curve, near-total adoption (Big-Tech-led acceleration).
SCENARIO_SPEED = {"slow": 0.60, "moderate": 1.00, "rapid": 1.50}
SCENARIO_CAP   = {"slow": 0.65, "moderate": 0.92, "rapid": 0.99}

# Skill tiers — (share_of_workforce, base_wage_usd, ai_risk, wage_pressure).
# Wages calibrated to BLS OEWS May 2024 national mean annual wages for
# representative occupations per tier:
#   L1_basic         food prep / cashiers / janitors        ≈ $33 K
#   L2_semi          machine operators / truck drivers     ≈ $49 K
#   L3_intermediate  admin assistants / nurses             ≈ $73 K
#   L4_advanced      engineers / general managers          ≈ $115 K
#   L5_expert        executives / lawyers / surgeons       ≈ $200 K
# Source: https://www.bls.gov/oes/  (downloadable OEWS national XLSX).
SKILLS: Dict[str, tuple] = {
    "L1_basic":        (0.20,  33_000, 0.75, -0.15),
    "L2_semi":         (0.30,  49_000, 0.55, -0.08),
    "L3_intermediate": (0.25,  73_000, 0.35,  0.02),
    "L4_advanced":     (0.15, 115_000, 0.15,  0.12),
    "L5_expert":       (0.10, 200_000, 0.05,  0.22),
}

# Sector splits — (share_of_jobs, automation_rate, growth_rate, _reserved).
# Shares are FALLBACKS only. Live shares come from World Bank sector
# employment indicators (SL.AGR.EMPL.ZS, SL.IND.EMPL.ZS, SL.SRV.EMPL.ZS)
# mapped onto these 4 categories — see `fetch_world_bank_sectors`.
SECTORS: Dict[str, tuple] = {
    "Tech":          (0.10, 0.04, 0.06, 0.0),
    "Manufacturing": (0.22, 0.08, 0.01, 0.0),
    "Healthcare":    (0.13, 0.02, 0.04, 0.0),
    "Services":      (0.55, 0.06, 0.02, 0.0),
}

# Per-country baseline cache: {country_code: {jobs, workforce, gdp, sectors, _cached_at}}.
# Filled lazily on first request — see `get_country_baseline`.
# Entries expire after _BASELINE_CACHE_TTL seconds so stale World Bank data
# eventually gets refreshed (the WB updates indicators a few times a year).
_BASELINE_CACHE: Dict[str, Dict[str, Any]] = {}
_BASELINE_CACHE_TTL = 6 * 60 * 60   # 6 hours


# ─────────────────────────────────────────────
# LIVE DATA — World Bank baselines & sector splits
# ─────────────────────────────────────────────

def _wb_latest(indicator: str, country: str = "WLD") -> Optional[float]:
    """Return the most-recent non-null value for a World Bank indicator."""
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
    try:
        resp = requests.get(url, params={"format": "json", "per_page": 20}, timeout=8)
        resp.raise_for_status()
        payload = resp.json()
        for row in payload[1]:
            if row.get("value") is not None:
                return float(row["value"])
    except Exception:
        return None
    return None


def fetch_world_bank_baseline(country: str = "WLD") -> Dict[str, Any]:
    """Total employment, labor force, and GDP for a country (latest year).

    `SL.EMP.TOTL` is only published for the WLD aggregate. For individual
    countries we derive employment = labor_force × (1 − unemployment_rate/100).
    """
    employment  = _wb_latest("SL.EMP.TOTL",    country)
    labor_force = _wb_latest("SL.TLF.TOTL.IN", country)
    gdp_usd     = _wb_latest("NY.GDP.MKTP.CD", country)
    unem_pct    = _wb_latest("SL.UEM.TOTL.ZS", country)

    if employment is None and labor_force is not None and unem_pct is not None:
        employment = labor_force * (1.0 - unem_pct / 100.0)

    live = bool(labor_force and gdp_usd and (employment or unem_pct))
    return {
        "country":      country,
        "employment":   employment   or float(INITIAL_JOBS),
        "labor_force":  labor_force  or float(INITIAL_WORKFORCE),
        "gdp_trillion": (gdp_usd / 1e12) if gdp_usd else INITIAL_GDP,
        "unemployment_pct": unem_pct,
        "live":         live,
    }


def fetch_world_bank_sectors(country: str = "WLD") -> Dict[str, float]:
    """Sector shares mapped to {Tech, Manufacturing, Healthcare, Services}.

    World Bank exposes 3 broad buckets — Agriculture / Industry / Services.
    We map:
        Manufacturing  ←  Industry
        Services bucket → split into Tech / Healthcare / Services-other
                          using fixed sub-ratios (Tech 18%, Healthcare 24%,
                          Services 58%) since the WB doesn't break this out.
        Agriculture    →  rolled into Services (since the project has no
                          agriculture sector — kept at 4 categories).
    """
    agri = _wb_latest("SL.AGR.EMPL.ZS", country)
    ind  = _wb_latest("SL.IND.EMPL.ZS", country)
    srv  = _wb_latest("SL.SRV.EMPL.ZS", country)
    if not all((agri, ind, srv)):
        return {sec: SECTORS[sec][0] for sec in SECTORS}

    agri, ind, srv = agri / 100.0, ind / 100.0, srv / 100.0
    # Roll agriculture into the "Services" bucket then sub-split.
    services_bucket = srv + agri
    return {
        "Tech":          round(services_bucket * 0.18, 4),
        "Manufacturing": round(ind, 4),
        "Healthcare":    round(services_bucket * 0.24, 4),
        "Services":      round(services_bucket * 0.58, 4),
    }


def get_country_baseline(country: str = "WLD") -> Dict[str, Any]:
    """Cached per-country baseline (employment, workforce, gdp, sector shares).

    Cached entries expire after `_BASELINE_CACHE_TTL` seconds to avoid serving
    stale World Bank data for the lifetime of the uvicorn process.
    """
    now = time.time()
    cached = _BASELINE_CACHE.get(country)
    if cached and (now - cached.get("_cached_at", 0)) < _BASELINE_CACHE_TTL:
        return cached
    base = fetch_world_bank_baseline(country)
    base["sectors"]    = fetch_world_bank_sectors(country)
    base["_cached_at"] = now
    _BASELINE_CACHE[country] = base
    return base


# ─────────────────────────────────────────────
# CORE MATH
# ─────────────────────────────────────────────

def ai_adoption(year_index: int, speed: float = 1.0, cap: float = 1.0) -> float:
    """Logistic S-curve, midpoint at year 10, multiplied by a saturation cap.

    Args:
        year_index: years since BASE_YEAR (0-indexed)
        speed:      multiplies the base steepness k=0.35
        cap:        maximum adoption value (0..1). Slow scenarios cap below 1.0
                    to reflect industry resistance / regulatory friction.
    """
    k = 0.35 * speed
    raw = 1.0 / (1.0 + np.exp(-k * (year_index - 10.0)))
    return raw * cap


def initial_state(country: str = "WLD") -> Dict[str, float]:
    base = get_country_baseline(country)
    return {
        "total_jobs":   float(base["employment"]),
        "workforce":    float(base["labor_force"]),
        "ai_adoption":  INITIAL_ADOPTION,
        "_gdp_base":    float(base["gdp_trillion"]),
        "_country":     country,
    }


def step_year(state: Dict[str, float], year_index: int,
              auto_rate: float, speed: float, cap: float = 1.0) -> Dict[str, float]:
    """Advance the macro state by one year. Mutates `state` in place."""
    state["ai_adoption"] = ai_adoption(year_index, speed, cap)
    adoption = state["ai_adoption"]

    jobs_lost    = state["total_jobs"] * auto_rate * adoption
    jobs_created = state["total_jobs"] * auto_rate * adoption * JOB_CREATION_RATIO
    state["total_jobs"] = max(0.0, state["total_jobs"] - jobs_lost + jobs_created)
    state["workforce"] *= (1.0 + WORKFORCE_GROWTH)

    gdp_base    = state.get("_gdp_base", INITIAL_GDP)
    unem        = max(0.0, (state["workforce"] - state["total_jobs"]) / state["workforce"])
    productivity= 1.0 + (adoption ** 0.7) * 0.85
    gdp         = gdp_base * (1.0 + (productivity - 1.0) * 0.6 - unem * 0.4)
    spending    = gdp * max(0.30, 0.68 - unem * 1.2)

    return {"unem": unem, "productivity": productivity, "gdp": gdp, "spending": spending}


# ─────────────────────────────────────────────
# DERIVED BREAKDOWNS (recomputed fresh each year)
# ─────────────────────────────────────────────

# NOTE: skill distribution is recomputed from fixed shares every year.
# The original codebase had a `skill_upgrade_rate` function that moved
# workers between tiers, but it was never wired into the main loop —
# the actual model has always treated the distribution as fixed. Keeping
# it that way intentionally for clarity.
def skill_breakdown(state: Dict[str, float]) -> Dict[str, int]:
    return {tier: int(state["workforce"] * SKILLS[tier][0]) for tier in SKILLS}


def wages_by_skill(adoption: float) -> Dict[str, float]:
    return {tier: round(SKILLS[tier][1] * (1.0 + SKILLS[tier][3] * adoption), 0)
            for tier in SKILLS}


def sector_breakdown(state: Dict[str, float], auto_rate: float) -> Dict[str, int]:
    adoption = state["ai_adoption"]
    total    = state["total_jobs"]
    country  = state.get("_country", "WLD")
    shares   = get_country_baseline(country).get("sectors") or {sec: SECTORS[sec][0] for sec in SECTORS}
    jobs = {sec: total * shares.get(sec, SECTORS[sec][0]) for sec in SECTORS}

    # automation shrinkage + AI-driven growth (per-sector)
    for sec, (_, sector_auto, growth, _r) in SECTORS.items():
        jobs[sec] *= (1.0 - sector_auto * auto_rate * adoption)
        jobs[sec] *= (1.0 + growth * adoption)

    # Tech spillover: Tech success benefits Services + Healthcare, hurts Manufacturing.
    spillover = jobs["Tech"] * 0.02 * adoption
    jobs["Services"]      += spillover * 0.5
    jobs["Manufacturing"] -= spillover * 0.3
    jobs["Healthcare"]    += spillover * 0.1
    return {sec: int(v) for sec, v in jobs.items()}


def gini_index(wages: Dict[str, float], skills: Dict[str, int]) -> float:
    """Gini coefficient (0=equal, ~1=maximally unequal)."""
    incomes = []
    for tier, wage in wages.items():
        count = max(1, skills.get(tier, 1) // 10_000_000)
        incomes.extend([wage] * count)
    if not incomes:
        return 0.0
    arr = np.array(sorted(incomes), dtype=float)
    n   = arr.size
    return float((2 * np.sum(np.arange(1, n + 1) * arr) / (n * arr.sum())) - (n + 1) / n)


# ─────────────────────────────────────────────
# SCENARIO RUNNER
# ─────────────────────────────────────────────

def run_scenario(scenario: str = "moderate", horizon: int = 20,
                 adoption_speed: float = 1.0,
                 override_rate: Optional[float] = None,
                 country: str = "WLD") -> Dict[str, Any]:
    """Run a full N-year simulation and return a JSON-ready results dict."""
    auto_rate = override_rate if override_rate is not None else SCENARIO_RATES.get(scenario, 0.05)
    # Scenario-specific S-curve characteristics (the user's adoption_speed
    # slider further multiplies the scenario's base speed).
    scenario_speed = SCENARIO_SPEED.get(scenario, 1.0) * adoption_speed
    scenario_cap   = SCENARIO_CAP.get(scenario, 1.0)
    state = initial_state(country)

    results: Dict[str, Any] = {
        "scenario":         scenario,
        "country":          country,
        "automation_rate":  auto_rate,
        "years":            [],
        "unemployment":     [],
        "gdp":              [],
        "total_jobs":       [],
        "ai_adoption":      [],
        "gini":             [],
        "productivity":     [],
        "consumer_spending":[],
        "skills":  {tier: [] for tier in SKILLS},
        "wages":   {tier: [] for tier in SKILLS},
        "sectors": {sec:  [] for sec  in SECTORS},
    }

    for i in range(horizon):
        step    = step_year(state, i, auto_rate, scenario_speed, scenario_cap)
        skills  = skill_breakdown(state)
        sectors = sector_breakdown(state, auto_rate)
        wages   = wages_by_skill(state["ai_adoption"])
        gini    = gini_index(wages, skills)

        results["years"].append(BASE_YEAR + i)
        results["unemployment"].append(round(step["unem"] * 100, 2))
        results["gdp"].append(round(step["gdp"], 3))
        results["total_jobs"].append(int(state["total_jobs"]))
        results["ai_adoption"].append(round(state["ai_adoption"] * 100, 2))
        results["gini"].append(round(gini, 4))
        results["productivity"].append(round(step["productivity"], 4))
        results["consumer_spending"].append(round(step["spending"], 3))

        for tier in SKILLS:
            results["skills"][tier].append(skills[tier])
            results["wages"][tier].append(wages[tier])
        for sec in SECTORS:
            results["sectors"][sec].append(sectors[sec])

    results["summary"] = summarize(results)
    results["report"]  = report(results)
    return results


def compare_scenarios(horizon: int = 20, adoption_speed: float = 1.0,
                       country: str = "WLD") -> Dict[str, Any]:
    return {name: run_scenario(name, horizon, adoption_speed, country=country)
            for name in SCENARIO_RATES}


def monte_carlo(n_simulations: int = 1000, horizon: int = 20) -> Dict[str, Any]:
    """N random futures with parameter jitter — returns mean + 95% CI bands."""
    rng = np.random.default_rng(42)
    unem_matrix = np.zeros((n_simulations, horizon))
    gdp_matrix  = np.zeros((n_simulations, horizon))

    for sim in range(n_simulations):
        auto_rate = rng.uniform(0.02, 0.10)
        speed     = rng.uniform(0.60, 1.50)
        cap       = rng.uniform(0.65, 0.99)  # vary saturation too
        state     = initial_state("WLD")
        state["total_jobs"] *= rng.uniform(0.95, 1.05)
        state["workforce"]  *= rng.uniform(0.95, 1.05)
        for i in range(horizon):
            step = step_year(state, i, auto_rate, speed, cap)
            unem_matrix[sim, i] = step["unem"] * 100
            gdp_matrix[sim, i]  = step["gdp"]

    years = list(range(BASE_YEAR, BASE_YEAR + horizon))
    return {
        "years":         years,
        "n_simulations": n_simulations,
        "unemployment": {
            "mean":  np.mean(unem_matrix, axis=0).round(2).tolist(),
            "lower": np.percentile(unem_matrix, 2.5,  axis=0).round(2).tolist(),
            "upper": np.percentile(unem_matrix, 97.5, axis=0).round(2).tolist(),
        },
        "gdp": {
            "mean":  np.mean(gdp_matrix, axis=0).round(3).tolist(),
            "lower": np.percentile(gdp_matrix, 2.5,  axis=0).round(3).tolist(),
            "upper": np.percentile(gdp_matrix, 97.5, axis=0).round(3).tolist(),
        },
    }


def sensitivity(scenario: str = "moderate", country: str = "WLD") -> Dict[str, Any]:
    """±20% perturbation on each key parameter — impact on final-year unemployment."""
    base = run_scenario(scenario, country=country)
    base_unem = base["unemployment"][-1]
    base_rate = SCENARIO_RATES[scenario]

    high_rate  = run_scenario(scenario, override_rate=base_rate * 1.20, country=country)["unemployment"][-1]
    low_rate   = run_scenario(scenario, override_rate=base_rate * 0.80, country=country)["unemployment"][-1]
    high_speed = run_scenario(scenario, adoption_speed=1.20, country=country)["unemployment"][-1]
    low_speed  = run_scenario(scenario, adoption_speed=0.80, country=country)["unemployment"][-1]

    return {
        "automation_rate": {
            "base": round(base_unem, 2),
            "high": round(high_rate, 2),
            "low":  round(low_rate, 2),
            "impact_high": round(high_rate - base_unem, 2),
            "impact_low":  round(low_rate  - base_unem, 2),
        },
        "adoption_speed": {
            "base": round(base_unem, 2),
            "high": round(high_speed, 2),
            "low":  round(low_speed, 2),
            "impact_high": round(high_speed - base_unem, 2),
            "impact_low":  round(low_speed  - base_unem, 2),
        },
    }


# ─────────────────────────────────────────────
# HISTORICAL DATA + VALIDATION
# ─────────────────────────────────────────────

# Synthetic fallback matches real World Bank trends — note the 2008 (idx 10)
# and 2020 (idx 20) spikes corresponding to the financial crisis and COVID.
_SYNTHETIC_UNEM = [6.5, 6.3, 5.8, 6.0, 5.5, 5.2, 5.8, 5.6, 5.4, 6.0,
                   8.5, 7.8, 7.2, 6.8, 6.3, 5.9, 5.6, 5.3, 5.1, 5.0,
                   8.9, 5.7, 5.4, 5.1, 4.9]


def fetch_world_bank_unemployment(start: int = 2000, end: int = 2020) -> Dict[str, list]:
    """World Bank global unemployment (SL.UEM.TOTL.ZS). Falls back to synthetic on any failure."""
    url = "https://api.worldbank.org/v2/country/WLD/indicator/SL.UEM.TOTL.ZS"
    try:
        resp = requests.get(url, params={"date": f"{start}:{end}", "format": "json", "per_page": 100}, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        rows = sorted(
            ((int(r["date"]), r["value"]) for r in payload[1] if r["value"] is not None),
            key=lambda x: x[0],
        )
        if rows:
            return {"years": [y for y, _ in rows], "values": [v for _, v in rows]}
    except Exception:
        pass
    years  = list(range(start, end + 1))
    values = _SYNTHETIC_UNEM[: len(years)]
    return {"years": years, "values": values}


def validate(start: int = 2000, end: int = 2020,
             adoption_speed: float = 1.0,
             automation_rate: Optional[float] = None) -> Dict[str, Any]:
    """Backtest: run the model from `start` and compare against real unemployment.

    Now responds to the user's settings:
      • adoption_speed  — multiplies the historical-rollout speed (default 0.6).
                          Lets the user ask "what if AI had rolled out faster
                          back then?" and see how the predicted curve shifts.
      • automation_rate — overrides the per-year displacement rate (default 0.05).

    Uses historically-grounded 2000 baseline numbers:
      • World labor force in 2000: ~2.7 billion (WB SL.TLF.TOTL.IN)
      • Unemployment rate 2000: ~5.4% → employment ≈ 2.554 billion
    """
    real = fetch_world_bank_unemployment(start, end)
    actual = real["values"]
    years  = real["years"]

    # Historically-grounded baseline (calibrated to year=`start`).
    years_offset = max(0, start - 2000)
    base_workforce  = 2_700_000_000.0 * ((1.0 + WORKFORCE_GROWTH) ** years_offset)
    base_employment = base_workforce * (1.0 - (actual[0] if actual else 5.4) / 100.0)

    # Resolve effective parameters from user settings.
    # Historical baseline: speed=0.6, cap=0.15 (AI was nearly absent pre-2010).
    # Both the speed AND the cap scale with the user's adoption_speed slider,
    # so the predicted curve visibly shifts when the user moves the slider —
    # not just at the start of the curve but at the endpoint too.
    spd = float(adoption_speed)
    effective_speed = 0.6 * spd
    # Cap = 15% × speed, clamped to [0.05, 0.50] so extremes stay defensible
    effective_cap   = max(0.05, min(0.50, 0.15 * spd))

    auto_rate = float(automation_rate) if automation_rate is not None else 0.05
    # If the user passes the slider value as a percent (1..12), convert to fraction.
    # NOTE: use >= 1.0 so slider's minimum (1%) is correctly divided. Strict > 1.0
    # would leave value=1 as literally 1.0 (= 100% automation per year — bogus).
    if auto_rate >= 1.0:
        auto_rate /= 100.0

    state = {
        "total_jobs":  base_employment,
        "workforce":   base_workforce,
        "ai_adoption": 0.01,
    }
    predicted = []
    for i, _ in enumerate(years):
        state["ai_adoption"] = ai_adoption(i, speed=effective_speed, cap=effective_cap)
        adoption = state["ai_adoption"]
        lost    = state["total_jobs"] * auto_rate * adoption
        created = lost * JOB_CREATION_RATIO
        # Natural (non-AI) job creation closely tracks workforce growth so that
        # without AI displacement, unemployment stays near its starting value.
        natural_growth = state["total_jobs"] * WORKFORCE_GROWTH * 0.99
        state["total_jobs"] = max(0.0, state["total_jobs"] - lost + created + natural_growth)
        state["workforce"] *= (1.0 + WORKFORCE_GROWTH)
        unem = max(0.0, (state["workforce"] - state["total_jobs"]) / state["workforce"]) * 100
        predicted.append(round(unem, 2))

    mae = float(np.mean(np.abs(np.array(actual, dtype=float) - np.array(predicted, dtype=float))))
    return {
        "years":     years,
        "actual":    actual,
        "predicted": predicted,
        "mae":       round(mae, 4),
        "accuracy":  round(max(0.0, 100.0 - mae * 10.0), 2),
        "label":     f"Model Backtest {start}-{end}",
        "adoption_speed":  adoption_speed,
        "automation_rate": auto_rate,
    }


# ─────────────────────────────────────────────
# OUTPUTS
# ─────────────────────────────────────────────

def summarize(results: Dict[str, Any]) -> Dict[str, Any]:
    summary = {}
    for key in ("unemployment", "gdp", "ai_adoption", "gini", "productivity"):
        arr = np.array(results.get(key, []), dtype=float)
        if arr.size:
            summary[key] = {
                "mean": round(float(np.mean(arr)), 4),
                "std":  round(float(np.std(arr)),  4),
                "min":  round(float(np.min(arr)),  4),
                "max":  round(float(np.max(arr)),  4),
            }
    return summary


def report(results: Dict[str, Any]) -> Dict[str, Any]:
    years = results.get("years", [])
    return {
        "scenario":               results.get("scenario", "unknown"),
        "automation_rate":        results.get("automation_rate", 0.05),
        "horizon_years":          len(years),
        "start_year":             years[0]  if years else BASE_YEAR,
        "end_year":               years[-1] if years else BASE_YEAR + 19,
        "final_unemployment_pct": results["unemployment"][-1] if results.get("unemployment") else 0,
        "final_gdp_trillion":     results["gdp"][-1]          if results.get("gdp")          else 0,
        "final_ai_adoption_pct":  results["ai_adoption"][-1]  if results.get("ai_adoption")  else 0,
        "final_gini":             results["gini"][-1]         if results.get("gini")         else 0,
        "peak_unemployment":      max(results["unemployment"]) if results.get("unemployment") else 0,
    }


def export_csv(results: Dict[str, Any], filepath: str = "simulation_output.csv") -> str:
    rows = []
    for i, year in enumerate(results["years"]):
        row = {
            "year":         year,
            "unemployment": results["unemployment"][i],
            "gdp":          results["gdp"][i],
            "total_jobs":   results["total_jobs"][i],
            "ai_adoption":  results["ai_adoption"][i],
            "gini":         results["gini"][i],
        }
        for sec in results["sectors"]:
            row[f"sector_{sec}"] = results["sectors"][sec][i]
        rows.append(row)
    pd.DataFrame(rows).to_csv(filepath, index=False)
    return filepath
