# backend/app/services/forecast.py
from __future__ import annotations
from typing import Dict, Literal
import pandas as pd
import numpy as np

Method = Literal["exp_smooth", "seasonal_ma"]


def _to_series(history: Dict[str, float]) -> pd.Series:
    """
    history keys should be YYYY-MM
    """
    if not history:
        return pd.Series(dtype=float)

    s = pd.Series({k: float(v) for k, v in history.items()}, dtype=float)
    # Parse YYYY-MM safely into month-start dates
    s.index = pd.to_datetime([f"{k}-01" for k in s.index])
    s = s.sort_index()
    return s


def exp_smoothing_forecast(history: Dict[str, float], horizon: int, alpha: float = 0.35) -> Dict:
    s = _to_series(history)
    if len(s) == 0:
        return {"method": "exp_smooth", "params": {"alpha": alpha}, "fitted": {}, "forecast": {}}

    fitted_vals = []
    level = float(s.iloc[0])

    for x in s:
        level = alpha * float(x) + (1 - alpha) * level
        fitted_vals.append(level)

    fitted_series = pd.Series(fitted_vals, index=s.index)

    future_idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    fc = pd.Series([level] * horizon, index=future_idx)

    return {
        "method": "exp_smooth",
        "params": {"alpha": alpha},
        "fitted": {d.strftime("%Y-%m"): round(float(v), 2) for d, v in fitted_series.items()},
        "forecast": {d.strftime("%Y-%m"): round(float(v), 2) for d, v in fc.items()},
    }


def seasonal_moving_average(history: Dict[str, float], horizon: int, season: int = 12) -> Dict:
    s = _to_series(history)
    if len(s) == 0:
        return {"method": "seasonal_ma", "params": {"season": season}, "fitted": {}, "forecast": {}}

    # Fallback if not enough history
    if len(s) < season:
        mean = float(s.mean()) if len(s) else 0.0
        future_idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
        fc = pd.Series([mean] * horizon, index=future_idx)

        return {
            "method": "seasonal_ma",
            "params": {"season": season},
            "fitted": {},
            "forecast": {d.strftime("%Y-%m"): round(float(v), 2) for d, v in fc.items()},
        }

    df = s.to_frame("y")
    df["k"] = np.arange(len(df)) % season
    seasonal_avg = df.groupby("k")["y"].mean()

    future_idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    start_k = len(s) % season

    fvals = []
    for i in range(horizon):
      k = (start_k + i) % season
      fvals.append(float(seasonal_avg.loc[k]))

    fc = pd.Series(fvals, index=future_idx)

    return {
        "method": "seasonal_ma",
        "params": {"season": season},
        "fitted": {},
        "forecast": {d.strftime("%Y-%m"): round(float(v), 2) for d, v in fc.items()},
    }


def forecast_revenue(
    history: Dict[str, float],
    horizon: int = 12,
    method: Method = "exp_smooth",
    **kwargs
) -> Dict:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    if method == "exp_smooth":
        alpha = float(kwargs.get("alpha", 0.35))
        return exp_smoothing_forecast(history, horizon, alpha=alpha)

    season = int(kwargs.get("season", 12))
    return seasonal_moving_average(history, horizon, season=season)
