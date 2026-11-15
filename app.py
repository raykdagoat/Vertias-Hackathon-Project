"""Glacier Lake Watch demo (Gradio).

    python app.py              # uses results/ and data/chips/ from a real run_all.py
    python app.py --synthetic  # uses fake data, for testing only
In Colab, the notebook launches this with a public share link.
"""
import argparse
import csv
import os

import gradio as gr
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from glw import model as M
from glw import viz
from glw.zones import ZONE_BY_ID, ZONES

ap = argparse.ArgumentParser()
ap.add_argument("--synthetic", action="store_true")
ap.add_argument("--share", action="store_true")
ap.add_argument("--cache", default="data/chips")
args, _ = ap.parse_known_args()
OUT = "results_synthetic" if args.synthetic else "results"
BUNDLE = joblib.load(os.path.join(OUT, "model.joblib"))
CLF = BUNDLE["clf"]

if args.synthetic:
    from glw import synthetic as S
    _idx = {z["id"]: i for i, z in enumerate(ZONES)}
    get_chip = lambda z, y: S.make_chip(z, y, _idx[z["id"]])
    get_static = lambda z: S.make_static(z, _idx[z["id"]])
else:
    from glw import data as D
    get_chip = lambda z, y: D.get_chip(z, y, args.cache)
    get_static = lambda z: D.get_static(z, args.cache)

LABELS = {f"{z['name']} ({z['country']})": z["id"] for z in ZONES}


def run_model(chip, static):
    F = M.make_features(chip["bands"], static["slope"])
    valid = M.valid_mask(chip)
    pred = M.predict_mask(CLF, F, valid)
    return M.main_lake(pred), valid


def load_series(zid):
    p = os.path.join(OUT, "lake_areas.csv")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [(int(r["year"]), float(r["area_ha"]), r["reliable"] == "True") for r in csv.DictReader(f)
                if r["zone"] == zid and r["area_ha"]]


def explore(label, year):
    zid = LABELS[label]; z = ZONE_BY_ID[zid]; year = int(year)
    chip = get_chip(z, year)
    if chip is None:
        return None, None, f"No usable Sentinel-2 image for {z['name']} in {year}."
    lake, valid = run_model(chip, get_static(z))
    photo = viz.rgb(chip["bands"]); over = viz.overlay_mask(chip["bands"], lake)
    s = load_series(zid)
    fig, ax = plt.subplots(figsize=(6, 3))
    if s:
        ys, ar, rel = zip(*s)
        ax.plot(ys, ar, "-o", color="#185FA5")
        for y_, a_, r_ in s:
            if not r_:
                ax.plot(y_, a_, "x", color="#A32D2D", ms=9)
        ax.axvline(year, color="#888780", ls="--")
    ax.set_xlabel("Year"); ax.set_ylabel("Lake area (ha)"); ax.set_title("Area by year (x = too cloudy, not used)")
    ax.grid(alpha=0.3); fig.tight_layout()
    cloud = 1 - valid.mean()
    info = (f"**{z['name']}**, {z['country']}  \nImage date: {chip['date']}  \n"
            f"Main lake area: **{lake.sum() * M.PIXEL_HA:.1f} ha**  \nCloud over chip: {cloud:.0%}  \n"
            f"Downstream: {z['downstream']}")
    return [(photo, "Satellite photo"), (over, "Model's lake (blue)")], fig, info


def watch_table():
    p = os.path.join(OUT, "watch_list.csv")
    if not os.path.exists(p):
        return [["Run run_all.py first"] + [""] * 6]
    with open(p) as f:
        rows = list(csv.DictReader(f))
    return [[r["rank"], r["name"], r["country"], r["downstream"], f"{float(r['latest_area_ha']):.1f}",
             f"{float(r['growth_ha_per_year']):+.2f}", "yes" if r["sudden_drop"] == "True" else "no"] for r in rows]


def check_any(lat, lon, season, year_a, year_b):
    """Run the model on ANY lake on Earth, live from the cloud."""
    if args.synthetic:
        return None, "Live check needs real data. Run without --synthetic."
    try:
        lat, lon = float(lat), float(lon)
    except ValueError:
        return None, "Enter numbers for latitude and longitude."
    months = {"Jun-Sep (southern dry season)": [6, 7, 8, 9], "Sep-Nov (after monsoon)": [9, 10, 11],
              "Jul-Sep (northern summer)": [7, 8, 9]}[season]
    z = dict(id=f"custom_{lat:.3f}_{lon:.3f}", name="Your lake", country="", lat=lat, lon=lon,
             months=months, split="custom", downstream="")
    static = D.get_static(z, args.cache)
    out, notes = [], []
    for y in (int(year_a), int(year_b)):
        c = D.get_chip(z, y, args.cache)
        if c is None:
            notes.append(f"{y}: no clear image found"); continue
        lake, valid = run_model(c, static)
        out.append((viz.overlay_mask(c["bands"], lake), f"{c['date']}: {lake.sum() * M.PIXEL_HA:.1f} ha"))
        notes.append(f"{c['date']}: {lake.sum() * M.PIXEL_HA:.1f} ha, cloud {1 - valid.mean():.0%}")
    return out, "  \n".join(notes)


with gr.Blocks(title="Glacier Lake Watch") as demo:
    gr.Markdown("# Glacier Lake Watch\nFinds glacial lakes in free Sentinel-2 satellite images, measures them every "
                "year, and ranks which ones are growing fastest so a hazard team knows where to look first. "
                "*Prototype for a student hackathon, not an official warning system.*")
    with gr.Tab("Explore a lake"):
        with gr.Row():
            dd = gr.Dropdown(list(LABELS), value=list(LABELS)[0], label="Lake")
            yr = gr.Slider(2017, 2025, value=2025, step=1, label="Year")
        go = gr.Button("Run model", variant="primary")
        gal = gr.Gallery(columns=2, height=360); plot = gr.Plot(); md = gr.Markdown()
        go.click(explore, [dd, yr], [gal, plot, md])
    with gr.Tab("Watch list"):
        gr.Markdown("Lakes ranked by growth in hectares per year. 'Sudden drop' can mean an outburst flood already happened.")
        tbl = gr.Dataframe(headers=["Rank", "Lake", "Country", "Downstream", "Latest area (ha)", "Growth (ha/yr)", "Sudden drop?"],
                           value=watch_table, interactive=False)
    with gr.Tab("Check any lake on Earth"):
        gr.Markdown("Type the coordinates of any glacial lake. The tool downloads two images and measures the change.")
        with gr.Row():
            la = gr.Textbox(label="Latitude", value="58.42"); lo = gr.Textbox(label="Longitude", value="-134.55")
            se = gr.Dropdown(["Jun-Sep (southern dry season)", "Sep-Nov (after monsoon)", "Jul-Sep (northern summer)"],
                             value="Jul-Sep (northern summer)", label="Season")
        with gr.Row():
            ya = gr.Slider(2017, 2025, value=2017, step=1, label="First year")
            yb = gr.Slider(2017, 2025, value=2025, step=1, label="Second year")
        go2 = gr.Button("Measure change", variant="primary")
        gal2 = gr.Gallery(columns=2, height=360); md2 = gr.Markdown()
        go2.click(check_any, [la, lo, se, ya, yb], [gal2, md2])

if __name__ == "__main__":
    demo.launch(share=args.share)
