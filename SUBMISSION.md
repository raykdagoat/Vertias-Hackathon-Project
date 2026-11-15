# Submission guide (Glacier Lake Watch)

Deadline: **Sunday Nov 15, 11:59 PM ET (10:59 PM Central).** Aim to submit by 9:59 PM ET (8:59 PM Central), 2 hours early as the brief suggests.

## Checklist

1. Open `notebooks/Glacier_Lake_Watch.ipynb` in Google Colab and click Runtime → Run all.
2. When `run_all.py` finishes, read `results/RESULTS.md` in the output.
3. Download `results.zip`. Upload the `results/` folder into this GitHub repo (Add file → Upload files).
4. Fill in the `_fill in_` spots in `README.md` (Results table, main takeaway, team names) with the REAL numbers from `RESULTS.md`. Don't round them up. If the model loses to a baseline somewhere, say so. Judges score honest modest results higher.
5. In the Colab, run the last cell to get a public demo link. Record the 2 minute video below.
6. Submit the form: track = **AI + Climate**, repo link, video link.

## Form answers (copy, then edit)

**Project name:** Glacier Lake Watch

**One-line summary:** An AI tool that finds glacial lakes in free Sentinel-2 satellite images, measures them every year, and ranks which lakes are growing fastest so hazard teams know which ones to check first.

**Who is it for:** A hazard analyst at a regional disaster agency in the Himalaya or Andes, planning which glacial lakes get a field visit each season.

**What did you add beyond the suggested project:** We started from the land-use mapping idea but built our own version. We added our own user (glacial lake flood hazard teams), our own data (live Sentinel-2, ESA WorldCover labels and Copernicus DEM for 12 named lakes, 2017 to 2025, no EuroSAT), and our own questions: does a model trained on Himalayan lakes work in the Andes, where does it fail (shadow, ice, steep slopes), and can lake area be forecast better than persistence?

**Baseline comparison:** Always-land, a tuned NDWI threshold, and ESA's own scene water class for detection. Persistence (next year = this year) for the forecast. Tested on 6 lakes the model never saw, years never shuffled.

**AI tools used:** Claude (Anthropic) for coding help and write-up drafting. Libraries: scikit-learn, rasterio, pystac-client, Gradio.

## 2 minute video script

**0:00 to 0:20, the problem.** "In October 2023, South Lhonak Lake in India burst and wiped out a dam downstream. There are thousands of lakes like it across the Himalaya and Andes, and agencies can only visit a few each year. We built Glacier Lake Watch to help them decide which ones to check first."

**0:20 to 0:50, the demo.** Open the app. In Explore a lake, pick a lake and slide from 2017 to 2025 so viewers watch the blue lake outline grow. Then show the Watch list tab. "This is the ranking a hazard analyst would use to plan field visits."

**0:50 to 1:20, does it beat a baseline?** Show the results table and the bar chart. "We tested on lakes the model never saw, including a different continent. Here's our F1 compared with the classic NDWI rule and ESA's own water layer." Say the real numbers.

**1:20 to 1:45, where it fails.** Show the worst error map. "Red is a false alarm, yellow is missed water. Our model struggles with [real failure from RESULTS.md]. And no forecast could predict South Lhonak's sudden collapse, so we flag sudden drops instead."

**1:45 to 2:00, wrap.** Show the Check any lake tab on a new lake. "It works on any glacial lake on Earth using free data. Main takeaway: [one sentence]."
