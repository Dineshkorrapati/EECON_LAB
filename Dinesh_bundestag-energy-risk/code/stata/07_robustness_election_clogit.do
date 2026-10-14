********************************************************************************
* 07_robustness_election_clogit.do
*
* Robustness check: re-estimate the conditional logit models using the regular
* instead of the actual date of the 2025 federal election.
*
* Input:  data/regression/regression_panel.dta
* Output: results/tables/tabRobust_election_clogit.tex
********************************************************************************

clear all
set more off

*** paths: run from the repository root, or via code/stata/00_master.do
if "$root" == "" global root "`c(pwd)'"
global raw_dir  "$root/data/raw"
global proc_dir "$root/data/regression"
global log_dir  "$root/results/logs"
global tab_dir  "$root/results/tables"
global fig_dir  "$root/results/figures"

use "${proc_dir}/regression_panel.dta", clear

********************************************************************************
*** I. RECODE years_to_election USING THE ANTICIPATED (REGULAR) DATE
***    (identical logic to 06_robustness_election_pooled.do)
********************************************************************************

local d_collapse = td(27dec2024)

gen long next_election_robust = .
replace next_election_robust = td(24sep2017) if speech_date <= td(24sep2017)
replace next_election_robust = td(26sep2021) if speech_date >  td(24sep2017) & speech_date <= td(26sep2021)
replace next_election_robust = td(28sep2025) if speech_date >  td(26sep2021) & speech_date <= `d_collapse'
replace next_election_robust = td(23feb2025) if speech_date >  `d_collapse' & speech_date <= td(23feb2025)
replace next_election_robust = td(25mar2029) if speech_date >  td(23feb2025)
format next_election_robust %tdDD.Mon.CCYY

assert !missing(next_election_robust)

gen days_to_next_election_robust = next_election_robust - speech_date
assert days_to_next_election_robust > 0

gen years_to_election_robust = days_to_next_election_robust / 365.25
label var years_to_election_robust "Years to next election (robust: anticipated date)"

********************************************************************************
*** II. RERUN THE CONDITIONAL LOGIT (matching 04_hdfe.do Section C
***     exactly, only swapping years_to_election for years_to_election_robust)
********************************************************************************

local outcomes env_risk geo_risk social_risk
eststo clear

foreach y of local outcomes {
    clogit `y' i.opposition c.years_to_election_robust ///
        i.post_crimea i.post_ns2 i.post_ukraine i.govt_speaker i.wp, ///
        group(speaker_id) vce(cluster speaker_id)
    eststo `y'_c1robust
}

********************************************************************************
*** III. EXPORT -- years_to_election coefficient only, all three outcomes
********************************************************************************

esttab env_risk_c1robust geo_risk_c1robust social_risk_c1robust ///
    using "${tab_dir}/tabRobust_election_clogit.tex", replace ///
    booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(years_to_election_robust) ///
    mtitles("Env." "Geo." "Social") ///
    title("Robustness check: conditional logit, years to election using anticipated date")
