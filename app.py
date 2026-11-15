"""Glacier Lake Watch web app (Gradio).

    python app.py                # uses results/ from a real run_all.py
    python app.py --share        # same, plus a temporary public link (Colab)
    python app.py --synthetic    # fake data, for testing only
On Hugging Face Spaces this file runs automatically (see DEPLOY.md).
"""
import argparse
import csv
import json
import os

import gradio as gr
import plotly.graph_objects as go

from glw import model as M
from glw import viz
from glw.measure import measure
from glw.zones import ZONE_BY_ID, ZONES

ap = argparse.ArgumentParser()
ap.add_argument("--synthetic", action="store_true")
ap.add_argument("--share", action="store_true")
ap.add_argument("--cache", default="data/chips")
args, _ = ap.parse_known_args()
OUT = "results_synthetic" if args.synthetic else "results"
MODEL_PATH = os.path.join(OUT, "model.joblib")

CLF = None
if os.path.exists(MODEL_PATH):
    import joblib
    CLF = joblib.load(MODEL_PATH)["clf"]

if args.synthetic:
    from glw import synthetic as S
    _idx = {z["id"]: i for i, z in enumerate(ZONES)}
    get_chip = lambda z, y: S.make_chip(z, y, _idx[z["id"]])
    get_static = lambda z: S.make_static(z, _idx[z["id"]])
else:
    from glw import data as D
    get_chip = lambda z, y: D.get_chip(z, y, args.cache)
    get_static = lambda z: D.get_static(z, args.cache)

LABELS = {f"{z['name']}, {z['country']}": z["id"] for z in ZONES}
ICE, ALERT = "#378ADD", "#D85A30"


