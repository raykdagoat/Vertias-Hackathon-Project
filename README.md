# Glacier Lake Watch

**Track:** Climate (Veritas AI International High School Hackathon 2026)  
**Team:** _your name(s)_

An AI tool that finds glacial lakes in free satellite images, measures a dozen things about each lake every year, and builds a report card for several uses: outburst flood risk, drought and water supply, lakes that already drained, glacier retreat, and water quality. A regional hazard team can use the ranking to decide which lakes to check first.

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

**Out, for every lake and every year from 2017 to 2025:**
- a water map (which 10 m pixels are lake water), made by the AI model
- size and shape: area, perimeter, length, elongation, shoreline complexity
- water: colour and muddiness (glacier-fed lakes are milky), percent of the lake covered by ice
- surroundings: glacier and snow ice in the 4 km box, distance from the lake to the nearest ice (a lake touching a glacier can be hit by falling ice)
- terrain: lake elevation and how far the valley drops below it
- flood potential: estimated water volume and a worst-case outburst peak flow, from published formulas (Huggel et al. 2002)

**Then, per lake, a report card:**
- **Outburst flood screening:** a 0 to 100 score from volume, growth, valley drop and glacier contact, with High, Medium and Low tiers
- **Drought and water supply:** shrinking lakes, change in stored water, and dry years well below the lake's own trend
- **Already drained:** sudden drops that may mean an outburst happened (South Lhonak, 2023)
- **Glacier retreat:** trend in ice area around the lake
- **Next-year area forecast** compared with persistence

**Web app:** `app.py` is a web app with five tabs. **Watch list** has a world map coloured by flood score and the full report card. **Compare lakes** charts any measurement over the years for several lakes at once. **Explore a lake** lets you slide through the years and watch the lake outline grow. **Check any lake on Earth** lets you type any coordinates and measures the change live from free satellite data, so users never have to upload images. **How it works** explains the method. It runs locally with `python app.py` (after `run_all.py`) and opens at http://127.0.0.1:7860.

## How it works

1. **Data.** For each lake and each year, we search the free Sentinel-2 archive and keep the image with the least cloud over our 4 km box. We read 6 color bands (blue, green, red, near infrared, and two shortwave infrared bands).
2. **Answer key.** ESA WorldCover 2021 is a global 10 m land cover map. Its "water" class is our label for training and testing.
3. **Inputs to the model.** The 6 bands, plus 3 indexes (NDWI, MNDWI, NDVI), brightness, and a cliff flag (slope over 25 degrees, from the Copernicus elevation map).
4. **Model.** A gradient boosted tree classifier (scikit-learn `HistGradientBoostingClassifier`). It decides for each pixel whether it's water.
5. **Lake outline.** We keep the water patch closest to the lake's centre. One pixel is 0.01 hectares.
6. **Measurements** (`glw/measure.py`). Shape comes from the outline. Water colour is the average reflectance inside the lake. Ice uses the standard snow index (NDSI over 0.4). Distance to ice uses a distance transform. Elevation and valley drop come from the Copernicus elevation map. Volume uses V = 0.104 x A^1.42 and peak flow uses Q = 0.00077 x V^1.017 (Huggel et al. 2002).
7. **Report card** (`glw/assess.py`). Trends are straight-line fits over clear years. The flood score is a simple weighted rank so anyone can check how it was made.

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

### Results (real data, lakes the model never saw)

Full tables, error maps and charts: **[results/RESULTS.md](results/RESULTS.md)**. Answer key: ESA WorldCover 2021 water class. Scores are per 10 m pixel.

| Method | F1, unseen Himalayan lakes | F1, Andes (new continent) |
|---|---|---|
| Always land (simplest guess) | 0.000 | 0.000 |
| ESA's built-in water layer | 0.850 | 0.904 |
| NDWI > 0.2 (classic rule, tuned on training lakes) | **0.855** | **0.941** |
| Our model, image bands only | 0.808 | 0.935 |
| Our model, bands + ESA flags (main model) | 0.766 | 0.926 |

| Forecast of next year's lake area (2023 to 2025) | Mean error |
|---|---|
| Persistence ("same as last year") | **17.9 ha** |
| Linear trend | 19.3 ha |
| Damped trend | 18.1 ha |

