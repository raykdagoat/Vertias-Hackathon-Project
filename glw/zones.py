"""Watch zones: one 4 km x 4 km box centred on each known glacial lake.

Coordinates are approximate lake centres. The 4 km box is wide enough that a
small coordinate error still keeps the lake inside the box.

split:
  train          -> used to train the model (Himalaya)
  test_himalaya  -> held out, never seen in training (same mountain range)
  test_andes     -> held out, a different continent (our "new place" test)

months: the season we pull images from. We pick the season when snow cover and
clouds are lowest, so the lake surface is visible.
  Himalaya: after the monsoon (Sep to Oct, Nov only as a fallback)
  Peruvian Andes: dry season (Jun to Sep)
"""

HIMALAYA_MONTHS = [9, 10]        # Nov images had long shadows and fresh snow
HIMALAYA_FALLBACK = [11]         # only used if Sep-Oct has no usable image
ANDES_MONTHS = [6, 7, 8, 9]

ZONES = [
    # ---- training zones (Himalaya) ----
    dict(id="imja_tsho", name="Imja Tsho", country="Nepal", lat=27.898, lon=86.925,
         split="train", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Dingboche and Khumbu valley villages"),
    dict(id="tsho_rolpa", name="Tsho Rolpa", country="Nepal", lat=27.861, lon=86.474,
         split="train", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Rolwaling valley and Tamakoshi hydropower"),
    dict(id="thulagi", name="Thulagi Lake", country="Nepal", lat=28.486, lon=84.484,
         split="train", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Marsyangdi river valley"),
    dict(id="lower_barun", name="Lower Barun", country="Nepal", lat=27.797, lon=87.095,
         split="train", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Arun river valley"),
    dict(id="longbasaba", name="Longbasaba", country="China (Tibet)", lat=27.953, lon=88.079,
         split="train", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Pumqu / Arun river"),
    dict(id="lugge_tsho", name="Lugge Tsho", country="Bhutan", lat=28.094, lon=90.298,
         split="train", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Punatsangchhu river (1994 flood)"),
    # ---- held-out test zones, same range ----
    dict(id="south_lhonak", name="South Lhonak Lake", country="India (Sikkim)", lat=27.912, lon=88.197,
         split="test_himalaya", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Teesta river (burst in Oct 2023)"),
    dict(id="raphstreng", name="Raphstreng Tsho", country="Bhutan", lat=28.107, lon=90.245,
         split="test_himalaya", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Punatsangchhu river"),
    dict(id="gepang_gath", name="Gepang Gath", country="India (Himachal)", lat=32.517, lon=77.217, size_m=6000,
         split="test_himalaya", months=HIMALAYA_MONTHS, fallback_months=HIMALAYA_FALLBACK, downstream="Chandra river, Sissu"),
    # ---- held-out test zones, new continent ----
    dict(id="palcacocha", name="Laguna Palcacocha", country="Peru", lat=-9.398, lon=-77.380,
         split="test_andes", months=ANDES_MONTHS, downstream="Huaraz city (1941 flood)"),
    dict(id="paron", name="Laguna Paron", country="Peru", lat=-8.999, lon=-77.684,
         split="test_andes", months=ANDES_MONTHS, downstream="Caraz town"),
    dict(id="laguna_513", name="Laguna 513", country="Peru", lat=-9.212, lon=-77.547,
         split="test_andes", months=ANDES_MONTHS, downstream="Carhuaz (2010 flood)"),
]

ZONE_BY_ID = {z["id"]: z for z in ZONES}
LABEL_YEAR = 2021  # ESA WorldCover v200 labels are made from 2021 imagery
