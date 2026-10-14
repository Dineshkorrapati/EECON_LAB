********************************************************************************
* 05_eventstudy.do
*
* Estimate the event studies around the Crimea annexation (2014), the Nord
* Stream 2 sanctions (2019) and the Russian invasion of Ukraine (2022), and the
* party convergence model.
*
* Input:  data/regression/regression_panel.dta
* Output: results/figures/, results/tables/
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
global add_dir  "$root/results/additional"
capture mkdir "${add_dir}"

log using "${log_dir}/05_eventstudy.log", replace text

use "${proc_dir}/regression_panel.dta", clear

local events  crimea ns2 ukraine
local lbl_crimea  "Crimea annexation (18.03.2014)"
local lbl_ns2     "Nord Stream 2 sanctions (21.12.2019)"
local lbl_ukraine "Ukraine invasion (24.02.2022)"

*** presentation order (paper convention): environmental -> geopolitical -> social
local outcomes env_risk geo_risk social_risk
local lbl_env_risk    "Environmental risk"
local lbl_geo_risk    "Geopolitical risk"
local lbl_social_risk "Social risk"


********************************************************************************
*** I. MONTHLY EVENT STUDIES (window: months -12..+12, ref = -1)
***    Day-based months (floor(days/30.4375)), so that speeches given in
***    the event month but before the event day count as pre-event. Note
***    that non-sitting months have no coefficient and per-bin N is small.
********************************************************************************

