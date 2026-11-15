"""Everything we measure about a lake from one satellite image.

The AI model gives us the lake outline. From that outline plus the image and the
elevation map we measure:

  size and shape    area, perimeter, length, elongation, shoreline complexity
  water             colour / muddiness (turbidity), ice cover on the lake
  surroundings      glacier ice area in the box, distance from lake to the glacier
  terrain           lake elevation, how far the valley drops below the lake
  flood potential   estimated water volume and worst-case outburst peak flow

Volume and peak flow use published rule-of-thumb formulas for glacial lakes
(Huggel et al. 2002). They are rough estimates, often off by 2x or more, and are
used for ranking lakes against each other, not as exact numbers.
"""
import numpy as np
from scipy import ndimage

RES = 10.0  # metres per pixel


def ice_mask(bands, water, valid):
    """Snow and glacier ice: bright in green, dark in shortwave infrared (NDSI rule)."""
    g, n, s1 = bands[1], bands[3], bands[4]
    ndsi = (g - s1) / (g + s1 + 1e-6)
    return (ndsi > 0.4) & (n > 0.11) & ~water & valid


def lake_volume_m3(area_m2):
    """Huggel et al. (2002): V = 0.104 * A^1.42 (A in m2, V in m3)."""
    return 0.104 * area_m2 ** 1.42 if area_m2 > 0 else 0.0


def peak_flow_m3s(volume_m3):
    """Huggel et al. (2002), moraine-dam breach worst case: Qmax = 0.00077 * V^1.017."""
    return 0.00077 * volume_m3 ** 1.017 if volume_m3 > 0 else 0.0


def shape(lake):
    area_px = int(lake.sum())
    if area_px < 3:
        return dict(perimeter_m=0.0, length_m=0.0, elongation=np.nan, shoreline_index=np.nan)
    edge = lake & ~ndimage.binary_erosion(lake)
    perim = edge.sum() * RES
    ys, xs = np.nonzero(lake)
    cov = np.cov(np.vstack([xs, ys]))
    ev = np.sort(np.linalg.eigvalsh(cov))[::-1]
    major = 4 * np.sqrt(max(ev[0], 1e-9)) * RES
    minor = 4 * np.sqrt(max(ev[1], 1e-9)) * RES
    area_m2 = area_px * RES * RES
    return dict(perimeter_m=float(perim), length_m=float(major), elongation=float(major / max(minor, RES)),
                shoreline_index=float(perim / (2 * np.sqrt(np.pi * area_m2))))


def measure(chip, static, lake, water, valid, lake_region=None):
    """All measurements for one lake in one image. Returns a flat dict."""
    bands = chip["bands"]
    area_m2 = float(lake.sum() * RES * RES)
    out = dict(area_ha=area_m2 / 1e4)
    out.update(shape(lake))

    # water colour: average reflectance inside the lake, 1 pixel in from the shore
    inner = ndimage.binary_erosion(lake) & valid
    if inner.sum() >= 5:
        red, green, blue = (float(np.nanmean(bands[i][inner])) for i in (2, 1, 0))
        out.update(water_red=red, water_green=green, water_blue=blue)
        out["turbidity"] = "clear" if red < 0.03 else ("milky" if red < 0.07 else "very muddy")
    else:
        out.update(water_red=np.nan, water_green=np.nan, water_blue=np.nan, turbidity="unknown")

    # ice: on the lake (frozen surface) and glaciers in the 4 km box
    ice = ice_mask(bands, water, valid)
    if lake_region is None:
        lake_region = ndimage.binary_dilation(lake, iterations=3)
    region_ok = lake_region & valid
    out["ice_on_lake_pct"] = float(100 * (ice & region_ok).sum() / max(region_ok.sum(), 1))
    out["ice_area_ha"] = float(ice.sum() * RES * RES / 1e4)
    if lake.any() and ice.any():
        dist = ndimage.distance_transform_edt(~ice) * RES
        out["lake_to_ice_m"] = float(dist[lake].min())
    else:
        out["lake_to_ice_m"] = np.nan
    out["glacier_contact"] = bool(out["lake_to_ice_m"] <= 50) if np.isfinite(out["lake_to_ice_m"]) else False

    # terrain from the elevation map
    dem = static.get("dem")
    if dem is not None and lake.any() and np.nanmax(dem) > 0:
        lake_elev = float(np.nanmedian(dem[lake]))
        good = dem > 0
        out["lake_elev_m"] = lake_elev
        out["valley_drop_m"] = float(lake_elev - np.nanmin(dem[good])) if good.any() else np.nan
    else:
        out["lake_elev_m"] = np.nan; out["valley_drop_m"] = np.nan

    # flood potential
    vol = lake_volume_m3(area_m2)
    out["volume_million_m3"] = vol / 1e6
    out["peak_flow_m3s"] = peak_flow_m3s(vol)
    return out
