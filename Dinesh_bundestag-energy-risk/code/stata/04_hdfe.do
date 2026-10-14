********************************************************************************
* 04_hdfe.do
*
* Estimate the linear probability models with fixed effects and the
* conditional logit models with speaker fixed effects.
*
* Input:  data/regression/regression_panel.dta
* Output: results/tables/
********************************************************************************

clear all
set more off
capture log close

*** paths: run from the repository root, or via code/stata/00_master.do
if "$root" == "" global root "`c(pwd)'"
global raw_dir  "$root/data/raw"
global proc_dir "$root/data/regression"
global log_dir  "$root/results/logs"
global tab_dir  "$root/results/tables"
global fig_dir  "$root/results/figures"
capture mkdir "$root/results"
capture mkdir "${log_dir}"
capture mkdir "${tab_dir}"
capture mkdir "${fig_dir}"

log using "${log_dir}/04_hdfe.log", replace text

use "${proc_dir}/regression_panel.dta", clear

local outcomes env_risk geo_risk social_risk
local lbl_env_risk    "Environmental risk"
local lbl_geo_risk    "Geopolitical risk"
local lbl_social_risk "Social risk"

eststo clear

foreach y of local outcomes {

    di as txt _n "==================== `y' ===================="

    *** B1: speaker FE + WP FE — within-speaker, coarse time controls
    reghdfe `y' i.opposition c.years_to_election ///
        i.post_crimea i.post_ns2 i.post_ukraine i.govt_speaker, ///
        absorb(speaker_id wp) vce(cluster speaker_id)
    eststo `y'_b1

    *** B2: speaker FE + month FE — sharpest within-speaker design
    reghdfe `y' i.opposition i.govt_speaker, ///
        absorb(speaker_id ym) vce(cluster speaker_id)
    eststo `y'_b2

    *** B3: sitting-day FE — party gaps within the same plenary day
    reghdfe `y' ib2.party_f i.opposition i.govt_speaker, ///
        absorb(speech_date) vce(cluster speaker_id)
    eststo `y'_b3

    *** B4: B3 + ln word count (robustness; unambiguous matches only)
    reghdfe `y' ib2.party_f i.opposition i.govt_speaker c.ln_wc, ///
        absorb(speech_date) vce(cluster speaker_id)
    eststo `y'_b4

    esttab `y'_b1 `y'_b2 `y'_b3 `y'_b4 ///
        using "${tab_dir}/tabB_hdfe_`y'.tex", replace ///
        booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
        mtitles("B1" "B2" "B3" "B4") ///
        stats(N N_clust r2_a, fmt(%9.0fc %9.0fc %9.3f) ///
              labels("Observations" "Speakers (clusters)" "Adj. R$^2$")) ///
        title("LPM with high-dimensional FE: `lbl_`y''") ///
        addnotes("B1: speaker + WP FE. B2: speaker + month FE (time-only" ///
                 "regressors absorbed). B3/B4: sitting-day FE. SE clustered" ///
                 "by speaker. B4 restricted to unambiguous word-count matches.") ///
        label nobaselevels eqlabels(none)

    esttab `y'_b1 `y'_b2 `y'_b3 `y'_b4, ///
        b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
        mtitles("B1" "B2" "B3" "B4") ///
        stats(N N_clust r2_a, fmt(%9.0fc %9.0fc %9.3f)) label nobaselevels
}

********************************************************************************
*** C: conditional (fixed-effects) logit — within-speaker, odds scale
********************************************************************************

foreach y of local outcomes {
    di as txt _n "========== clogit `y' =========="
    clogit `y' i.opposition c.years_to_election ///
        i.post_crimea i.post_ns2 i.post_ukraine i.govt_speaker i.wp, ///
        group(speaker_id) vce(cluster speaker_id)
    eststo `y'_c1
    di as txt "speaker clusters used (with outcome variation): " e(N_clust)
}

esttab env_risk_c1 geo_risk_c1 social_risk_c1 ///
    using "${tab_dir}/tabC_clogit.tex", replace ///
    booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    drop(*.wp) ///
    mtitles("Env." "Geo." "Social") ///
    stats(N N_clust, fmt(%9.0fc %9.0fc) ///
          labels("Observations" "Speakers (clusters)")) ///
    title("Conditional logit with speaker fixed effects (log-odds)") ///
    addnotes("Speakers without within-variation in the outcome drop out." ///
             "WP fixed effects included. SE clustered by speaker.") ///
    label nobaselevels eqlabels(none)

esttab env_risk_c1 geo_risk_c1 social_risk_c1, ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) drop(*.wp) ///
    stats(N N_clust, fmt(%9.0fc %9.0fc)) label nobaselevels

log close