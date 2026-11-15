# Model selection study (done after our final full run)

On unseen Himalayan lakes our model lost to the simple NDWI rule. Most of its false alarms were on
snow, ice and debris-covered glacier. So we tried 5 model versions, 3 decision thresholds, and
removing tiny water specks.

**Rule we followed:** judge versions using ONLY the 6 training lakes, with leave-one-lake-out
cross-validation (train on 5 lakes, score on the 6th, repeat 6 times). The test lakes were not used to choose.

| Version | Inputs | Threshold | Speck removal | CV F1 (training lakes) | Test F1 Himalaya | Test F1 Andes |
|---|---|---|---|---|---|---|
| A, model settings used in our official run | all 14 | 0.5 | no | 0.870 | 0.701 | 0.928 |
| B, regularized | all 14 | 0.45 | yes | **0.885 (best CV)** | 0.764 | 0.940 |
| B, regularized | all 14 | 0.6 | yes | 0.879 | 0.838 | 0.944 |
| D, ratios only, regularized | 11 ratio inputs | 0.45 | yes | 0.874 | 0.851 | 0.945 |
| D, ratios only, regularized | 11 ratio inputs | 0.6 | yes | 0.868 | 0.867 | 0.946 |
| NDWI > 0.2 (baseline) | 1 index | 0.2 | no | n/a | 0.855 | 0.941 |

Numbers come from `exp1_feature_sets.py` and `exp2_threshold_cleanup.py`, run on the 2021 images.
Version A here scores a bit lower than in `results/RESULTS.md` (0.766 Himalaya) because the training
pixels are randomly sampled.

**What we would choose:** version B with threshold 0.45 and speck removal, because it had the best
cross-validation score on the training lakes. We ran this study after our final full run and ran
out of time to rerun the whole pipeline with it, so the official results in `results/RESULTS.md`
use version A.

**What we learned (honestly, after looking at the test lakes):** versions that use only brightness
*ratios* (like NDWI) instead of raw brightness carry over better to new lakes, even though they
score a little lower in cross-validation. Raw brightness changes with sun angle, season and haze,
so a model trained on it partly memorizes the lighting of its training images. We did NOT switch to
the ratio version, because we only found this by looking at test results, and picking a model that
way would make our test score unfair. It's the first thing we'd try next, on a fresh set of test lakes.
