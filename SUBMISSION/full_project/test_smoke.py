"""
Smoke test for the clean rebuild — hits every endpoint and asserts shape.
Run AFTER starting the server with:
    python -m uvicorn backend.app:app --port 8000
"""
import sys
import json
import requests

BASE = "http://localhost:8000"


def check(name: str, condition: bool, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}{(' — ' + detail) if detail else ''}")
    return condition


def test_simulate() -> bool:
    print("/api/simulate/moderate")
    r = requests.get(f"{BASE}/api/simulate/moderate?horizon=10").json()
    ok = True
    required = ["scenario", "automation_rate", "years", "unemployment", "gdp",
                "total_jobs", "ai_adoption", "gini", "productivity",
                "consumer_spending", "skills", "wages", "sectors", "summary",
                "report", "ml_forecast"]
    ok &= check("all required keys present",
                all(k in r for k in required),
                f"missing: {[k for k in required if k not in r]}")
    ok &= check("years has 10 entries", len(r["years"]) == 10)
    ok &= check("unemployment is percentage (>1)", r["unemployment"][0] > 1)
    ok &= check("5 skill tiers", sorted(r["skills"].keys()) == sorted(
        ["L1_basic", "L2_semi", "L3_intermediate", "L4_advanced", "L5_expert"]))
    ok &= check("4 sectors", sorted(r["sectors"].keys()) == sorted(
        ["Tech", "Manufacturing", "Healthcare", "Services"]))
    ok &= check("report has final_unemployment_pct",
                "final_unemployment_pct" in r["report"])
    return ok


def test_compare() -> bool:
    print("/api/compare")
    r = requests.get(f"{BASE}/api/compare?horizon=5").json()
    return all([
        check("has slow/moderate/rapid", set(r.keys()) == {"slow", "moderate", "rapid"}),
        check("each scenario has years array", all("years" in r[s] for s in r)),
    ])


def test_monte_carlo() -> bool:
    print("/api/monte-carlo")
    r = requests.get(f"{BASE}/api/monte-carlo?n_simulations=100&horizon=5").json()
    return all([
        check("has unemployment + gdp", "unemployment" in r and "gdp" in r),
        check("has mean/lower/upper",
              set(r["unemployment"].keys()) == {"mean", "lower", "upper"}),
        check("arrays match horizon", len(r["unemployment"]["mean"]) == 5),
    ])


def test_sensitivity() -> bool:
    print("/api/sensitivity")
    r = requests.get(f"{BASE}/api/sensitivity").json()
    return all([
        check("has both parameters",
              set(r.keys()) == {"automation_rate", "adoption_speed"}),
        check("automation_rate has all fields",
              set(r["automation_rate"].keys()) == {"base", "high", "low", "impact_high", "impact_low"}),
    ])


def test_validate() -> bool:
    print("/api/validate")
    r = requests.get(f"{BASE}/api/validate").json()
    return all([
        check("has years/actual/predicted/mae/accuracy",
              {"years", "actual", "predicted", "mae", "accuracy"}.issubset(r.keys())),
        check("accuracy is numeric", isinstance(r["accuracy"], (int, float))),
    ])


def test_models() -> bool:
    print("/api/models")
    r = requests.get(f"{BASE}/api/models").json()
    return check("has 'available' key", "available" in r,
                 f"Ollama {'reachable' if r.get('available') else 'unreachable (OK)'}")


def test_oxford() -> bool:
    print("/api/oxford-risk")
    r = requests.get(f"{BASE}/api/oxford-risk").json()
    return all([
        check("has jobs/risk/source", {"jobs", "risk", "source"}.issubset(r.keys())),
        check("10 jobs, 10 risks", len(r["jobs"]) == 10 and len(r["risk"]) == 10),
    ])


def test_oxford_full() -> bool:
    print("/api/oxford-full")
    r = requests.get(f"{BASE}/api/oxford-full").json()
    return all([
        check("has occupations/count/source", {"occupations", "count", "source"}.issubset(r.keys())),
        check("≥ 40 occupations", r["count"] >= 40),
        check("spans full probability range",
              min(o["probability"] for o in r["occupations"]) < 0.05
              and max(o["probability"] for o in r["occupations"]) > 0.95),
    ])


def test_baseline() -> bool:
    print("/api/baseline?country=WLD")
    r = requests.get(f"{BASE}/api/baseline").json()
    return all([
        check("has employment/labor_force/gdp_trillion/sectors",
              {"employment", "labor_force", "gdp_trillion", "sectors"}.issubset(r.keys())),
        check("live flag present", "live" in r),
        check("4 sectors mapped", len(r["sectors"]) == 4),
    ])


def test_countries() -> bool:
    print("/api/countries")
    r = requests.get(f"{BASE}/api/countries").json()
    return all([
        check("has countries list", "countries" in r and isinstance(r["countries"], list)),
        check("≥ 25 countries", len(r["countries"]) >= 25),
        check("WLD present", any(c["code"] == "WLD" for c in r["countries"])),
    ])


def test_country_specific() -> bool:
    print("/api/simulate/moderate?country=USA")
    r = requests.get(f"{BASE}/api/simulate/moderate?horizon=5&country=USA").json()
    return all([
        check("country='USA' echoed back", r.get("country") == "USA"),
        check("starting jobs differ from WLD", r["total_jobs"][0] < 1_000_000_000),
    ])


if __name__ == "__main__":
    try:
        requests.get(BASE, timeout=2).raise_for_status()
    except Exception:
        print(f"Server not reachable at {BASE} — start it first:")
        print("  python -m uvicorn backend.app:app --port 8000")
        sys.exit(1)

    tests = [test_simulate, test_compare, test_monte_carlo,
             test_sensitivity, test_validate, test_models, test_oxford,
             test_oxford_full, test_baseline, test_countries, test_country_specific]
    results = [t() for t in tests]
    passed = sum(results)
    total  = len(results)
    print()
    print(f"=== {passed}/{total} endpoint groups passed ===")
    sys.exit(0 if passed == total else 1)
