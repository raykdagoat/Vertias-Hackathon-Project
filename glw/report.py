"""Write results/RESULTS.md from the numbers the pipeline actually produced."""
import os


def _pct(x):
    return f"{100 * x:.1f}%"


def write_results_md(out, r, methods):
    L = []
    if r["synthetic"]:
        L += ["> **WARNING: these results come from FAKE synthetic data made to test the code.**",
              "> Do not report them. Run `python run_all.py` without `--synthetic` for real results.", ""]
    L += ["# Glacier Lake Watch: results", "",
          "Every number on this page was written automatically by `run_all.py` from the run it just finished.",
          f"Years: {r['years'][0]} to {r['years'][-1]}. Training pixels: {r['n_train_pixels']:,}. "
          f"NDWI threshold tuned on training lakes only: {r['ndwi_threshold']}.", ""]

    # ---- detection
    L += ["## 1. Does the model beat simple baselines at finding lake water?", "",
          "Answer key: ESA WorldCover 2021 water class. Scores are per pixel (10 m x 10 m) on lakes the model never saw.",
          "Missed water = false negatives. False water = false alarms (false positives).", ""]
    for g, tbl in r["group_scores"].items():
        if not tbl:
            continue
        L += [f"### {g}", "", "| Method | Accuracy | Recall | Precision | F1 | IoU | Missed water (ha) | False water (ha) |",
              "|---|---|---|---|---|---|---|---|"]
        for m in methods:
            if m in tbl:
                s = tbl[m]
                L.append(f"| {m} | {_pct(s['accuracy'])} | {_pct(s['recall'])} | {_pct(s['precision'])} | "
                         f"{s['f1']:.3f} | {s['iou']:.3f} | {s['missed_water_ha']:.1f} | {s['false_water_ha']:.1f} |")
        L.append("")
        if "Our model" in tbl and len(tbl) > 1:
            best_base = max((m for m in tbl if not m.startswith("Our model")), key=lambda m: tbl[m]["f1"])
            d = tbl["Our model"]["f1"] - tbl[best_base]["f1"]
            verdict = "beats" if d > 0.005 else ("ties with" if abs(d) <= 0.005 else "does NOT beat")
            L += [f"Takeaway: our model {verdict} the best baseline ({best_base}) here, F1 change {d:+.3f}.", ""]
        if g == "train (seen, for reference)":
            L += ["(Training lakes are shown only for reference. They are not a fair test.)", ""]

    # ---- conditions
    L += ["## 2. Where does it fail?", "",
          "Same unseen lakes, split by terrain. Shadow = Sentinel-2 dark/shadow pixels. "
          "Snow/ice from WorldCover or the scene classifier. Steep = slope over 20 degrees.", ""]
    for g, gd in r["condition_scores"].items():
        L += [f"### {g}", "", "| Method | Terrain | Recall | Precision | F1 | Missed water (ha) | False water (ha) |",
              "|---|---|---|---|---|---|---|"]
        for m, cd in gd.items():
            for c, s in cd.items():
                L.append(f"| {m} | {c} | {_pct(s['recall'])} | {_pct(s['precision'])} | {s['f1']:.3f} | "
                         f"{s['missed_water_ha']:.1f} | {s['false_water_ha']:.1f} |")
        L.append("")
    # worst zone
    tz = [z for z in r["per_zone"] if z["split"] != "train" and "Our model" in z]
    scored = [z for z in tz if z["water_ha_label"] >= 5] or tz
    if tz:
        worst = min(scored, key=lambda z: z["Our model"]["f1"])
        best = max(scored, key=lambda z: z["Our model"]["f1"])
        L += ["### Per lake (unseen lakes)", "", "| Lake | Split | Image date | Label water (ha) | Model F1 | Bands-only F1 | ESA F1 | NDWI F1 | Missed (ha) | False (ha) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        nd = [m for m in methods if m.startswith("NDWI")][0]
        for z in tz:
            s = z["Our model"]
            L.append(f"| {z['name']} | {z['split']} | {z['image_date']} | {z['water_ha_label']:.1f} | {s['f1']:.3f} | "
                     f"{z['Our model, bands only']['f1']:.3f} | {z['ESA scene class']['f1']:.3f} | {z[nd]['f1']:.3f} | {s['missed_water_ha']:.1f} | {s['false_water_ha']:.1f} |")
        L += ["", f"Worst unseen lake for our model: **{worst['name']}** (F1 {worst['Our model']['f1']:.3f}). "
              f"See `figures/errors_{worst['zone']}.png`. Best: {best['name']} (F1 {best['Our model']['f1']:.3f}).", "",
              f"![worst case](figures/errors_{worst['zone']}.png)", ""]
    if r["importance"]:
        L += ["### Which inputs matter most", "", "Permutation importance on unseen-lake pixels (drop in F1 when that input is scrambled):", "",
              "| Input | Importance |", "|---|---|"]
        L += [f"| {k} | {v:.3f} |" for k, v in r["importance"].items()] + [""]

    # ---- forecast
    f = r["forecast"]
    L += ["## 3. Can we forecast next year's lake size?", "",
          f"Backtest years: {f['test_years']}. Each forecast uses only earlier years (no shuffling). "
          f"{f['n']} lake-years tested. The 'actual' value is our own model's measurement, not a field survey.", "",
          "| Method | Mean absolute error (ha) |", "|---|---|",
          f"| Persistence baseline (next year = this year) | {f['mae_persistence']:.2f} |",
          f"| Linear trend | {f['mae_trend']:.2f} |",
          f"| Damped trend (average of the two) | {f['mae_damped']:.2f} |", ""]
    if f["n"]:
        bestm = min(["persistence", "trend", "damped"], key=lambda k: f[f"mae_{k}"])
        L += [f"Takeaway: the best forecast here is **{bestm}**." +
              (" Persistence is hard to beat, which is an honest result." if bestm == "persistence" else ""), ""]
    L += ["![lake areas](figures/lake_areas.png)", ""]

    # ---- watch list
    L += ["## 4. Watch list: which lakes should a hazard team check first?", "",
          "Ranked by growth in hectares per year (linear fit over reliable years). "
          "This is a prototype ranking, not an official hazard assessment.", "",
          "| Rank | Lake | Country | Downstream | Area first year (ha) | Area latest (ha) | Growth (ha/yr) | Growth (%/yr) | Next-year forecast (ha) | Sudden drop? |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for w in r["watch_list"]:
        L.append(f"| {w['rank']} | {w['name']} | {w['country']} | {w['downstream']} | {w['first_area_ha']:.1f} ({w['first_year']}) | "
                 f"{w['latest_area_ha']:.1f} ({w['latest_year']}) | {w['growth_ha_per_year']:+.2f} | {w['growth_pct_per_year']:+.1f} | "
                 f"{w['forecast_next_ha']:.1f} | {'yes' if w['sudden_drop'] else 'no'} |")
    L.append("")
    for fn in sorted(os.listdir(os.path.join(out, "figures"))):
        if fn.startswith("before_after_"):
            L += [f"![{fn}](figures/{fn})", ""]

    # ---- report card
    cards = r.get("report_card") or []
    if cards:
        from glw.assess import SCORE_NOTE
        f_ = lambda v, d=1: "n/a" if v is None or (isinstance(v, float) and v != v) else f"{v:,.{d}f}"
        L += ["## 5. Lake report card: one image, many uses", "",
              "From each lake outline we also measure shape, water colour, ice, distance to the glacier, terrain, "
              "and estimated volume and flood peak. Values are for the latest clear year. "
              "Volume uses Huggel et al. (2002). Peak flow shows a typical value (Clague and Mathews 1973) and a worst case "
              "(Huggel et al. 2002). These are rough and can be off by 2x or more. Glacier = a connected ice body of at least 5 ha.", "",
              "### Outburst flood screening", "",
              "| Rank | Lake | Tier | Score | Volume (million m3) | Peak flow, typical / worst case (m3/s) | Growth (%/yr) | Valley drop below lake (m) | Distance to glacier ice (m) | Flags |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for c in cards:
            L.append(f"| {c['flood_rank']} | {c['name']} | {c['flood_tier']} | {c['flood_score']} | {f_(c['volume_million_m3'], 2)} | "
                     f"{f_(c['peak_flow_typical_m3s'], 0)} / {f_(c['peak_flow_m3s'], 0)} | {c['growth_pct_per_year']:+.1f} | {f_(c['valley_drop_m'], 0)} | "
                     f"{f_(c['lake_to_ice_m'], 0)} | {c['flags']} |")
        L += ["", SCORE_NOTE, "",
              "### Drought and water supply", "",
              "Some of these lakes are also water sources (Laguna Paron feeds a hydropower and irrigation system). "
              "A lake that keeps shrinking, or has years well below its own trend, is a water supply warning. Note: Paron and Palcacocha are partly drained by people on purpose (hydropower and flood safety), so their changes are not only climate.", "",
              "| Lake | Median area (ha) | Latest (ha) | Stored water change since first year (million m3) | Low-water years (<85% of trend) | Concern |",
              "|---|---|---|---|---|---|"]
        for c in sorted(cards, key=lambda c: c["growth_pct_per_year"]):
            L.append(f"| {c['name']} | {f_(c['area_median_ha'])} | {f_(c['area_ha'])} | {c['volume_change_million_m3']:+.2f} | "
                     f"{c['dry_years'] or 'none'} | {c['water_supply_concern']} |")
        L += ["", "### Glacier retreat and water quality", "",
              "| Lake | Glacier ice in box (ha) | Ice change (ha/yr) | Water colour | Red reflectance | Ice on lake (%) | Lake length (m) | Elongation | Lake elevation (m) |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c in cards:
            L.append(f"| {c['name']} | {f_(c['ice_area_ha'])} | {f_(c['ice_change_ha_per_year'], 2)} | {c['turbidity']} | "
                     f"{f_(c['water_red'], 3)} | {f_(c['ice_on_lake_pct'])} | {f_(c['length_m'], 0)} | {f_(c['elongation'], 2)} | "
                     f"{f_(c['lake_elev_m'], 0)} |")
        L += ["", "Ice area mixes glaciers with leftover seasonal snow, so single years can jump. The trend over many years is more useful.",
              "Muddy, milky water usually means the lake is fed by a glacier that is actively grinding rock.", "",
              "![indicators](figures/lake_indicators.png)", "",
              "Every yearly measurement is in `lake_measurements.csv`."]
    with open(os.path.join(out, "RESULTS.md"), "w") as fh:
        fh.write("\n".join(L))
