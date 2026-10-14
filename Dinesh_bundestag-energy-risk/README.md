# The Energy Trilemma in German Parliamentary Debates: How Parties, Government Roles and Geopolitical Shocks Shape Attention

Dinesh Korrapati, Christin Hoffmann and Felix Müsgens  
Brandenburg University of Technology Cottbus-Senftenberg, Chair of Energy Economics

This repository contains the code and data for the paper. The study analyses how German political parties frame energy risks in Bundestag plenary speeches from four legislative periods (2013 to 2025). Each speech is classified with the open-weight language model Qwen2.5-32B, run locally, by energy policy topic, risk type (environmental, geopolitical or social) and energy source. The classifications are validated against manual coding and used to analyse differences between parties and the effects of major energy-related events.

The repository is organised in four parts. `/data` contains the speech data at each processing stage, `/code` the scripts for every step of the analysis, `/validation` the validation sample, manual coding and model labels, and `/results` all tables and figures reported in the paper. Further outputs that do not appear in the paper are stored in `/results/additional`. The Python scripts require the packages listed in `requirements.txt`.

### Collecting and Classifying the Speeches

The speeches come from the official plenary protocols of the German Bundestag, retrieved through the DIP API. The complete set of speeches and the cleaned speeches per Bundestag period are not included because they exceed GitHub's file size limit, but they can be rebuilt with the first two scripts below. All data from the keyword filtering step onward are included, so every result reported in the paper can be reproduced without rebuilding them.

- `01_extract_speeches.py` downloads all plenary speeches and writes them to `/data/raw`.
- `02_clean_and_split_periods.py` cleans the speeches and splits them by Bundestag period into `/data/interim`.
- `03_filter_energy_speeches.py` keeps the speeches matching the energy keyword dictionary and writes them to `/data/energy_filtered`.
- `04_classify_corpus.py` classifies each speech with Qwen2.5-32B through a local Ollama server (`ollama pull qwen2.5:32b`) and writes the results to `/data/classified`.
- `05_add_speaker_roles.py` adds speaker roles and corrects party labels, writing to `/data/speaker_roles`.
- `06_build_regression_panel.py` builds the regression panel in `/data/regression`.

### Descriptive Results

- `data_loader.py` loads and prepares the classifications for the two scripts below.
- `07_descriptive_figures.py` creates the descriptive figures.
- `08_descriptive_tables.py` creates the descriptive tables.

### Validation

- `01_draw_validation_sample.py` draws the stratified random sample of 100 speeches.
- `02_self_consistency.py` classifies each speech in the sample five times and computes the self-consistency scores.
- `03_evaluate_manual_coding.py` compares the manual coding with the model's labels and computes precision, recall and F1 for every label.

### Regressions

The Stata code requires the packages `estout`, `ftools` and `reghdfe` (`ssc install estout`, `ssc install ftools`, `ssc install reghdfe`). Start Stata in the repository's main folder and run `do code/stata/00_master.do`, which runs the following files in order.

- `01_speaker_crosswalk.do` links speakers to the official master data of the Members of the Bundestag.
- `02_prep_regression.do` creates the Stata dataset `data/regression/regression_panel.dta`.
- `03_logit_main.do` estimates the pooled logit models and average marginal effects.
- `04_hdfe.do` estimates the linear probability models with fixed effects and the conditional logit models.
- `05_eventstudy.do` estimates the event studies and the party convergence model.
- `06_robustness_election_pooled.do` and `07_robustness_election_clogit.do` re-estimate the models using the regular instead of the actual date of the 2025 federal election.
- `08_lpm_speaker_month_fe.do` estimates the linear probability models with speaker and calendar-month fixed effects (Model B2).
