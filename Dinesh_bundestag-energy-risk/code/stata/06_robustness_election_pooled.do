********************************************************************************
* 06_robustness_election_pooled.do
*
* Robustness check: re-estimate the pooled logit models using the regular
* instead of the actual date of the 2025 federal election.
*
* Input:  data/regression/regression_panel.dta
* Output: results/tables/tabRobust_election.tex
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

*** sanity check: robust and original variables should be identical everywhere
*** EXCEPT the 26sep2021-27dec2024 window, where robust should be LARGER
*** (anticipated Sep 2025 is later than the actual Feb 2025 that was used)
gen diff_check = years_to_election_robust - years_to_election
su diff_check if speech_date > td(26sep2021) & speech_date <= `d_collapse'
su diff_check if speech_date <= td(26sep2021) | speech_date > `d_collapse'
assert abs(diff_check) < 0.001 if speech_date <= td(26sep2021) | speech_date > `d_collapse'
drop diff_check

********************************************************************************
*** II. RERUN M2 AND M4 WITH years_to_election_robust, ALL THREE OUTCOMES
********************************************************************************

local outcomes env_risk geo_risk social_risk
eststo clear

foreach y of local outcomes {
    logit `y' ib2.party_f i.opposition c.years_to_election_robust ///
        i.govt_speaker i.wp, vce(cluster speaker_id)
    eststo `y'_m2robust

    logit `y' ib2.party_f i.opposition c.years_to_election_robust ///
        i.govt_speaker i.post_crimea i.post_ns2 i.post_ukraine i.wp, ///
        vce(cluster speaker_id)
    eststo `y'_m4robust
}

********************************************************************************
*** III. EXPORT -- years_to_election coefficient only, M2 and M4, all outcomes
********************************************************************************

esttab env_risk_m2robust geo_risk_m2robust social_risk_m2robust ///
       env_risk_m4robust geo_risk_m4robust social_risk_m4robust ///
    using "${tab_dir}/tabRobust_election.tex", replace ///
    booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(years_to_election_robust) ///
    mtitles("Env. (M2)" "Geo. (M2)" "Social (M2)" ///
            "Env. (M4)" "Geo. (M4)" "Social (M4)") ///
    title("Robustness check: years to election using anticipated (regular) date")