# ------------------------------------------------------------------ data helpers
def read_csv(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def metrics():
    p = os.path.join(OUT, "metrics.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def series(zid):
    return [(int(r["year"]), float(r["area_ha"]), r["reliable"] == "True")
            for r in read_csv("lake_areas.csv") if r["zone"] == zid and r["area_ha"]]


def run_model(chip, static):
    F = M.make_features(chip["bands"], static["slope"])
    valid = M.valid_mask(chip)
    water = M.predict_mask(CLF, F, valid)
    return M.main_lake(water), valid, water


def fmt(v, d=1, unit=""):
    try:
        if v != v:
            return "n/a"
    except TypeError:
        return str(v)
    return f"{v:,.{d}f}{unit}"


def measure_md(m):
    contact = "yes, touching" if m["glacier_contact"] else fmt(m["lake_to_ice_m"], 0, " m")
    return (f"| Measurement | Value |\n|---|---|\n"
            f"| Lake area | **{fmt(m['area_ha'])} ha** ({fmt(m['area_ha'] / 100, 2)} km²) |\n"
            f"| Estimated water volume | {fmt(m['volume_million_m3'], 1)} million m³ |\n"
            f"| Worst-case outburst peak flow | {fmt(m['peak_flow_m3s'], 0)} m³/s |\n"
            f"| Lake length / elongation | {fmt(m['length_m'], 0)} m / {fmt(m['elongation'], 2)} |\n"
            f"| Shoreline complexity | {fmt(m['shoreline_index'], 2)} (1 = perfect circle) |\n"
            f"| Water colour | {m['turbidity']} (red reflectance {fmt(m['water_red'], 3)}) |\n"
            f"| Ice on the lake | {fmt(m['ice_on_lake_pct'], 0)}% |\n"
            f"| Distance to glacier ice | {contact} |\n"
            f"| Glacier and snow ice in 4 km box | {fmt(m['ice_area_ha'])} ha |\n"
            f"| Lake elevation | {fmt(m['lake_elev_m'], 0)} m |\n"
            f"| Valley drop below lake | {fmt(m['valley_drop_m'], 0)} m |")


def _layout(fig, h=360):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", size=13))
    return fig


# ------------------------------------------------------------------ UI pieces
def stat_cards():
    wl = read_csv("report_card.csv"); m = metrics()
    f1 = "n/a"
    try:
        f1 = f"{m['group_scores']['Himalaya (unseen lakes)']['Our model']['f1']:.2f}"
    except (KeyError, TypeError):
        pass
    top = wl[0]["name"] if wl else "Run the pipeline"
    growth = f"Flood score {wl[0]['flood_score']}/100, {wl[0]['flood_tier']}" if wl else ""
    n_high = sum(r["flood_tier"] == "High" for r in wl)
    years = f"{m['years'][0]} to {m['years'][-1]}" if m.get("years") else "2017 to 2025"
    cards = [("Lakes monitored", str(len(ZONES)), f"{n_high} in the high flood tier" if wl else "Himalaya and Andes"),
             ("Top of watch list", top, growth),
             ("Model F1 on unseen lakes", f1, "Higher is better, max 1.0"),
             ("Years of images", years, "Sentinel-2, 10 m pixels")]
    html = "".join(f'<div class="card"><div class="lbl">{a}</div><div class="val">{b}</div><div class="sub">{c}</div></div>'
                   for a, b, c in cards)
    return f'<div class="cards">{html}</div>'


def world_map():
    wl = {r["zone"]: r for r in read_csv("report_card.csv")}
    lat, lon, text, size, color = [], [], [], [], []
    for z in ZONES:
        r = wl.get(z["id"])
        sc = float(r["flood_score"]) if r else 0.0
        lat.append(z["lat"]); lon.append(z["lon"])
        size.append(10 + sc / 4); color.append(sc)
        extra = (f"<br>Flood tier: {r['flood_tier']} ({sc:.0f}/100)<br>Growth: {float(r['growth_pct_per_year']):+.1f}%/yr"
                 f"<br>{r['flags']}") if r else ""
        text.append(f"<b>{z['name']}</b><br>{z['country']}{extra}<br>Downstream: {z['downstream']}")
    fig = go.Figure(go.Scattergeo(lat=lat, lon=lon, text=text, hoverinfo="text", mode="markers",
                                  marker=dict(size=size, color=color, colorscale=[[0, "#B5D4F4"], [0.5, ICE], [1, ALERT]],
                                              line=dict(width=1, color="white"),
                                              colorbar=dict(title="Score", thickness=12), cmin=0, cmax=100)))
    fig.update_geos(projection_type="natural earth", showcountries=True, countrycolor="#B4B2A9",
                    showland=True, landcolor="#F1EFE8", showocean=True, oceancolor="#E6F1FB", bgcolor="rgba(0,0,0,0)")
    return _layout(fig, 420)


WATCH_HEADERS = ["Rank", "Lake", "Country", "Flood tier", "Score", "Area (ha)", "Growth (%/yr)",
                 "Volume (M m³)", "Water supply concern", "Flags"]


def watch_rows():
    rows = read_csv("report_card.csv")
    if not rows:
        return [["", "Run run_all.py to build the watch list"] + [""] * 8]
    f = lambda v, d: fmt(float(v), d) if v not in ("", "nan") else "n/a"
    return [[r["flood_rank"], r["name"], r["country"], r["flood_tier"], r["flood_score"], f(r["area_ha"], 1),
             f"{float(r['growth_pct_per_year']):+.1f}", f(r["volume_million_m3"], 1), r["water_supply_concern"],
             r["flags"]] for r in rows]


METRICS = {"Lake area (ha)": "area_ha", "Estimated volume (million m³)": "volume_million_m3",
           "Worst-case peak flow (m³/s)": "peak_flow_m3s", "Glacier and snow ice in box (ha)": "ice_area_ha",
           "Distance from lake to glacier (m)": "lake_to_ice_m", "Water muddiness (red reflectance)": "water_red",
           "Ice on lake (%)": "ice_on_lake_pct", "Lake length (m)": "length_m"}


def metric_chart(labels, metric):
    key = METRICS[metric]
    rows = read_csv("lake_measurements.csv")
    fig = go.Figure()
    for lab in labels or []:
        zid = LABELS[lab]
        pts = [(int(r["year"]), float(r[key])) for r in rows
               if r["zone"] == zid and r["reliable"] == "True" and r[key] not in ("", "nan")]
        if pts:
            fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="lines+markers", name=lab))
    fig.update_layout(xaxis_title="Year", yaxis_title=metric, legend=dict(orientation="h", y=-0.25))
    return _layout(fig, 420)


