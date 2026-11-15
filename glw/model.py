"""Features, the water model, the baselines, and the scoring code."""
import numpy as np
from scipy import ndimage

from .data import SCL_CLOUD

FEATURE_NAMES = ["blue", "green", "red", "nir", "swir16", "swir22",
                 "ndwi", "mndwi", "ndvi", "brightness", "cliff_gt25deg"]
WC_WATER, WC_SNOW = 80, 70
PIXEL_HA = 0.01  # one 10 m x 10 m pixel = 100 m2 = 0.01 hectares


def make_features(bands, slope):
    b, g, r, n, s1, s2 = bands
    eps = 1e-6
    ndwi = (g - n) / (g + n + eps)      # McFeeters NDWI: water is high
    mndwi = (g - s1) / (g + s1 + eps)   # modified NDWI: better for snow and shadow
    ndvi = (n - r) / (n + r + eps)
    bright = (b + g + r) / 3
    # Why not raw slope? The elevation map was made from 2011-2015 radar data, so the
    # lake surface back then is perfectly flat in it. A model fed raw slope learns
    # "water = the old flat lake outline" and would hide new growth. A cliff flag only
    # rules out steep rock (>25 deg), where a lake can never be, now or later.
    cliff = (np.nan_to_num(slope) > 25).astype("float32")
    return np.stack([b, g, r, n, s1, s2, ndwi, mndwi, ndvi, bright, cliff]).astype("float32")


def valid_mask(chip):
    """Pixels we can score: real data and not cloud."""
    ok = np.all(np.isfinite(chip["bands"]), axis=0)
    ok &= ~np.isin(chip["scl"], list(SCL_CLOUD))
    return ok


def to_table(F, mask):
    """(features, H, W) -> (n_pixels, features) for pixels in mask."""
    return F[:, mask].T


# ---------------------------------------------------------------- baselines
def baseline_all_land(F):
    return np.zeros(F.shape[1:], bool)


def baseline_ndwi(F, threshold):
    return F[FEATURE_NAMES.index("ndwi")] > threshold


def baseline_scl(chip):
    """ESA's own built-in scene classification says 'water' (class 6)."""
    return chip["scl"] == 6


def tune_ndwi_threshold(X, y):
    """Pick the NDWI cut-off that gives the best F1 on TRAINING pixels only."""
    ndwi = X[:, FEATURE_NAMES.index("ndwi")]
    best_t, best_f1 = 0.0, -1
    for t in np.arange(-0.3, 0.71, 0.02):
        p = ndwi > t
        tp = np.sum(p & y); fp = np.sum(p & ~y); fn = np.sum(~p & y)
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1
    return round(best_t, 2)


# ---------------------------------------------------------------- the model
def train_model(X, y, seed=0):
    from sklearn.ensemble import HistGradientBoostingClassifier

    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                         l2_regularization=1.0, random_state=seed)
    clf.fit(X, y)
    return clf


def predict_mask(clf, F, mask, threshold=0.5):
    out = np.zeros(F.shape[1:], bool)
    if mask.any():
        out[mask] = clf.predict_proba(to_table(F, mask))[:, 1] >= threshold
    return out


# ---------------------------------------------------------------- scoring
def confusion(pred, truth, mask):
    p, t = pred[mask], truth[mask]
    return dict(tp=int(np.sum(p & t)), fp=int(np.sum(p & ~t)), fn=int(np.sum(~p & t)), tn=int(np.sum(~p & ~t)))


def scores(c):
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    n = max(tp + fp + fn + tn, 1)
    return dict(
        accuracy=(tp + tn) / n,
        recall=tp / max(tp + fn, 1),        # share of real water pixels we caught
        precision=tp / max(tp + fp, 1),     # share of our "water" that really is water
        f1=2 * tp / max(2 * tp + fp + fn, 1),
        iou=tp / max(tp + fp + fn, 1),
        missed_water_ha=fn * PIXEL_HA,      # false negatives, in hectares
        false_water_ha=fp * PIXEL_HA,       # false positives (false alarms), in hectares
    )


def add_conf(a, b):
    return {k: a.get(k, 0) + b[k] for k in b}


# ---------------------------------------------------------------- lake area
def main_lake(mask, min_pixels=20):
    """The connected water patch closest to the chip centre (our target lake)."""
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros_like(mask)
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    h, w = mask.shape
    cy, cx = h / 2, w / 2
    best, best_d = 0, 1e18
    centers = ndimage.center_of_mass(mask, lab, range(1, n + 1))
    for i, (sz, (y, x)) in enumerate(zip(sizes, centers), start=1):
        if sz < min_pixels:
            continue
        d = (y - cy) ** 2 + (x - cx) ** 2
        # prefer big lakes near the centre
        d = d / np.sqrt(sz)
        if d < best_d:
            best, best_d = i, d
    return lab == best if best else np.zeros_like(mask)
