# Glacier Lake Watch

**Veritas AI International High School Hackathon 2026, AI + Climate track**

An AI tool that finds glacial lakes in free satellite images, measures how big each one is every year, and ranks which lakes are growing fastest. A regional hazard team can use the ranking to decide which lakes to check first.

> This project is a student prototype. It is not an official flood warning or hazard assessment.

## The problem

As glaciers melt, water collects behind loose piles of rock and ice at the glacier's end. These glacial lakes can burst without warning. That's called a glacial lake outburst flood (GLOF). In October 2023, South Lhonak Lake in Sikkim, India burst. The flood destroyed the Chungthang dam on the Teesta river and killed many people downstream. Millions of people across the Himalaya and the Andes live below lakes like this.

There are thousands of these lakes, and many are in places nobody can visit often. Field teams can only survey a few each year, so they need to know which lakes to look at first.

## 1. Who is it for?

**User:** a hazard analyst at a regional disaster agency. Examples are Nepal's Department of Hydrology and Meteorology, Bhutan's National Center for Hydrology and Meteorology, India's Sikkim State Disaster Management Authority, or Peru's national glacier authority (INAIGEM).

**The moment they reach for it:** every year after the monsoon (Himalaya) or in the dry season (Andes), when they plan which lakes get a field visit, a sensor, or a pumping project. The tool gives them a ranked watch list plus before and after images for each lake.

**The decision it supports:** "Which 3 lakes do we send the team to this season?"

## 2. What goes in, and what comes out?

**In:** the latitude and longitude of a lake, a season, and a year. The tool downloads a 4 km by 4 km Sentinel-2 satellite image for that spot by itself.

**Out:**
- a water map (which 10 m pixels are lake water)
- the lake's area in hectares for every year from 2017 to 2025
- a next-year area forecast
- a watch list ranked by growth in hectares per year, with a flag if the lake suddenly shrank (a sign it may already have burst)

The demo app (`app.py`) also has a "Check any lake on Earth" tab. You type any coordinates and it measures the change live.

## How it works

1. **Data.** For each lake and each year, we search the free Sentinel-2 archive and keep the image with the least cloud over our 4 km box. We read 6 color bands (blue, green, red, near infrared, and two shortwave infrared bands).
2. **Answer key.** ESA WorldCover 2021 is a global 10 m land cover map. Its "water" class is our label for training and testing.
3. **Inputs to the model.** The 6 bands, plus 3 indexes (NDWI, MNDWI, NDVI), brightness, and a cliff flag (slope over 25 degrees, from the Copernicus elevation map).
4. **Model.** A gradient boosted tree classifier (scikit-learn `HistGradientBoostingClassifier`). It decides for each pixel whether it's water.
5. **Lake area.** We keep the water patch closest to the lake's centre and count its pixels. One pixel is 0.01 hectares.
6. **Forecast and watch list.** We fit each lake's yearly areas and rank lakes by how fast they're growing.

## 3. Does it beat a simple baseline?

We compare 4 methods on lakes the model never saw:

| Method | What it is |
|---|---|
| Always land | The simplest guess. Most pixels aren't water, so this gets high accuracy but finds zero lakes. |
| NDWI threshold | The classic rule used in glacial lake papers: water if NDWI is above a cut-off. To be fair, we tuned the cut-off on the training lakes. |
| ESA scene class | The water class that ESA's own processing puts on every Sentinel-2 image. |
| Our model | The gradient boosted classifier. |

For the forecast, we use the persistence baseline from the brief: "next year's lake area = this year's." We train on earlier years and test on 2023, 2024, and 2025. Years are never shuffled.

### How we tested fairly

- **Training lakes (6, Himalaya):** Imja Tsho, Tsho Rolpa, Thulagi, Lower Barun (Nepal), Longbasaba (Tibet), Lugge Tsho (Bhutan).
- **Unseen Himalayan lakes (3):** South Lhonak (India), Raphstreng Tsho (Bhutan), Gepang Gath (India).
- **Unseen new continent (3, Andes):** Palcacocha, Paron, Laguna 513 (Peru).

The lakes are tens to thousands of kilometres apart, so test pixels never leak into training.

### Results

All results are in **[results/RESULTS.md](results/RESULTS.md)**, written automatically by `run_all.py` from the real run. The headline numbers are copied here:

| | Our model | Best baseline |
|---|---|---|
| F1, unseen Himalayan lakes | _fill in_ | _fill in (which one)_ |
| F1, Andes | _fill in_ | _fill in_ |
| Forecast error, persistence vs our best (ha) | _fill in_ | _fill in_ |

**Main takeaway:** _one sentence, filled in from the real results._

