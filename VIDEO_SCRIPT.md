# 2 minute demo video script

Record your screen with the web app (`python app.py`, or the last cell of the Colab notebook for a link) plus `results/RESULTS.md` open. Read this out loud.

**0:00 to 0:15, the problem**
"On October 4th, 2023, South Lhonak Lake in India burst and destroyed a dam downstream. Thousands of glacial lakes like it are growing as glaciers melt, and hazard teams can only visit a few each year. Glacier Lake Watch helps them decide which lakes to check first."

**0:15 to 1:15, the demo**
- Watch list tab: "Each dot is a lake in the Himalaya or the Andes, coloured by our flood screening score. Longbasaba in Tibet and Lower Barun in Nepal are at the top: big lakes touching glacier ice."
- Explore a lake tab: pick South Lhonak and slide from 2022 to 2023. "In October 2022 our model measured the lake at 158 hectares. Three weeks after the 2023 outburst it measured almost nothing, and the tool flagged a sudden drop." Point out the measurement table: volume, peak flow, distance to glacier, water colour.
- Compare lakes tab: show area or glacier ice over time for 3 lakes.
- Check any lake tab: click the Mendenhall Lake example. "It works on any lake on Earth, using free satellite images. Nobody has to upload anything."

**1:15 to 1:45, results and baseline**
"We trained on 6 Himalayan lakes and tested on 6 lakes the model never saw, including 3 in Peru. In Peru our model scored an F1 of 0.93 and beat ESA's built-in water layer. But honestly, the simple NDWI water index still scored a little higher, 0.94. For forecasting next year's size, 'same as last year' beat our trend forecast."

**1:45 to 2:00, where it fails and takeaway**
"Our model's biggest weakness is wet, rock-covered glacier ice, which it mistakes for water. And right after the South Lhonak flood it measured the lake as nearly empty when it wasn't, because of muddy water. Main takeaway: one yearly water map from free satellite data can feed a full report card for flood risk, water supply and glacier retreat, anywhere on Earth."