**Main takeaway:** the AI model carries over to a new continent (F1 0.93 in Peru after training only in the Himalaya) and beats ESA's built-in water layer there, but it does **not** beat the simple NDWI rule. Its value is what it feeds: one water map per year turns into 15 measurements and a report card for flood risk, water supply, drained lakes and glacier retreat. And it caught the real South Lhonak outburst in 2023.

**Honest notes:**
- On unseen Himalayan lakes our model catches more of the real water than ESA's layer (recall 92% vs 80%), but it raises many more false alarms on snow and ice (precision 66% vs 91%).
- Persistence beat both trend forecasts. Lake areas jump from year to year (ice, sediment, partial drainage), so "same as last year" is a strong baseline.
- After the final run, a check using only the training lakes found that a more regularized model with speck removal scores better (not in the official numbers, since we ran out of time to rerun). A version using only brightness ratios generalized best, but we only found that by looking at the test lakes, so we didn't switch to it. See [experiments/MODEL_SELECTION.md](experiments/MODEL_SELECTION.md).

## 4. Where does it fail?

`RESULTS.md` splits errors by terrain and shows an error map for every test lake (red = false alarm, yellow = missed water).

- **Snow and ice are the biggest problem.** On unseen Himalayan lakes, most of our model's false water is on pixels labeled snow or ice (159 ha of false water there, vs 21 ha on normal ground). Wet, debris-covered glacier ice looks a lot like water.
- **Worst lake: Gepang Gath** (F1 0.61). The lake itself is found well, but the model marks the rock-covered glacier tongue below the lake and thin meltwater streams as water. Wet, dark debris on ice looks like water to it. NDWI and ESA's layer don't make this mistake (see `results/figures/errors_gepang_gath.png`).
- **Shadows:** ESA's water layer misses every lake pixel in mountain shadow (0% recall). Ours finds about 80% of them. NDWI does about as well.
- **South Lhonak, 2023:** the model measured the lake at 158 ha in Oct 2022 and almost 0 ha on 26 Oct 2023, three weeks after the real outburst flood of 4 Oct 2023. The sudden-drop flag worked. But the lake did not fully empty, so the near-zero area is wrong: muddy, sediment-filled water right after the flood confused the model.
- **False "sudden drops":** Imja Tsho shows a drop from 173 ha (2024) to 91 ha (2025). There was no flood there, so this is most likely ice or snow on the lake surface. A real system would confirm drops with a second image.
- **Label errors:** WorldCover is itself made by a model, so some "errors" may be the answer key's fault.

## What we fixed after the first real run

Our first run on real data exposed bugs that synthetic test data never showed. We kept those results in [results_first_run/](results_first_run/) so you can compare.
1. Some images came from the edge of a satellite pass and were blank. We now keep only images that fully cover the lake.
2. Newer images (2022 onward) had a brightness offset subtracted twice, making water look negative. We now check each image's processing version.
3. Our Gepang Gath box was about 2.5 km off. We moved it to the published location (32°31'N 77°13'E).
4. Thin snow made 10 of 12 lakes "touch a glacier." Glaciers now must be connected ice bodies of 5 ha or more.
5. November images had long shadows and fresh snow, so the Himalaya season is now September to October.

## What we'd do next

- Switch to brightness-ratio inputs and test them on a fresh set of lakes, since that version looked like it generalized best.
- Add hand-checked lake outlines for a few lakes, so the answer key isn't another model.
- Use two images per year and confirm any sudden drop before flagging it, to cut false alarms from ice.

## Make it your own: what we added

The brief has a land-use classification project (EuroSAT). We changed it in all three ways the brief suggests:

- **Our own user and setting:** a hazard team ranking dangerous glacial lakes, in the Himalaya and Andes, instead of general land use in Europe.
- **Our own data:** live Sentinel-2 chips, ESA WorldCover labels, and Copernicus DEM slope for 12 named lakes over 9 years. We don't use EuroSAT at all.
- **Our own uses:** one AI water map feeds five different decisions (flood screening, water supply, drained-lake check, glacier retreat, water quality).
- **Our own questions:**
  - Does a model trained only on Himalayan lakes still work on a different continent (the Andes)?
  - Where does it fail (shadow, ice, steep slopes)?
  - Can lake area be forecast better than "same as last year"?

