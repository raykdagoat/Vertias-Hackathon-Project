"""Turn yearly measurements into a report card for each lake, for several uses.

Uses covered
  1. Outburst flood hazard   growth, volume, glacier contact, steep valley below
  2. Drought / water supply  shrinking lakes and dry years below normal
  3. Already drained         sudden drops that may mean an outburst happened
  4. Glacier retreat         how fast the ice in the 4 km box is shrinking
  5. Water quality           muddy (glacier-fed) vs clear water, ice-covered lakes
"""
import numpy as np


def _slope(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    ok = np.isfinite(ys)
    if ok.sum() < 3:
        return np.nan
    return float(np.polyfit(xs[ok], ys[ok], 1)[0])


def _pct_rank(vals):
    """0 to 1 rank of each value among all lakes (NaN -> 0)."""
    v = np.array([x if np.isfinite(x) else -np.inf for x in vals], float)
    order = v.argsort().argsort()
    return order / max(len(v) - 1, 1)


def report_card(measurements, zones_by_id):
    """measurements: {zone_id: [dict(year=..., reliable=..., **measure())]}"""
    cards = []
    for zid, rows in measurements.items():
        rows = [r for r in rows if r.get("reliable")]
        if len(rows) < 2:
            continue
        z = zones_by_id[zid]
        yrs = [r["year"] for r in rows]
        area = [r["area_ha"] for r in rows]
        latest, first = rows[-1], rows[0]
        med = float(np.median(area))
        growth = _slope(yrs, area)
        drops = [(rows[i]["year"], area[i - 1], area[i]) for i in range(1, len(rows))
                 if area[i] < 0.75 * area[i - 1]]
        # a dry year is one well below what the lake's own trend says it should be
        if len(rows) >= 4:
            k, b = np.polyfit(yrs, area, 1)
            expected = [k * y + b for y in yrs]
        else:
            expected = [med] * len(rows)
        dry_years = [r["year"] for r, e in zip(rows, expected) if r["area_ha"] < 0.85 * e]
        c = dict(
            zone=zid, name=z["name"], country=z["country"], downstream=z["downstream"],
            years=f"{yrs[0]}-{yrs[-1]}", n_years=len(rows),
            area_ha=latest["area_ha"], area_first_ha=first["area_ha"], area_median_ha=med,
            growth_ha_per_year=growth, growth_pct_per_year=100 * growth / max(med, 1e-6),
            volume_million_m3=latest["volume_million_m3"],
            volume_change_million_m3=latest["volume_million_m3"] - first["volume_million_m3"],
            peak_flow_m3s=latest["peak_flow_m3s"],
            length_m=latest["length_m"], elongation=latest["elongation"],
            lake_elev_m=latest["lake_elev_m"], valley_drop_m=latest["valley_drop_m"],
            lake_to_ice_m=latest["lake_to_ice_m"], glacier_contact=latest["glacier_contact"],
            ice_area_ha=latest["ice_area_ha"],
            ice_change_ha_per_year=_slope(yrs, [r["ice_area_ha"] for r in rows]),
            turbidity=latest["turbidity"], water_red=latest["water_red"],
            ice_on_lake_pct=latest["ice_on_lake_pct"],
            sudden_drop=bool(drops), drop_years=",".join(str(d[0]) for d in drops),
            dry_years=",".join(str(y) for y in dry_years),
        )
        flags = []
        if c["growth_pct_per_year"] > 2:
            flags.append("Growing")
        if c["growth_pct_per_year"] < -2:
            flags.append("Shrinking")
        if c["sudden_drop"]:
            flags.append(f"Sudden drop {c['drop_years']}")
        if dry_years and not drops:
            flags.append(f"Low-water years {c['dry_years']}")
        if c["glacier_contact"]:
            flags.append("Touches glacier")
        if c["ice_on_lake_pct"] > 20:
            flags.append("Partly frozen")
        c["flags"] = ", ".join(flags) if flags else "Stable"
        cards.append(c)

    if not cards:
        return cards
    # flood screening score: transparent weights, ranked against the other lakes
    vol = _pct_rank([c["volume_million_m3"] for c in cards])
    grow = _pct_rank([c["growth_pct_per_year"] for c in cards])
    drop = _pct_rank([c["valley_drop_m"] for c in cards])
    for i, c in enumerate(cards):
        s = 35 * vol[i] + 30 * grow[i] + 15 * drop[i] + 20 * (1.0 if c["glacier_contact"] else 0.0)
        c["flood_score"] = round(float(s), 1)
        c["flood_tier"] = "High" if s >= 60 else ("Medium" if s >= 35 else "Low")
        # water supply concern: shrinking or many dry years
        c["water_supply_concern"] = ("High" if c["growth_pct_per_year"] < -3 else
                                     "Medium" if (c["growth_pct_per_year"] < -1 or c["dry_years"]) else "Low")
    cards.sort(key=lambda c: c["flood_score"], reverse=True)
    for i, c in enumerate(cards, 1):
        c["flood_rank"] = i
    return cards


SCORE_NOTE = ("Flood screening score (0-100) = 35 x volume rank + 30 x growth rank + 15 x valley drop rank "
              "+ 20 if the lake touches glacier ice. Ranks are relative to the other lakes here. "
              "High >= 60, Medium >= 35. Prototype screening only, not a hazard assessment.")