foreach e of local events {

    *** day-based monthly event time; shift so that ref -1 -> 11 (factor
    *** variables need non-negative values: evm +12 -> 0..24, ref at 11)
    capture drop evmf_`e'
    gen int evmf_`e' = floor(evd_`e' / 30.4375) + 12 ///
        if inrange(floor(evd_`e' / 30.4375), -12, 12)

    foreach y of local outcomes {

        qui count if !missing(evmf_`e')
        di as txt _n "===== event study: `e' / `y'  (N in window = " r(N) ") ====="

        reghdfe `y' ib11.evmf_`e' i.govt_speaker if !missing(evmf_`e'), ///
            absorb(party_f) vce(cluster speaker_id)
        eststo es_`e'_`y'

        *** joint placebo test on pre-event coefficients (months -12..-2)
        qui levelsof evmf_`e' if evmf_`e' < 11, local(prelvls)
        local pretest ""
        foreach l of local prelvls {
            local pretest "`pretest' `l'.evmf_`e'"
        }
        if "`pretest'" != "" {
            capture test `pretest'
            if !_rc di as txt "joint pre-trend test: F = " %6.2f r(F) ///
                ", p = " %6.4f r(p)
        }

        *** figure (vector pdf) via twoway on a numeric month axis:
        *** filled dots = p<0.10, hollow = not significant, gray hollow =
        *** reference month (-1); gray band = intervention month (bin 0).
        local dfr = e(df_r)
        preserve
            clear
            qui set obs 25
            gen int month = _n - 13
            gen double b  = .
            gen double se = .
            forvalues l = 0/24 {
                local m = `l' - 12
                if `l' == 11 {                       // reference month -1
                    qui replace b = 0 if month == `m'
                    continue
                }
                capture scalar _bb = _b[`l'.evmf_`e']
                if _rc continue                       // month not in window
                capture scalar _ss = _se[`l'.evmf_`e']
                if _ss > 0 {                          // omitted levels: se==0
                    qui replace b  = _bb if month == `m'
                    qui replace se = _ss if month == `m'
                }
            }
            gen double lo = b - invttail(`dfr', .025) * se
            gen double hi = b + invttail(`dfr', .025) * se
            gen byte sig  = 2 * ttail(`dfr', abs(b / se)) < .10 if se < .
            gen double b_sig = b if sig == 1
            gen double b_ins = b if sig == 0
            gen double b_ref = b if se >= . & b == 0

            *** Keep only months -3 to 12 for Crimea to remove blank space
            if "`e'" == "crimea" {
                drop if month < -3
            }

            *** gray band over the intervention month (bin 0 = event day +30.4d)
            qui summarize lo
            local ymin = min(r(min), 0) - .02
            qui summarize hi
            local ymax = max(r(max), 0) + .02
            gen double band_x  = cond(_n == 1, -0.5, 0.5) if _n <= 2
            gen double band_lo = `ymin' if _n <= 2
            gen double band_hi = `ymax' if _n <= 2

            local xopts "xlabel(-12(3)12) xscale(range(-12.5 12.5))"
            if "`e'" == "crimea" local xopts "xlabel(-3(3)12) xscale(range(-3.5 12.5))"

            twoway ///
                (rarea band_hi band_lo band_x, color(gs14) lwidth(none)) ///
                (rcap hi lo month, lcolor(gs6)) ///
                (scatter b_sig month, msymbol(O)  msize(medsmall) mcolor(black)) ///
                (scatter b_ins month, msymbol(Oh) msize(medsmall) mcolor(black)) ///
                (scatter b_ref month, msymbol(Oh) msize(medsmall) mcolor(gs8)) ///
                , yline(0, lpattern(dash) lcolor(gs8)) ///
                `xopts' ///
                xtitle("Months relative to event") ///
                ytitle("Effect on P(`lbl_`y'')") ///
                title("`lbl_`e''", size(medium)) ///
                legend(order(3 "p < 0.10" 4 "p {&ge} 0.10" 1 "event month") ///
                    pos(6) rows(1) size(small) region(lstyle(none))) ///
                xsize(7) ysize(4) plotregion(margin(zero)) ///
                graphregion(color(white)) bgcolor(white)
            graph export "${add_dir}/fig_es_`e'_`y'.pdf", replace
        restore
    }

    *** ---------------------------------------------------------------
    *** combined three-series plot for this event (all outcomes together)
    *** ---------------------------------------------------------------
    preserve
        clear
        qui set obs 25
        gen int month = _n - 13
        foreach y of local outcomes {
            gen double b_`y'  = .
            gen double se_`y' = .
        }

        foreach y of local outcomes {
            qui estimates restore es_`e'_`y'
            local dfr = e(df_r)
            forvalues l = 0/24 {
                local m = `l' - 12
                if `l' == 11 {
                    qui replace b_`y' = 0 if month == `m'
                    continue
                }
                capture scalar _bb = _b[`l'.evmf_`e']
                if _rc continue
                capture scalar _ss = _se[`l'.evmf_`e']
                if _ss > 0 {
                    qui replace b_`y'  = _bb if month == `m'
                    qui replace se_`y' = _ss if month == `m'
                }
            }
            gen double lo_`y' = b_`y' - invttail(`dfr', .025) * se_`y'
            gen double hi_`y' = b_`y' + invttail(`dfr', .025) * se_`y'

            gen byte sig_`y'  = 2 * ttail(`dfr', abs(b_`y' / se_`y')) < .10 if se_`y' < .
            gen double b_sig_`y' = b_`y' if sig_`y' == 1
            gen double b_ins_`y' = b_`y' if sig_`y' == 0
            gen double b_ref_`y' = b_`y' if se_`y' >= . & b_`y' == 0
        }

        qui summarize lo_env_risk
        local ymin = r(min)
        qui summarize lo_geo_risk
        local ymin = min(`ymin', r(min))
        qui summarize lo_social_risk
        local ymin = min(`ymin', r(min)) - .02

        qui summarize hi_env_risk
        local ymax = r(max)
        qui summarize hi_geo_risk
        local ymax = max(`ymax', r(max))
        qui summarize hi_social_risk
        local ymax = max(`ymax', r(max)) + .02

        *** Keep only months -3 to 12 for Crimea to remove blank space
        if "`e'" == "crimea" {
            drop if month < -3
        }

        gen double band_x  = cond(_n == 1, -0.5, 0.5) if _n <= 2
        gen double band_lo = `ymin' if _n <= 2
        gen double band_hi = `ymax' if _n <= 2

        *** small x-offsets so the three series' error bars don't overlap
        gen double m_env    = month - 0.15
        gen double m_geo    = month
        gen double m_social = month + 0.15

        *** Dummy layer for event month legend box
        gen double dummy_band = .

        local xopts "xlabel(-12(3)12) xscale(range(-12.5 12.5))"
        if "`e'" == "crimea" local xopts "xlabel(-3(3)12) xscale(range(-3.5 12.5))"

        twoway ///
            (rarea band_hi band_lo band_x, color(gs14) lwidth(none)) ///
            (rarea dummy_band dummy_band month, color(gs14) lwidth(none)) ///
            (rcap hi_env_risk    lo_env_risk    m_env,    lcolor(green)) ///
            (rcap hi_geo_risk    lo_geo_risk    m_geo,    lcolor(blue)) ///
            (rcap hi_social_risk lo_social_risk m_social, lcolor(orange)) ///
            (scatter b_sig_env_risk    m_env,    msymbol(O)  msize(medsmall) mcolor(green)) ///
            (scatter b_ins_env_risk    m_env,    msymbol(Oh) msize(medsmall) mcolor(green)) ///
            (scatter b_sig_geo_risk    m_geo,    msymbol(S)  msize(medsmall) mcolor(blue)) ///
            (scatter b_ins_geo_risk    m_geo,    msymbol(Sh) msize(medsmall) mcolor(blue)) ///
            (scatter b_sig_social_risk m_social, msymbol(T)  msize(medsmall) mcolor(orange)) ///
            (scatter b_ins_social_risk m_social, msymbol(Th) msize(medsmall) mcolor(orange)) ///
            , yline(0, lpattern(dash) lcolor(gs8)) ///
            `xopts' ///
            xtitle("Months relative to event") ///
            ytitle("Effect on P(risk)") ///
            title("`lbl_`e''", size(medium)) ///
            legend(order(6 "Environmental (p < 0.10)" 7 "Environmental (p {&ge} 0.10)" ///
                         8 "Geopolitical (p < 0.10)"  9 "Geopolitical (p {&ge} 0.10)" ///
                         10 "Social (p < 0.10)"        11 "Social (p {&ge} 0.10)" ///
                         2 "event month") ///
                pos(6) cols(2) size(vsmall) region(lstyle(none))) ///
            xsize(7) ysize(4) plotregion(margin(zero)) ///
            graphregion(color(white)) bgcolor(white)
        graph export "${fig_dir}/fig_es_`e'_combined.pdf", replace
    restore
}


********************************************************************************
*** II. PARTY CONVERGENCE — party x post_ukraine, 19th + 20th WP
********************************************************************************

eststo clear

foreach y of local outcomes {
    reghdfe `y' ib2.party_f##i.post_ukraine i.opposition i.govt_speaker ///
        if inlist(wp, 19, 20), absorb(wp) vce(cluster speaker_id)
    eststo conv_`y'

    *** joint test: did party gaps change post-Ukraine?
    qui testparm i(1 3 4 5 6).party_f#1.post_ukraine
    di as txt "`y' — joint test party x post: F = " %6.2f r(F) ///
        ", p = " %6.4f r(p)
}

esttab conv_env_risk conv_geo_risk conv_social_risk ///
    using "${tab_dir}/tabD_convergence.tex", replace ///
    booktabs b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    mtitles("Env." "Geo." "Social") ///
    stats(N N_clust r2_a, fmt(%9.0fc %9.0fc %9.3f) ///
          labels("Observations" "Speakers (clusters)" "Adj. R$^2$")) ///
    title("Party convergence after the 2022 invasion (LPM, 19th--20th WP)") ///
    addnotes("Base party: CDU/CSU. WP FE included; post-Ukraine main effect" ///
             "identified within the 20th WP. SE clustered by speaker.") ///
    label nobaselevels eqlabels(none) interaction(" $\times$ ")

esttab conv_env_risk conv_geo_risk conv_social_risk, ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) label nobaselevels

log close