**A design decision we're proud of:** our first version used raw slope as an input. Then we realised the elevation map was made from 2011 to 2015 radar data, so the old lake outline is perfectly flat in it. A model fed raw slope would learn the *old* lake shape and hide new growth, which is the one thing we care about. We replaced it with a "cliff" flag (slope over 25 degrees) that only rules out steep rock, where a lake can't be now or later.

## Run it yourself

The easiest way is to open `notebooks/Glacier_Lake_Watch_RUN.ipynb` in Google Colab and click Runtime → Run all. It has all the code built in and saves results to your Google Drive. You don't need a GPU. A full run takes about 10 minutes.

```bash
pip install -r requirements.txt
python run_all.py            # real data, about 20-40 min the first time, cached after that
python app.py --share        # web app with a temporary public link
# permanent free hosting on Hugging Face Spaces: see DEPLOY.md
python run_all.py --synthetic   # fake data, only to check the code works offline
```

```
glw/zones.py       the 12 lakes, train/test split, seasons
glw/data.py        downloads Sentinel-2, WorldCover and DEM chips from public cloud storage
glw/model.py       features, model, baselines, scoring, lake outline
glw/measure.py     shape, water colour, ice, glacier distance, terrain, volume, peak flow
glw/assess.py      report card: flood score, drought / water supply, drained lakes, glacier retreat
glw/timeseries.py  forecast backtest and watch list
glw/viz.py         figures
glw/report.py      writes results/RESULTS.md
run_all.py         the whole pipeline
app.py             the web app (Gradio + Plotly)
DEPLOY.md          how to host the web app for free
hf_space/          settings file for Hugging Face Spaces
```

## Limitations

- WorldCover is from 2021. We train and test on 2021 images (or the closest year) so the labels match the image.
- Lake area is not lake volume, and growth is not the only thing that makes a lake dangerous. The type of dam, steep ice above the lake, and how many people live downstream all matter. A real hazard team would combine our ranking with those.
- Forecast "truth" is our own model's measurement of later years, not a field survey.
- Volume and peak flow come from rule-of-thumb formulas fitted on other lakes. They can be off by 2x or more, so we use them to compare lakes, not as exact values.
- Ice area mixes glaciers with leftover seasonal snow. We pick late-season images to reduce this, but single years can jump.
- Some lakes are drained on purpose by people (Paron for hydropower, Palcacocha for flood safety), so not every change is climate.
- Cloudy years are skipped (we need at least 90% clear sky over the lake), so some lakes have gaps.
- Lake coordinates are approximate centres. Each 4 km box is wide enough to contain the lake.

## Citations and tools

**Data**
- Sentinel-2 Level-2A imagery, European Space Agency / Copernicus, accessed through the Earth Search STAC API by Element 84 on AWS Open Data: https://earth-search.aws.element84.com/v1 (licence: Copernicus open data).
- ESA WorldCover 10 m 2021 v200. Zanaga, D. et al. (2022), https://esa-worldcover.org (CC BY 4.0).
- Copernicus DEM GLO-30, ESA, on AWS Open Data: https://registry.opendata.aws/copernicus-dem/
- Lake locations and flood history from public sources about each lake (e.g. reporting on the October 2023 South Lhonak outburst).

**Methods**
- Huggel, C., Kääb, A., Haeberli, W., Teysseire, P., & Paul, F. (2002). Remote sensing based assessment of hazards from glacier lake outbursts: a case study in the Swiss Alps. *Canadian Geotechnical Journal*, 39(2), 316-330. (Volume and peak flow formulas.)
- Dozier, J. (1989). Spectral signature of alpine snow cover from the Landsat Thematic Mapper. *Remote Sensing of Environment.* (NDSI snow and ice index.)
- McFeeters, S. K. (1996). The use of the Normalized Difference Water Index (NDWI). *International Journal of Remote Sensing.*
- Xu, H. (2006). Modification of NDWI (MNDWI). *International Journal of Remote Sensing.*

**Libraries:** scikit-learn, Plotly, NumPy, SciPy, rasterio / GDAL, pyproj, pystac-client, matplotlib, Gradio, Google Colab.

**AI tools used:** Claude (Anthropic) helped debug code.

## Team

_Add names here._ All listed members contributed during the hackathon weekend (Nov 14 to 15, 2026).
