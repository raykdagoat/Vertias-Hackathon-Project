"""FAKE data for testing the code offline. Never used for reported results.

Makes chips with a lake that grows each year, a mountain shadow, and a snow
patch, so every step of the pipeline can be checked without internet.
"""
import numpy as np

N = 400


def _scene(seed, year, lake_scale, south=False):
    rng = np.random.default_rng(seed * 1000 + year)
    yy, xx = np.mgrid[0:N, 0:N]
    cy, cx = N / 2 + rng.normal(0, 3), N / 2 + rng.normal(0, 3)
    r = 25 + 4 * lake_scale
    lake = ((yy - cy) / (r * 0.6)) ** 2 + ((xx - cx) / r) ** 2 < 1
    shadow = (xx < 90) & (yy > 60)
    snow = (yy < 70)
    land = np.ones((6, N, N), "float32") * np.array([0.08, 0.10, 0.12, 0.22, 0.25, 0.18])[:, None, None]
    land += rng.normal(0, 0.02, land.shape).astype("float32")
    water = np.array([0.06, 0.08, 0.05, 0.02, 0.01, 0.01])[:, None]
    shade = np.array([0.03, 0.03, 0.03, 0.035, 0.03, 0.02])[:, None]
    snowv = np.array([0.8, 0.8, 0.78, 0.7, 0.1, 0.08])[:, None]
    if south:  # a different "continent": turbid, brighter lakes
        water = water + np.array([0.04, 0.06, 0.05, 0.03, 0.01, 0.0])[:, None]
    bands = land.copy()
    bands[:, snow] = snowv + rng.normal(0, 0.03, (6, snow.sum()))
    bands[:, shadow] = shade + rng.normal(0, 0.008, (6, shadow.sum()))
    bands[:, lake] = water + rng.normal(0, 0.01, (6, lake.sum()))
    bands = np.clip(bands, 0.001, 1).astype("float32")
    scl = np.full((N, N), 5, "uint8"); scl[lake] = 6; scl[shadow] = 2; scl[snow] = 11
    cloud = (rng.random() < 0.3)
    if cloud:
        c = ((yy - 300) ** 2 + (xx - 320) ** 2) < 40 ** 2
        scl[c] = 9
    return bands, scl, lake, snow


def make_chip(zone, year, idx):
    scale = (year - 2017) * (1.0 + 0.3 * (idx % 3))
    if zone["id"] == "south_lhonak" and year >= 2024:
        scale *= 0.4  # a sudden drain, like a real outburst
    bands, scl, _, _ = _scene(idx, year, scale, south=zone["split"] == "test_andes")
    return dict(bands=bands, scl=scl, date=f"{year}-10-01", item_id=f"SYNTH_{zone['id']}_{year}",
                clear_frac=float(np.mean(scl != 9)))


def make_static(zone, idx):
    _, _, lake, snow = _scene(idx, 2021, (2021 - 2017) * (1.0 + 0.3 * (idx % 3)),
                              south=zone["split"] == "test_andes")
    wc = np.full(lake.shape, 60, "uint8"); wc[snow] = 70; wc[lake] = 80
    rng = np.random.default_rng(idx)
    yy, _ = np.mgrid[0:N, 0:N]
    noise = rng.random(lake.shape) < 0.01  # label noise, like the real map
    wc[noise & lake] = 60
    yy, xx = np.mgrid[0:N, 0:N]
    slope = np.full(lake.shape, 35.0, "float32")
    slope[(abs(yy - N / 2) < 110) & (abs(xx - N / 2) < 150)] = 8.0  # valley floor and glacier tongue
    dem = (4200 + 3 * (N - yy) + 40 * idx).astype("float32")  # valley drops toward the bottom of the box
    return dict(worldcover=wc, slope=slope, dem=dem)
