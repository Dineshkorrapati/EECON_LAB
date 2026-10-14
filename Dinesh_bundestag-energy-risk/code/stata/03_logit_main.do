********************************************************************************
* 03_logit_main.do
*
* Estimate the pooled logit models of risk invocation and their average
* marginal effects.
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

log using "${log_dir}/03_logit_main.log", replace text

use "${proc_dir}/regression_panel.dta", clear

local outcomes env_risk geo_risk social_risk
local lbl_env_risk    "Environmental risk"
local lbl_geo_risk    "Geopolitical risk"
local lbl_social_risk "Social risk"

eststo clear

foreach y of local outcomes {

    di as txt _n "==================== `y' ===================="

    *** M1: party only
    logit `y' ib2.party_f, vce(cluster speaker_id)
    eststo `y'_m1

    *** M2: + opposition, election countdown, govt speaker, WP FE
    logit `y' ib2.party_f i.opposition c.years_to_election ///
        i.govt_speaker i.wp, vce(cluster speaker_id)
    eststo `y'_m2
    margins, dydx(*) post
    eststo `y'_m2ame
    estimates restore `y'_m2

    *** M3: + party x opposition
    logit `y' ib2.party_f##i.opposition c.years_to_election ///
        i.govt_speaker i.wp, vce(cluster speaker_id)
    eststo `y'_m3
    *** opposition effect by party (only meaningful for parties w/ both states)
    margins party_f, dydx(opposition)

    *** M4: M2 + post-event dummies (no interaction -> all AMEs estimable)
    logit `y' ib2.party_f i.opposition c.years_to_election ///
        i.govt_speaker i.post_crimea i.post_ns2 i.post_ukraine i.wp, ///
        vce(cluster speaker_id)
    eststo `y'_m4
    margins, dydx(*) post
    eststo `y'_m4ame

    *** M5: M3 + post-event dummies (interaction; coefficient table only —
    *** party/opposition AMEs are not estimable for parties with empty
    *** party x opposition cells)
    logit `y' ib2.party_f##i.opposition c.years_to_election ///
        i.govt_speaker i.post_crimea i.post_ns2 i.post_ukraine i.wp, ///
        vce(cluster speaker_id)
    eststo `y'_m5
}

********************************************************************************
*** EXPORT — one coefficient table per outcome (M1–M4)
********************************************************************************

foreach y of local outcomes {
    esttab `y'_m1 `y'_m2 `y'_m3 `y'_m4 `y'_m5 ///
        using "${tab_dir}/tabA_logit_`y'.tex", replace ///
        booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
        drop(*.wp) ///
        mtitles("M1" "M2" "M3" "M4" "M5") ///
        stats(N N_clust r2_p, fmt(%9.0fc %9.0fc %9.3f) ///
              labels("Observations" "Speakers (clusters)" "Pseudo R$^2$")) ///
        title("Pooled logit: `lbl_`y'' (log-odds; SE clustered by speaker)") ///
        addnotes("Base party: CDU/CSU. WP fixed effects included in M2--M4." ///
                 "AfD and Linke are never in government; their interaction cells are empty.") ///
        label nobaselevels eqlabels(none) interaction(" $\times$ ")

    esttab `y'_m1 `y'_m2 `y'_m3 `y'_m4 `y'_m5, ///
        b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) drop(*.wp) ///
        mtitles("M1" "M2" "M3" "M4" "M5") ///
        stats(N N_clust r2_p, fmt(%9.0fc %9.0fc %9.3f)) label nobaselevels
}

*** AME summary table: M2 and M4 for all three outcomes
esttab env_risk_m2ame geo_risk_m2ame social_risk_m2ame ///
       env_risk_m4ame geo_risk_m4ame social_risk_m4ame ///
    using "${tab_dir}/tabA_ame_all.tex", replace ///
    booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    drop(*.wp) ///
    mtitles("Env." "Geo." "Social" "Env." "Geo." "Social") ///
    mgroups("M2" "M4", pattern(1 0 0 1 0 0) ///
        prefix(\multicolumn{@span}{c}{) suffix(}) span ///
        erepeat(\cmidrule(lr){@span})) ///
    stats(N, fmt(%9.0fc) labels("Observations")) ///
    title("Average marginal effects (probability scale; SE clustered by speaker)") ///
    label nobaselevels eqlabels(none)

esttab env_risk_m2ame geo_risk_m2ame social_risk_m2ame ///
       env_risk_m4ame geo_risk_m4ame social_risk_m4ame, ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) drop(*.wp) label nobaselevels

log close