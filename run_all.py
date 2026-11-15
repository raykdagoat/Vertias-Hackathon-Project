"""Glacier Lake Watch: the whole pipeline in one command.

    python run_all.py                 # real satellite data (needs internet, ~30-45 min first run)
    python run_all.py --synthetic     # fake data, for checking the code works offline

Steps
  1. Download one cloud-free Sentinel-2 chip per lake per year, plus labels and slope
  2. Train a water model on 2021 images of the TRAINING lakes only
  3. Score it against 3 baselines on lakes it never saw (Himalaya and Andes)
  4. Break errors down by terrain (shadow, snow/ice, steep slopes) to find where it fails
  5. Measure each lake's area every year, then backtest a forecast vs persistence
  6. Measure shape, water colour, ice, glacier distance, terrain, volume and flood potential
  7. Build a report card per lake (flood hazard, drought/water supply, drained lakes,
     glacier retreat, water quality) and write results/RESULTS.md with all figures
"""
import argparse
import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import ndimage

from glw import model as M
from glw import timeseries as T
from glw import viz
from glw.assess import report_card
from glw.measure import measure
from glw.zones import LABEL_YEAR, ZONE_BY_ID, ZONES


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-year", type=int, default=2017)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--synthetic", action="store_true", help="fake data, for testing only")
    ap.add_argument("--cache", default="data/chips")
    ap.add_argument("--out", default="results")
    ap.add_argument("--seed", type=int, default=0)
    return ap.parse_args()


# ------------------------------------------------------------------ 1. data
def load_all(args, years):
    if args.synthetic:
        from glw import synthetic as S
        idx = {z["id"]: i for i, z in enumerate(ZONES)}
        static = {z["id"]: S.make_static(z, idx[z["id"]]) for z in ZONES}
        chips = {(z["id"], y): S.make_chip(z, y, idx[z["id"]]) for z in ZONES for y in years}
        return static, chips

    from glw import data as D

    print("Downloading labels and slope ...")
    with ThreadPoolExecutor(args.workers) as ex:
        static = dict(zip([z["id"] for z in ZONES], ex.map(lambda z: D.get_static(z, args.cache), ZONES)))

    jobs = [(z, y) for z in ZONES for y in years]

    def job(zy):
        z, y = zy
        for attempt in range(3):
            try:
                c = D.get_chip(z, y, args.cache)
                print(f"  {z['id']:<14} {y}: " + (f"{c['date']} clear={c['clear_frac']:.2f}" if c else "no image"))
                return c
            except Exception as e:
                print(f"  {z['id']} {y} attempt {attempt + 1} failed: {e}")
                time.sleep(3)
        return None

    print(f"Downloading {len(jobs)} Sentinel-2 chips ...")
    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(job, jobs))
    chips = {(z["id"], y): c for (z, y), c in zip(jobs, results)}
    return static, chips


def label_chip(chips, zid, years):
    """The 2021 image (to match the 2021 label map), or the nearest year we have."""
    for y in sorted(years, key=lambda y: abs(y - LABEL_YEAR)):
        if chips.get((zid, y)) is not None:
            return y, chips[(zid, y)]
    return None, None