def area_chart(zid, year=None):
    s = series(zid)
    fig = go.Figure()
    if s:
        good = [p for p in s if p[2]]; bad = [p for p in s if not p[2]]
        fig.add_trace(go.Scatter(x=[p[0] for p in good], y=[p[1] for p in good], mode="lines+markers", name="Clear years",
                                 line=dict(color=ICE, width=3), marker=dict(size=8)))
        if bad:
            fig.add_trace(go.Scatter(x=[p[0] for p in bad], y=[p[1] for p in bad], mode="markers", name="Too cloudy, not used",
                                     marker=dict(symbol="x", size=10, color=ALERT)))
        if year:
            fig.add_vline(x=year, line_dash="dash", line_color="#888780")
    fig.update_layout(xaxis_title="Year", yaxis_title="Lake area (hectares)", legend=dict(orientation="h", y=1.12))
    return _layout(fig, 320)


def explore(label, year):
    zid = LABELS[label]; z = ZONE_BY_ID[zid]; year = int(year)
    if CLF is None:
        return None, area_chart(zid), "No trained model yet. Run `python run_all.py` first."
    chip = get_chip(z, year)
    if chip is None:
        return None, area_chart(zid, year), f"No clear Sentinel-2 image for **{z['name']}** in {year}. Try another year."
    static = get_static(z)
    lake, valid, water = run_model(chip, static)
    m = measure(chip, static, lake, water, valid)
    imgs = [(viz.rgb(chip["bands"]), f"Satellite photo, {chip['date']}"),
            (viz.overlay_mask(chip["bands"], lake), "Lake found by the model")]
    card = next((c for c in read_csv("report_card.csv") if c["zone"] == zid), None)
    tier = f"  \n**Flood screening tier:** {card['flood_tier']} ({card['flood_score']}/100)  \n**Flags:** {card['flags']}" if card else ""
    info = (f"### {z['name']}\n{z['country']}. Image {chip['date']}, cloud {1 - valid.mean():.0%}.  \n"
            f"**Downstream:** {z['downstream']}{tier}\n\n" + measure_md(m))
    return imgs, area_chart(zid, year), info


def check_any(lat, lon, season, year_a, year_b):
    if args.synthetic:
        return None, "Live check needs real data. Run the app without `--synthetic`."
    if CLF is None:
        return None, "No trained model yet. Run `python run_all.py` first."
    try:
        lat, lon = float(lat), float(lon)
        assert -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, AssertionError):
        return None, "Enter a latitude between -90 and 90 and a longitude between -180 and 180."
    months = {"Jun-Sep (southern dry season)": [6, 7, 8, 9], "Sep-Nov (after monsoon)": [9, 10, 11],
              "Jul-Sep (northern summer)": [7, 8, 9]}[season]
    z = dict(id=f"custom_{lat:.3f}_{lon:.3f}", name="Your lake", country="", lat=lat, lon=lon,
             months=months, split="custom", downstream="")
    try:
        static = D.get_static(z, args.cache)
    except Exception as e:
        return None, f"Couldn't download map data for that spot: {e}"
    out, areas = [], []
    for y in sorted({int(year_a), int(year_b)}):
        try:
            c = D.get_chip(z, y, args.cache)
        except Exception as e:
            areas.append((y, None, f"download failed ({e})")); continue
        if c is None:
            areas.append((y, None, "no clear image in that season")); continue
        lake, valid, water = run_model(c, static)
        m = measure(c, static, lake, water, valid)
        out.append((viz.overlay_mask(c["bands"], lake), f"{c['date']}: {m['area_ha']:.1f} ha"))
        areas.append((y, m, f"{c['date']}, cloud {1 - valid.mean():.0%}"))
    got = [(y, m) for y, m, _ in areas if m is not None]
    lines = [f"**{y}:** {n}" for y, m, n in areas if m is None]
    if len(got) == 2:
        (y1, a), (y2, b) = got
        rows = [("Lake area (ha)", "area_ha", 1), ("Est. volume (million m³)", "volume_million_m3", 2),
                ("Worst-case peak flow (m³/s)", "peak_flow_m3s", 0), ("Glacier/snow ice in box (ha)", "ice_area_ha", 1),
                ("Distance to glacier ice (m)", "lake_to_ice_m", 0), ("Water red reflectance", "water_red", 3)]
        t = [f"| | {y1} | {y2} | Change |", "|---|---|---|---|"]
        for label, k, d in rows:
            ch = b[k] - a[k] if (a[k] == a[k] and b[k] == b[k]) else float("nan")
            t.append(f"| {label} | {fmt(a[k], d)} | {fmt(b[k], d)} | {'n/a' if ch != ch else f'{ch:+,.{d}f}'} |")
        t.append(f"| Water colour | {a['turbidity']} | {b['turbidity']} | |")
        lines.append("\n".join(t))
        if a["area_ha"] > 0:
            pct = 100 * (b["area_ha"] - a["area_ha"]) / a["area_ha"]
            verdict = ("growing, so flood risk is rising" if pct > 10 else
                       "shrinking, so check for drought or drainage" if pct < -10 else "roughly stable")
            lines.append(f"\n### The lake is {verdict} ({pct:+.0f}% area)")
    elif got:
        y, m = got[0]
        lines.append(f"**{y}:**\n\n" + measure_md(m))
    return out, "\n\n".join(lines)


