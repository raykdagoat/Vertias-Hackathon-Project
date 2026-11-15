"""Pictures for the write-up, the demo and the video."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def rgb(bands, gain=3.0):
    b, g, r = bands[0], bands[1], bands[2]
    img = np.stack([r, g, b], -1) * gain
    return np.clip(np.nan_to_num(img), 0, 1)


def overlay_mask(bands, mask, color=(0.1, 0.6, 1.0), alpha=0.55):
    img = rgb(bands).copy()
    img[mask] = (1 - alpha) * img[mask] + alpha * np.array(color)
    return img


def error_map(bands, pred, truth, valid):
    """Grey image; cyan = correct water, red = false alarm, yellow = missed water."""
    base = rgb(bands).mean(-1, keepdims=True).repeat(3, -1) * 0.8
    tp = pred & truth & valid; fp = pred & ~truth & valid; fn = ~pred & truth & valid
    base[tp] = (0.0, 0.85, 0.9)
    base[fp] = (0.95, 0.15, 0.15)
    base[fn] = (1.0, 0.85, 0.0)
    base[~valid] = (0.3, 0.3, 0.3)
    return base


def save_error_figure(path, title, bands, preds, truth, valid):
    """preds: {name: mask}. One panel for the photo, one per method."""
    n = 1 + len(preds)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.6))
    axes[0].imshow(rgb(bands)); axes[0].set_title("Satellite photo"); axes[0].axis("off")
    for ax, (name, p) in zip(axes[1:], preds.items()):
        ax.imshow(error_map(bands, p, truth, valid)); ax.set_title(name); ax.axis("off")
    fig.suptitle(title + "\ncyan = correct water, red = false alarm, yellow = missed water, grey = cloud",
                 fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def save_timeseries_figure(path, series, names, highlight=None):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for zid, pts in series.items():
        if not pts:
            continue
        ys, ar = zip(*pts)
        lw = 2.5 if highlight and zid in highlight else 1.2
        ax.plot(ys, ar, marker="o", lw=lw, label=names.get(zid, zid))
    ax.set_xlabel("Year"); ax.set_ylabel("Main lake area (hectares)")
    ax.set_title("Glacial lake area measured by our model, one image per year")
    ax.legend(fontsize=7, ncol=2); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def save_metric_bars(path, table, group):
    names = list(table.keys())
    f1 = [table[n]["f1"] for n in names]; rec = [table[n]["recall"] for n in names]
    prec = [table[n]["precision"] for n in names]
    x = np.arange(len(names)); w = 0.27
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.bar(x - w, rec, w, label="Recall (caught water)")
    ax.bar(x, prec, w, label="Precision (no false alarms)")
    ax.bar(x + w, f1, w, label="F1")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8); ax.set_ylim(0, 1)
    ax.set_title(f"Water detection on unseen zones: {group}"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def save_before_after(path, title, chip_a, chip_b, mask_a, mask_b):
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.8))
    for ax, c, m in [(axes[0], chip_a, mask_a), (axes[1], chip_b, mask_b)]:
        ax.imshow(overlay_mask(c["bands"], m)); ax.axis("off")
        ax.set_title(f"{c['date']}  |  {m.sum() * 0.01:.1f} ha")
    fig.suptitle(title); fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def save_multi_metric(path, measurements, names):
    """Four indicators over time for every lake."""
    panels = [("area_ha", "Lake area (ha)"), ("volume_million_m3", "Est. volume (million m3)"),
              ("ice_area_ha", "Glacier ice in box (ha)"), ("water_red", "Water muddiness (red reflectance)")]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (key, title) in zip(axes.ravel(), panels):
        for zid, rows in measurements.items():
            pts = [(r["year"], r[key]) for r in rows if r["reliable"] and np.isfinite(r[key])]
            if pts:
                ys, vs = zip(*pts)
                ax.plot(ys, vs, marker="o", ms=3, lw=1.2, label=names.get(zid, zid))
        ax.set_title(title, fontsize=10); ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=6, ncol=2)
    fig.suptitle("What the model measured each year (clear years only)")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)