We report the results we actually got, including the weak ones.

## 4. Where does it fail?

`RESULTS.md` splits errors by terrain (shadow, snow and ice, steep slopes) and shows an error map for every test lake (red = false alarm, yellow = missed water). It also names the worst lake.

These are the failure cases we expected going in, and we checked each one against the results:

- **Mountain shadows.** Dark shadowed slopes look like water to simple rules. This is the classic NDWI false alarm.
- **Frozen or ice-covered lakes.** Ice is bright, so a frozen lake doesn't look like water. This is more likely in the Andes dry season, which is winter there.
- **Grey, muddy glacial water.** Water full of ground-up rock reflects more light, which lowers NDWI. Lakes in Peru are often this colour.
- **Label errors.** WorldCover is itself a model and it's not perfect. Some "errors" may be the label's fault, not ours.
- **Outburst floods break the forecast.** South Lhonak drained in October 2023. No trend line can predict a sudden collapse, so our forecast misses it. The watch list flags sudden drops for this reason.

## Make it your own: what we added

The brief has a land-use classification project (EuroSAT). We changed it in all three ways the brief suggests:

- **Our own user and setting:** a hazard team ranking dangerous glacial lakes, in the Himalaya and Andes, instead of general land use in Europe.
- **Our own data:** live Sentinel-2 chips, ESA WorldCover labels, and Copernicus DEM slope for 12 named lakes over 9 years. We don't use EuroSAT at all.
- **Our own questions:**
  - Does a model trained only on Himalayan lakes still work on a different continent (the Andes)?
  - Where does it fail (shadow, ice, steep slopes)?
  - Can lake area be forecast better than "same as last year"?

**A design decision we're proud of:** our first version used raw slope as an input. Then we realised the elevation map was made from 2011 to 2015 radar data, so the old lake outline is perfectly flat in it. A model fed raw slope would learn the *old* lake shape and hide new growth, which is the one thing we care about. We replaced it with a "cliff" flag (slope over 25 degrees) that only rules out steep rock, where a lake can't be now or later.

## Run it yourself

The easiest way is to open `notebooks/Glacier_Lake_Watch.ipynb` in Google Colab and click Runtime → Run all. You don't need a GPU.

```bash
pip install -r requirements.txt
python run_all.py            # real data, about 20-40 min the first time, cached after that
python app.py --share        # demo with a public link
python run_all.py --synthetic   # fake data, only to check the code works offline
```

```
glw/zones.py       the 12 lakes, train/test split, seasons
glw/data.py        downloads Sentinel-2, WorldCover and DEM chips from public cloud storage
glw/model.py       features, model, baselines, scoring, lake outline
glw/timeseries.py  forecast backtest and watch list
glw/viz.py         figures
glw/report.py      writes results/RESULTS.md
run_all.py         the whole pipeline
app.py             Gradio demo
```

## Limitations

- WorldCover is from 2021. We train and test on 2021 images (or the closest year) so the labels match the image.
- Lake area is not lake volume, and growth is not the only thing that makes a lake dangerous. The type of dam, steep ice above the lake, and how many people live downstream all matter. A real hazard team would combine our ranking with those.
- Forecast "truth" is our own model's measurement of later years, not a field survey.
- Cloudy years are skipped (we need at least 90% clear sky over the lake), so some lakes have gaps.
- Lake coordinates are approximate centres. Each 4 km box is wide enough to contain the lake.

## Citations and tools

**Data**
- Sentinel-2 Level-2A imagery, European Space Agency / Copernicus, accessed through the Earth Search STAC API by Element 84 on AWS Open Data: https://earth-search.aws.element84.com/v1 (licence: Copernicus open data).
- ESA WorldCover 10 m 2021 v200. Zanaga, D. et al. (2022), https://esa-worldcover.org (CC BY 4.0).
- Copernicus DEM GLO-30, ESA, on AWS Open Data: https://registry.opendata.aws/copernicus-dem/
- Lake locations and flood history from public sources about each lake (e.g. reporting on the October 2023 South Lhonak outburst).

**Methods**
- McFeeters, S. K. (1996). The use of the Normalized Difference Water Index (NDWI). *International Journal of Remote Sensing.*
- Xu, H. (2006). Modification of NDWI (MNDWI). *International Journal of Remote Sensing.*

**Libraries:** scikit-learn, NumPy, SciPy, rasterio / GDAL, pyproj, pystac-client, matplotlib, Gradio, Google Colab.

**AI tools used:** Claude (Anthropic) helped write and debug code and draft this write-up. Our team reviewed every part and can explain each step.

## Team

_Add names here._ All listed members contributed during the hackathon weekend (Nov 14 to 15, 2026).