# ------------------------------------------------------------------ layout
CSS = """
.gradio-container {max-width: 1150px !important; margin: auto;}
.hero {padding: 28px 28px 22px; border-radius: 16px; background: #0C447C; margin-bottom: 8px;}
.hero h1 {color: #ffffff !important; font-size: 32px; margin: 0 0 6px; font-weight: 600;}
.hero p {color: #E6F1FB !important; font-size: 16px; margin: 0; max-width: 780px; line-height: 1.6;}
.hero .tag {display: inline-block; background: rgba(255,255,255,0.15); color: #ffffff; padding: 3px 10px; border-radius: 99px; font-size: 12px; margin-bottom: 12px;}
.cards {display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 6px 0 4px;}
.card {border: 1px solid var(--border-color-primary); border-radius: 12px; padding: 14px 16px; background: var(--background-fill-primary);}
.card .lbl {font-size: 13px; color: var(--body-text-color-subdued);}
.card .val {font-size: 22px; font-weight: 600; margin-top: 4px; color: var(--body-text-color);}
.card .sub {font-size: 12px; color: var(--body-text-color-subdued); margin-top: 2px;}
.foot {font-size: 12px; color: var(--body-text-color-subdued); text-align: center; padding: 10px;}
"""
THEME = gr.themes.Soft(primary_hue="blue", secondary_hue="sky", neutral_hue="slate",
                       font=[gr.themes.GoogleFont("Inter"), "sans-serif"])

HERO = """<div class="hero"><span class="tag">Veritas AI Hackathon 2026, AI + Climate</span>
<h1>Glacier Lake Watch</h1>
<p>Glacial lakes can burst and flood the valleys below them, and in dry years they can shrink and stop supplying water.
This tool finds glacial lakes in free satellite images, measures a dozen things about each one every year, and builds a
report card for flood risk, drought and glacier retreat.</p></div>"""

HOW = """
### How it works
1. **Satellite images.** For each lake and year, the app finds the clearest Sentinel-2 image in the free Earth Search archive on AWS. Nobody has to upload anything.
2. **AI water map.** A gradient boosted model checks every 10 m pixel and decides if it's lake water. It learned from ESA WorldCover water labels on 6 Himalayan lakes.
3. **Fair test.** We tested it on 6 lakes it never saw, including 3 on a different continent (Peru), and compared it with simple baselines.
4. **Many measurements from one outline.** Each year we measure area, shape, water colour (muddy glacier water vs clear), ice on the lake, glacier ice nearby and distance to it, lake elevation, and the valley drop below. From area we estimate volume and a worst-case outburst flood peak (Huggel et al. 2002 formulas, rough).
5. **Report card for different uses.**
   - *Outburst floods:* a 0 to 100 screening score from volume, growth, valley drop and glacier contact.
   - *Drought and water supply:* shrinking lakes and dry years below the lake's own trend.
   - *Already drained:* sudden drops that may mean an outburst happened.
   - *Glacier retreat and water quality:* ice area trend and water colour.

Full results, baselines and failure cases are in `results/RESULTS.md` in the GitHub repo.

**This is a student prototype, not an official warning system.** Real hazard decisions also depend on the dam type, ice above the lake, and who lives downstream.
"""

