"""Download small image chips from free public cloud data.

Sources (all free, no account needed):
  * Sentinel-2 L2A surface reflectance, via the Earth Search STAC API (Element 84 / AWS)
  * ESA WorldCover 2021 v200 land cover map (used as our "answer key" for water)
  * Copernicus DEM GLO-30 elevation (used to compute slope)

We only read a 4 km x 4 km window from each file. Cloud-optimised GeoTIFFs let us
do that without downloading whole satellite tiles.
"""
import calendar
import math
import os

import numpy as np

CHIP_SIZE_M = 4000
RES_M = 10
STAC_URL = "https://earth-search.aws.element84.com/v1"
S2_ASSETS = ["blue", "green", "red", "nir", "swir16", "swir22"]  # B02 B03 B04 B08 B11 B12
SCL_CLOUD = {0, 1, 8, 9, 10}  # nodata, saturated, cloud medium, cloud high, cirrus

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="2",
    AWS_NO_SIGN_REQUEST="YES",
    VSI_CACHE="TRUE",
)


# ---------------------------------------------------------------- grid helpers
def chip_grid(lat, lon, size_m=CHIP_SIZE_M, res=RES_M):
    """A square 10 m grid in the local UTM zone, centred on (lat, lon)."""
    from pyproj import Transformer
    from rasterio.transform import from_origin

    utm_zone = int((lon + 180) // 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + utm_zone
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    half = size_m / 2
    n = int(size_m / res)
    return dict(crs=f"EPSG:{epsg}", transform=from_origin(x - half, y + half, res, res), width=n, height=n)


def bbox_lonlat(lat, lon, size_m=CHIP_SIZE_M, pad=1.2):
    dlat = (size_m / 2) * pad / 111_000
    dlon = dlat / max(math.cos(math.radians(lat)), 0.1)
    return [lon - dlon, lat - dlat, lon + dlon, lat + dlat]


def read_to_grid(href, grid, resampling="bilinear"):
    """Read one band of a remote GeoTIFF, warped onto our chip grid."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT

    rs = Resampling.nearest if resampling == "nearest" else Resampling.bilinear
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(href) as src:
            with WarpedVRT(src, crs=grid["crs"], transform=grid["transform"],
                           width=grid["width"], height=grid["height"], resampling=rs,
                           src_nodata=src.nodata if src.nodata is not None else 0, nodata=0) as vrt:
                return vrt.read(1).astype("float32")


def _read_tiles_merged(urls, grid, resampling):
    """Read several tiles onto one grid (for chips near a tile edge)."""
    out = None
    for u in urls:
        try:
            arr = read_to_grid(u, grid, resampling)
        except Exception as e:  # tile missing (e.g. ocean) or network hiccup
            print(f"    could not read {u.split('/')[-1]}: {e}")
            continue
        out = arr if out is None else np.where(out == 0, arr, out)
    return out


# ---------------------------------------------------------------- Sentinel-2
def _scale_offset(asset):
    rb = (asset.extra_fields.get("raster:bands") or [{}])[0]
    return float(rb.get("scale", 1e-4)), float(rb.get("offset", 0.0))


def search_scenes(lat, lon, year, months, max_cloud=50):
    from pystac_client import Client

    last_day = calendar.monthrange(year, months[-1])[1]
    dt = f"{year}-{months[0]:02d}-01/{year}-{months[-1]:02d}-{last_day}"
    client = Client.open(STAC_URL)
    search = client.search(collections=["sentinel-2-l2a"], bbox=bbox_lonlat(lat, lon), datetime=dt,
                           query={"eo:cloud_cover": {"lt": max_cloud}}, max_items=60)
    items = list(search.items())
    items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100))
    return items


def fetch_s2_chip(zone, year, n_candidates=4):
    """Best (least cloudy over our chip) Sentinel-2 image for one zone and year."""
    grid = chip_grid(zone["lat"], zone["lon"])
    items = search_scenes(zone["lat"], zone["lon"], year, zone["months"])
    if not items:
        return None
    best = None
    for it in items[:n_candidates]:
        try:
            scl = read_to_grid(it.assets["scl"].href, grid, "nearest")
        except Exception as e:
            print(f"    SCL read failed for {it.id}: {e}")
            continue
        clear = float(np.mean(~np.isin(scl, list(SCL_CLOUD))))
        if best is None or clear > best[1]:
            best = (it, clear, scl)
        if clear > 0.97:
            break
    if best is None:
        return None
    it, clear, scl = best
    bands = []
    for a in S2_ASSETS:
        dn = read_to_grid(it.assets[a].href, grid, "bilinear")
        scale, offset = _scale_offset(it.assets[a])
        refl = dn * scale + offset
        refl[dn == 0] = np.nan
        bands.append(refl)
    return dict(bands=np.stack(bands).astype("float32"), scl=scl.astype("uint8"),
                date=it.properties["datetime"][:10], item_id=it.id, clear_frac=clear)


# ---------------------------------------------------------------- labels + DEM
def _tile_corners(lat, lon, step):
    b = bbox_lonlat(lat, lon, pad=1.0)
    lats = sorted({math.floor(b[1] / step) * step, math.floor(b[3] / step) * step})
    lons = sorted({math.floor(b[0] / step) * step, math.floor(b[2] / step) * step})
    return [(la, lo) for la in lats for lo in lons]


def worldcover_urls(lat, lon):
    urls = []
    for la, lo in _tile_corners(lat, lon, 3):
        tag = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
        urls.append(f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                    f"ESA_WorldCover_10m_2021_v200_{tag}_Map.tif")
    return urls


def dem_urls(lat, lon):
    urls = []
    for la, lo in _tile_corners(lat, lon, 1):
        name = (f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_"
                f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM")
        urls.append(f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif")
    return urls


def fetch_static(zone):
    """WorldCover classes and slope (degrees) for a zone. These don't change by year."""
    grid = chip_grid(zone["lat"], zone["lon"])
    wc = _read_tiles_merged(worldcover_urls(zone["lat"], zone["lon"]), grid, "nearest")
    dem = _read_tiles_merged(dem_urls(zone["lat"], zone["lon"]), grid, "bilinear")
    if dem is None:
        slope = np.zeros((grid["height"], grid["width"]), "float32")
    else:
        gy, gx = np.gradient(dem, RES_M)
        slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
    if wc is None:
        wc = np.zeros_like(slope)
    return dict(worldcover=wc.astype("uint8"), slope=slope, dem=(dem if dem is not None else slope * 0))


# ---------------------------------------------------------------- caching
def cache_path(cache_dir, zone_id, year):
    return os.path.join(cache_dir, f"{zone_id}_{year}.npz")


def get_chip(zone, year, cache_dir="data/chips"):
    os.makedirs(cache_dir, exist_ok=True)
    p = cache_path(cache_dir, zone["id"], year)
    if os.path.exists(p):
        d = np.load(p, allow_pickle=True)
        if "missing" in d.files:
            return None
        return {k: (d[k].item() if d[k].ndim == 0 else d[k]) for k in d.files}
    chip = fetch_s2_chip(zone, year)
    if chip is None:
        np.savez_compressed(p, missing=True)
        return None
    np.savez_compressed(p, **chip)
    return chip


def get_static(zone, cache_dir="data/chips"):
    os.makedirs(cache_dir, exist_ok=True)
    p = os.path.join(cache_dir, f"{zone['id']}_static.npz")
    if os.path.exists(p):
        d = np.load(p)
        return {k: d[k] for k in d.files}
    s = fetch_static(zone)
    np.savez_compressed(p, **s)
    return s
