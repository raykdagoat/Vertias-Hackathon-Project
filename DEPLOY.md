# Put the web app online (free, permanent link)

Do this AFTER the Colab run, because the app needs the trained model in `results/`.

1. Make a free account at https://huggingface.co and click **New Space**.
2. Name it `glacier-lake-watch`, choose **Gradio** as the SDK, hardware **CPU basic (free)**, visibility **Public**. Click Create.
3. On the Space page, open **Files**, then **Add file → Upload files**. Upload:
   - `app.py`
   - `requirements.txt`
   - the whole `glw/` folder
   - the whole `results/` folder from your Colab run (it must contain `model.joblib`, `watch_list.csv`, `lake_areas.csv`, `metrics.json`)
   - `hf_space/README.md`, but upload it as `README.md` at the top level (replace the one the Space made). It tells Hugging Face how to run the app.
4. Wait 2 to 4 minutes while it builds. Your app is live at `https://huggingface.co/spaces/YOUR-NAME/glacier-lake-watch`.
5. Put that link in the GitHub README and on the submission form.

The "Explore a lake" tab downloads each image the first time someone opens it, so the first click on a lake takes about 10 to 20 seconds. After that it's cached.