GR6 = int(gr.__version__.split(".")[0]) >= 6
with gr.Blocks(title="Glacier Lake Watch", **({} if GR6 else dict(theme=THEME, css=CSS))) as demo:
    gr.HTML(HERO)
    gr.HTML(stat_cards())
    if CLF is None:
        gr.Markdown("> No trained model found in `results/`. Run `python run_all.py` (or the Colab notebook) first.")
    with gr.Tabs():
        with gr.Tab("Watch list"):
            gr.Markdown("Bigger, redder dots have a higher flood screening score. Hover over a dot for details.")
            gr.Plot(world_map(), show_label=False)
            gr.Dataframe(headers=WATCH_HEADERS, value=watch_rows(), interactive=False, wrap=True)
            gr.Markdown("**Flood score** (0 to 100) mixes lake volume, growth, how far the valley drops below the lake, and whether the lake "
                        "touches glacier ice. **Water supply concern** rises when a lake keeps shrinking or has dry years. "
                        "A **sudden drop** can mean the lake already burst, like South Lhonak in 2023.")
        with gr.Tab("Compare lakes"):
            gr.Markdown("Pick lakes and a measurement to see how they changed every year. Only clear-sky years are shown.")
            with gr.Row():
                cl = gr.Dropdown(list(LABELS), value=list(LABELS)[:3], multiselect=True, label="Lakes", scale=3)
                cm = gr.Dropdown(list(METRICS), value=list(METRICS)[0], label="Measurement", scale=2)
            cplot = gr.Plot(show_label=False)
            cl.change(metric_chart, [cl, cm], cplot); cm.change(metric_chart, [cl, cm], cplot)
            demo.load(metric_chart, [cl, cm], cplot)
        with gr.Tab("Explore a lake"):
            with gr.Row():
                dd = gr.Dropdown(list(LABELS), value=list(LABELS)[0], label="Lake", scale=3)
                yr = gr.Slider(2017, 2025, value=2025, step=1, label="Year", scale=2)
            with gr.Row():
                with gr.Column(scale=3):
                    gal = gr.Gallery(columns=2, height=380, show_label=False, object_fit="contain")
                with gr.Column(scale=2):
                    md = gr.Markdown()
            plot = gr.Plot(show_label=False)
            dd.change(explore, [dd, yr], [gal, plot, md])
            yr.release(explore, [dd, yr], [gal, plot, md])
            demo.load(explore, [dd, yr], [gal, plot, md])
        with gr.Tab("Check any lake on Earth"):
            gr.Markdown("Type the coordinates of any glacial lake. The app downloads two satellite images live and measures how much the lake changed. It takes about 30 seconds.")
            with gr.Row():
                la = gr.Textbox(label="Latitude", value="58.42")
                lo = gr.Textbox(label="Longitude", value="-134.55")
                se = gr.Dropdown(["Jun-Sep (southern dry season)", "Sep-Nov (after monsoon)", "Jul-Sep (northern summer)"],
                                 value="Jul-Sep (northern summer)", label="Season")
            with gr.Row():
                ya = gr.Slider(2017, 2025, value=2017, step=1, label="First year")
                yb = gr.Slider(2017, 2025, value=2025, step=1, label="Second year")
            gr.Examples([["58.42", "-134.55", "Jul-Sep (northern summer)", 2017, 2025],
                         ["27.861", "86.474", "Sep-Nov (after monsoon)", 2017, 2025],
                         ["-9.398", "-77.38", "Jun-Sep (southern dry season)", 2017, 2025]],
                        inputs=[la, lo, se, ya, yb],
                        label="Try one: Mendenhall Lake (Alaska), Tsho Rolpa (Nepal), Palcacocha (Peru)")
            go2 = gr.Button("Measure change", variant="primary", size="lg")
            with gr.Row():
                with gr.Column(scale=3):
                    gal2 = gr.Gallery(columns=2, height=380, show_label=False, object_fit="contain")
                with gr.Column(scale=2):
                    md2 = gr.Markdown()
            go2.click(check_any, [la, lo, se, ya, yb], [gal2, md2])
        with gr.Tab("How it works"):
            gr.Markdown(HOW)
    gr.HTML('<div class="foot">Data: ESA Sentinel-2 and WorldCover, Copernicus DEM, via AWS Open Data. Student prototype, not an official hazard warning.</div>')

if __name__ == "__main__":
    demo.launch(share=args.share, **(dict(theme=THEME, css=CSS) if GR6 else {}))
