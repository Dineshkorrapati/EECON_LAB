********************************************************************************
* 08_lpm_speaker_month_fe.do
*
* Robustness check: estimate the linear probability models with speaker and
* calendar-month fixed effects (Model B2).
*
* Input:  data/regression/regression_panel.dta
* Output: results/tables/tabB2_results.tex
********************************************************************************
clear all
set more off

if "$root" == "" global root "`c(pwd)'"
use "$root/data/regression/regression_panel.dta", clear

capture mkdir "$root/results"
capture mkdir "$root/results/tables"
eststo clear

foreach y in env_risk geo_risk social_risk {
    reghdfe `y' i.opposition i.govt_speaker, ///
        absorb(speaker_id ym) vce(cluster speaker_id)
    eststo `y'_b2
}

esttab env_risk_b2 geo_risk_b2 social_risk_b2 ///
    using "$root/results/tables/tabB2_results.tex", replace ///
    booktabs b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    mtitles("Environmental" "Geopolitical" "Social") ///
    keep(1.opposition 1.govt_speaker _cons) ///
    order(1.opposition 1.govt_speaker _cons) ///
    coeflabels( ///
        1.opposition "Opposition" ///
        1.govt_speaker "Government office (non-MdB role)" ///
        _cons "Constant") ///
    stats(N N_clust r2_a, ///
        fmt(%9.0fc %9.0fc %9.3f) ///
        labels("Observations" "Speakers (clusters)" "Adjusted R-squared")) ///
    title("Model B2: Linear probability models with speaker and calendar-month fixed effects\label{tab:b2_results}") ///
    addnotes( ///
        "Speaker and calendar-month fixed effects included in all models." ///
        "Standard errors clustered by speaker are in parentheses.") ///
    nobaselevels eqlabels(none)
