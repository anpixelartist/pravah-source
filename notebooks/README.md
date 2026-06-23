# notebooks
Exploration only — production logic lives in `src/pravah/` (tested, reusable), never in a
notebook. Suggested: `01_profiling` (sanity-check the FACTs), `02_features` (prototype FE-3
coverage normalisation), `03_forecast` (M3 model + SHAP). Import from the package:
`from pravah import pipeline, pressure`.
