"""
RandomForest unemployment forecaster.

Trains on World Bank global unemployment (2000–2024) and projects forward
year-by-year using its own predictions as autoregressive inputs.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler

from backend.simulation import fetch_world_bank_unemployment


FEATURE_COLS = ["trend", "lag1", "lag2", "lag3", "rolling3", "ai_proxy"]


def _build_features(years: list, values: list) -> pd.DataFrame:
    df = pd.DataFrame({"year": years, "unemployment_rate": values}).sort_values("year").reset_index(drop=True)
    df["lag1"]     = df["unemployment_rate"].shift(1)
    df["lag2"]     = df["unemployment_rate"].shift(2)
    df["lag3"]     = df["unemployment_rate"].shift(3)
    df["trend"]    = df["year"] - df["year"].min()
    df["rolling3"] = df["unemployment_rate"].rolling(3).mean()
    df["ai_proxy"] = df["year"].apply(lambda y: max(0.0, (y - 2015) ** 2 / 100.0))
    return df.dropna().reset_index(drop=True)


def train() -> Dict[str, Any]:
    """Train RandomForest with proper time-series train/test split.

    The previous version measured MAE on the same data the model was trained on
    (in-sample), which is overfitting and gives misleadingly low error. Now we
    hold out the last 5 years (~20% of the 25-year series) as a TEST set and
    report MAE on that. The final model is retrained on the full series so that
    forecasts use all available history.
    """
    raw = fetch_world_bank_unemployment(2000, 2024)
    df  = _build_features(raw["years"], raw["values"])

    X = df[FEATURE_COLS].values
    y = df["unemployment_rate"].values

    # Time-series split: last 5 rows = held-out test set.
    n = len(df)
    split = max(1, n - 5)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Fit scaler on train only, then transform both.
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test) if len(X_test) else X_train_s[:0]

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_s, y_train)

    # Honest out-of-sample MAE on held-out years
    if len(X_test):
        mae_test = mean_absolute_error(y_test, model.predict(X_test_s))
    else:
        mae_test = mean_absolute_error(y_train, model.predict(X_train_s))

    # Retrain on full series so forecasts use every available data point
    X_all_s = scaler.fit_transform(X)
    model.fit(X_all_s, y)

    return {
        "model":     model,
        "scaler":    scaler,
        "mae":       round(float(mae_test), 4),  # honest, held-out MAE
        "accuracy":  round(max(0.0, 100.0 - mae_test * 10.0), 2),
        "base_year": int(df["year"].min()),
        "test_years": int(len(X_test)),  # how many years were held out
        "train_years": int(len(X_train)),
    }


def forecast_unemployment(start: int = 2025, end: int = 2044) -> Dict[str, Any]:
    """Forecast unemployment for [start, end] inclusive."""
    trained = train()
    model, scaler = trained["model"], trained["scaler"]

    raw = fetch_world_bank_unemployment(2000, 2024)
    history = list(raw["values"][-5:])
    base_year = trained["base_year"]

    years     = list(range(start, end + 1))
    predicted = []
    for year in years:
        lag1     = history[-1] if len(history) >= 1 else 5.0
        lag2     = history[-2] if len(history) >= 2 else 5.0
        lag3     = history[-3] if len(history) >= 3 else 5.0
        rolling3 = float(np.mean(history[-3:])) if len(history) >= 3 else lag1
        feats = np.array([[year - base_year, lag1, lag2, lag3, rolling3,
                            max(0.0, (year - 2015) ** 2 / 100.0)]])
        pred = float(model.predict(scaler.transform(feats))[0])
        pred = round(max(0.0, pred), 3)
        predicted.append(pred)
        history.append(pred)

    importances = {col: round(float(v), 4)
                   for col, v in zip(FEATURE_COLS, model.feature_importances_)}
    return {
        "years":                  years,
        "predicted_unemployment": predicted,
        "model_accuracy":         trained["accuracy"],
        "model_mae":              trained["mae"],
        "feature_importances":    importances,
    }