# ------------------------------------------------------------------ main
def main():
    args = parse()
    years = list(range(args.first_year, args.last_year + 1))
    out = args.out if not args.synthetic else args.out + "_synthetic"
    figs = os.path.join(out, "figures")
    os.makedirs(figs, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    static, chips = load_all(args, years)
    report = dict(synthetic=args.synthetic, years=years, zones={})

    # ---------------------------------------------------------- 2. train
    X_parts, y_parts, label_years = [], [], {}
    for z in ZONES:
        if z["split"] != "train":
            continue
        ly, chip = label_chip(chips, z["id"], years)
        if chip is None:
            print(f"  no training image for {z['id']}"); continue
        label_years[z["id"]] = ly
        F = M.make_features(chip["bands"], static[z["id"]]["slope"], chip["scl"])
        valid = M.valid_mask(chip)
        truth = static[z["id"]]["worldcover"] == M.WC_WATER
        X = M.to_table(F, valid); y = truth[valid]
        water_idx = np.where(y)[0]; land_idx = np.where(~y)[0]
        keep_land = rng.choice(land_idx, size=min(len(land_idx), max(4 * len(water_idx), 20000)), replace=False)
        keep = np.concatenate([water_idx, keep_land])
        X_parts.append(X[keep]); y_parts.append(y[keep])
    X_train = np.concatenate(X_parts); y_train = np.concatenate(y_parts)
    print(f"Training on {len(y_train):,} pixels ({y_train.mean():.1%} water) from {len(X_parts)} lakes")
    clf = M.train_model(X_train, y_train, seed=args.seed)                              # bands + ESA flags
    clf_bands = M.train_model(X_train[:, :M.N_BAND_FEATURES], y_train, seed=args.seed)  # bands only
    ndwi_t = M.tune_ndwi_threshold(X_train, y_train)
    report["ndwi_threshold"] = ndwi_t
    report["n_train_pixels"] = int(len(y_train))
    import joblib
    joblib.dump(dict(clf=clf, clf_bands=clf_bands, ndwi_threshold=ndwi_t, features=M.FEATURE_NAMES),
                os.path.join(out, "model.joblib"))

    # ---------------------------------------------------------- 3 + 4. evaluate
    methods = ["Always land", f"NDWI > {ndwi_t}", "ESA scene class", "Our model, bands only", "Our model"]
    groups = {"train (seen, for reference)": "train", "Himalaya (unseen lakes)": "test_himalaya",
              "Andes (new continent)": "test_andes"}
    conditions = ["normal", "shadow", "snow/ice", "steep (>20 deg)"]
    group_conf = {g: {m: {} for m in methods} for g in groups}
    cond_conf = {g: {m: {c: {} for c in conditions} for m in methods[1:]} for g in groups if g != "train (seen, for reference)"}
    per_zone = []
    test_samples = []

    for z in ZONES:
        ly, chip = label_chip(chips, z["id"], years)
        if chip is None:
            continue
        g = [k for k, v in groups.items() if v == z["split"]][0]
        F = M.make_features(chip["bands"], static[z["id"]]["slope"], chip["scl"])
        valid = M.valid_mask(chip)
        wc = static[z["id"]]["worldcover"]
        truth = wc == M.WC_WATER
        preds = {
            methods[0]: M.baseline_all_land(F),
            methods[1]: M.baseline_ndwi(F, ndwi_t),
            methods[2]: M.baseline_scl(chip),
            methods[3]: M.predict_mask(clf_bands, F, valid),
            methods[4]: M.predict_mask(clf, F, valid),
        }
        shadow = np.isin(chip["scl"], [2, 3])
        snow = (wc == M.WC_SNOW) | (chip["scl"] == 11)
        steep = static[z["id"]]["slope"] > 20
        cond_masks = {"shadow": shadow, "snow/ice": snow & ~shadow, "steep (>20 deg)": steep & ~shadow & ~snow}
        cond_masks["normal"] = ~(shadow | snow | steep)
        row = dict(zone=z["id"], name=z["name"], split=z["split"], image_date=chip["date"],
                   water_ha_label=float(truth[valid].sum() * M.PIXEL_HA))
        for m, p in preds.items():
            c = M.confusion(p, truth, valid)
            group_conf[g][m] = M.add_conf(group_conf[g][m], c)
            row[m] = M.scores(c)
            if g in cond_conf and m != methods[0]:
                for cn, cm in cond_masks.items():
                    cc = M.confusion(p, truth, valid & cm)
                    cond_conf[g][m][cn] = M.add_conf(cond_conf[g][m][cn], cc)
        per_zone.append(row)
        if z["split"] != "train":
            viz.save_error_figure(os.path.join(figs, f"errors_{z['id']}.png"), f"{z['name']} ({z['country']}), {chip['date']}",
                                  chip["bands"], {methods[1]: preds[methods[1]], methods[2]: preds[methods[2]], methods[4]: preds[methods[4]]}, truth, valid)
            idx = np.where(valid.ravel())[0]
            take = rng.choice(idx, size=min(4000, len(idx)), replace=False)
            test_samples.append((M.to_table(F, valid)[np.searchsorted(idx, take)], truth.ravel()[take]))

    group_scores = {g: {m: M.scores(c) for m, c in d.items() if c} for g, d in group_conf.items()}
    cond_scores = {g: {m: {c: M.scores(v) for c, v in d.items() if v} for m, d in gd.items()} for g, gd in cond_conf.items()}
    for g, tbl in group_scores.items():
        if g != "train (seen, for reference)" and tbl:
            viz.save_metric_bars(os.path.join(figs, f"metrics_{groups[g]}.png"), tbl, g)

    # which inputs matter most (permutation importance on unseen-lake pixels)
    importance = {}
    if test_samples:
        from sklearn.inspection import permutation_importance
        Xs = np.concatenate([a for a, _ in test_samples]); ys = np.concatenate([b for _, b in test_samples])
        if ys.any() and (~ys).any():
            pi = permutation_importance(clf, Xs, ys, scoring="f1", n_repeats=3, random_state=args.seed)
            importance = {n: float(v) for n, v in sorted(zip(M.FEATURE_NAMES, pi.importances_mean), key=lambda t: -t[1])}

    # ---------------------------------------------------------- 5. yearly areas
    series, series_rows, measurements = {}, [], {}
    for z in ZONES:
        wc_water = static[z["id"]]["worldcover"] == M.WC_WATER
        region = ndimage.binary_dilation(wc_water, iterations=25) if wc_water.any() else np.ones_like(wc_water)
        lake_region = ndimage.binary_dilation(wc_water, iterations=3) if wc_water.any() else None
        pts, mrows = [], []
        for y in years:
            chip = chips.get((z["id"], y))
            if chip is None:
                series_rows.append(dict(zone=z["id"], year=y, area_ha="", reliable=False, note="no image")); continue
            F = M.make_features(chip["bands"], static[z["id"]]["slope"], chip["scl"])
            valid = M.valid_mask(chip)
            water = M.predict_mask(clf, F, valid)
            lake = M.main_lake(water)
            area = float(lake.sum() * M.PIXEL_HA)
            clear_over_lake = float(valid[region].mean())
            reliable = clear_over_lake >= 0.9 and area > 0
            series_rows.append(dict(zone=z["id"], year=y, area_ha=round(area, 2), reliable=reliable,
                                    note=f"{chip['date']} clear over lake {clear_over_lake:.0%}"))
            m = measure(chip, static[z["id"]], lake, water, valid, lake_region)
            mrows.append(dict(zone=z["id"], name=z["name"], year=y, date=chip["date"], reliable=reliable,
                              clear_pct=round(100 * clear_over_lake, 1), **m))
            if reliable:
                pts.append((y, area))
        series[z["id"]] = pts
        measurements[z["id"]] = mrows
    cards = report_card(measurements, ZONE_BY_ID)
    names = {z["id"]: z["name"] for z in ZONES}
    viz.save_timeseries_figure(os.path.join(figs, "lake_areas.png"), series, names)

    test_years = [y for y in years[-3:]]
    bt = T.backtest(series, test_years)
    forecast = dict(test_years=test_years, n=len(bt),
                    mae_persistence=T.mae(bt, "persistence"), mae_trend=T.mae(bt, "trend"),
                    mae_damped=T.mae(bt, "damped"), rows=bt)
    wl = T.watch_list(series, ZONE_BY_ID, years[-1] + 1)

    # before / after pictures for the fastest-growing lake and for South Lhonak
    for zid in ([wl[0]["zone"]] if wl else []) + ["south_lhonak"]:
        pts = series.get(zid, [])
        if len(pts) >= 2:
            ya, yb = pts[0][0], pts[-1][0]
            ca, cb = chips[(zid, ya)], chips[(zid, yb)]
            ma = M.main_lake(M.predict_mask(clf, M.make_features(ca["bands"], static[zid]["slope"], ca["scl"]), M.valid_mask(ca)))
            mb = M.main_lake(M.predict_mask(clf, M.make_features(cb["bands"], static[zid]["slope"], cb["scl"]), M.valid_mask(cb)))
            viz.save_before_after(os.path.join(figs, f"before_after_{zid}.png"), names[zid], ca, cb, ma, mb)

    # ---------------------------------------------------------- 6. save
    report.update(group_scores=group_scores, condition_scores=cond_scores, per_zone=per_zone,
                  importance=importance, forecast=forecast, watch_list=wl, label_years=label_years,
                  report_card=cards)
    with open(os.path.join(out, "metrics.json"), "w") as f:
        json.dump(report, f, indent=2, default=float)
    with open(os.path.join(out, "lake_areas.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["zone", "year", "area_ha", "reliable", "note"]); w.writeheader(); w.writerows(series_rows)
    if wl:
        with open(os.path.join(out, "watch_list.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(wl[0].keys())); w.writeheader(); w.writerows(wl)
    allm = [r for rows in measurements.values() for r in rows]
    if allm:
        with open(os.path.join(out, "lake_measurements.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(allm[0].keys())); w.writeheader(); w.writerows(allm)
    if cards:
        with open(os.path.join(out, "report_card.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(cards[0].keys())); w.writeheader(); w.writerows(cards)
    viz.save_multi_metric(os.path.join(figs, "lake_indicators.png"), measurements, names)
    from glw.report import write_results_md
    write_results_md(out, report, methods)
    print(f"\nDone. Open {out}/RESULTS.md")


if __name__ == "__main__":
    main()
