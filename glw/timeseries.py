"""Turn yearly lake areas into a forecast and a watch list.

Forecast rule from the brief: train on earlier years, test on later years,
never shuffle years, and compare with persistence ("next year = this year").
"""
import numpy as np


def _fit_line(years, areas):
    if len(years) < 2:
        return 0.0, areas[-1] if len(areas) else np.nan
    slope, intercept = np.polyfit(years, areas, 1)
    return float(slope), float(intercept)


def forecast_one(years, areas, target_year):
    """Three forecasts for target_year using ONLY years before it."""
    yrs = np.array([y for y in years if y < target_year])
    ars = np.array([a for y, a in zip(years, areas) if y < target_year])
    if len(yrs) == 0:
        return None
    persistence = float(ars[-1])
    slope, intercept = _fit_line(yrs, ars)
    trend = max(slope * target_year + intercept, 0.0)
    damped = 0.5 * (persistence + trend)
    return dict(persistence=persistence, trend=trend, damped=damped, n_past=len(yrs))


def backtest(series, test_years, min_past=3):
    """series: {zone_id: [(year, area_ha), ...]} of reliable years only."""
    rows = []
    for zid, pts in series.items():
        years = [p[0] for p in pts]
        areas = [p[1] for p in pts]
        for t in test_years:
            if t not in years:
                continue
            f = forecast_one(years, areas, t)
            if f is None or f["n_past"] < min_past:
                continue
            actual = areas[years.index(t)]
            rows.append(dict(zone=zid, year=t, actual=actual, **f))
    return rows


def mae(rows, key):
    if not rows:
        return float("nan")
    return float(np.mean([abs(r[key] - r["actual"]) for r in rows]))


def watch_list(series, zones_by_id, next_year):
    rows = []
    for zid, pts in series.items():
        if len(pts) < 3:
            continue
        years = np.array([p[0] for p in pts]); areas = np.array([p[1] for p in pts])
        slope, _ = _fit_line(years, areas)
        latest_year, latest = int(years[-1]), float(areas[-1])
        first = float(areas[0])
        f = forecast_one(list(years), list(areas), next_year)
        z = zones_by_id[zid]
        rows.append(dict(zone=zid, name=z["name"], country=z["country"], downstream=z["downstream"],
                         first_year=int(years[0]), first_area_ha=first,
                         latest_year=latest_year, latest_area_ha=latest,
                         growth_ha_per_year=slope,
                         growth_pct_per_year=100 * slope / max(np.mean(areas), 1e-6),
                         forecast_next_ha=f["damped"] if f else np.nan,
                         sudden_drop=bool(np.any(np.diff(areas) < -0.25 * np.maximum(areas[:-1], 1e-6)))))
    rows.sort(key=lambda r: r["growth_ha_per_year"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
