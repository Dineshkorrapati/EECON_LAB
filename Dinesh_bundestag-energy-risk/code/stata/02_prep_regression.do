********************************************************************************
* 02_prep_regression.do
*
* Prepare the regression dataset.
*
* Creates the party, opposition, election-timing and event variables used in
* the regressions.
*
* Input:  data/regression/Logit_panel_dataset.xlsx, speaker_crosswalk.csv,
*         wordcount_speaker_day.csv
* Output: data/regression/regression_panel.dta
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

log using "${log_dir}/02_prep_regression.log", replace text

********************************************************************************
*** I. IMPORT 
********************************************************************************

import excel using "${proc_dir}/Logit_panel_dataset.xlsx", ///
    firstrow case(preserve) clear

count
assert `r(N)' == 8564

*** speech_date: import excel may deliver %td (daily) or %tc (datetime) —
*** convert format-robustly and verify the year range
local fmt : format speech_date
if strpos("`fmt'", "tc") gen long date = dofc(speech_date)
else                     gen long date = speech_date
format date %tdDD.Mon.CCYY
assert !missing(date)
assert inrange(year(date), 2013, 2026)
drop speech_date
rename date speech_date

*** legislative period 18/19/20/21
gen byte wp = real(substr(period, 1, 2))
assert inlist(wp, 18, 19, 20, 21)

*** UTF-8 check: umlauts must have survived import (Grüne)
qui count if party == "Grüne"
di as txt "UTF-8 check — rows with party 'Grüne': " r(N)
assert r(N) > 0


********************************************************************************
*** II. VALIDATION OF DELIVERED CODING
********************************************************************************

*** II.1 duplicates: speaker x date (multiple energy speeches per day possible)
duplicates report speaker speech_date
duplicates tag speaker speech_date, gen(dup_speaker_day)
qui count if dup_speaker_day > 0
di as txt "obs on speaker-days with >1 energy speech: " r(N)

*** II.2 opposition coding: list every within-party status change with its date
*** Expected (day-precise government formations):
***   Merkel III sworn in 17dec2013 (SPD Opp→Reg within 18th WP)
***   Merkel IV sworn in 14mar2018 (caretaker before: coding to be inspected)
***   Scholz sworn in 08dec2021 (CDU/CSU Reg→Opp, Grüne/FDP Opp→Reg within 20th)
***   FDP leaves coalition 06nov2024 (FDP Reg→Opp within 20th)
***   Merz sworn in 06may2025 (SPD stays Reg, Grüne Reg→Opp within 21st)
preserve
    keep party speech_date opposition
    duplicates drop
    sort party speech_date opposition
    collapse (mean) opposition, by(party speech_date)
    bysort party (speech_date): gen switch = opposition != opposition[_n-1] & _n > 1
    di as txt _n "=== opposition status switches by party (date, new status) ==="
    list party speech_date opposition if switch, noobs sepby(party)
restore

*** II.2b DOCUMENTED CORRECTION:
*** Michael Kretschmer (CDU/CSU, guest speaker, 03jul2020) is the single
*** observation coded opposition=1 while CDU/CSU was governing — the only
*** mixed party-day in the data. Set to 0 (CDU/CSU in government on that day).
qui count if party == "CDU/CSU" & speech_date == td(03jul2020) & opposition == 1
di as txt "Kretschmer correction — obs affected: " r(N)
assert r(N) == 1
replace opposition = 0 if party == "CDU/CSU" & speech_date == td(03jul2020) ///
    & opposition == 1

*** II.3 cross-check reconstructed vs delivered running variables (below, III.4)

*** II.4 sample composition vs manuscript Table 1
tab period
tab party
tab opposition
tabstat env_risk geo_risk social_risk, by(period) format(%9.3f)


********************************************************************************
*** III. VARIABLE CONSTRUCTION
********************************************************************************

*** III.1 party factor (base CDU/CSU), government-member speaker flag
encode party, gen(party_f)
label list party_f
gen byte govt_speaker = speaker_role != "MdB"
label var govt_speaker "Government member"

*** III.1b stable speaker identity via official MdB IDs.
*** Crosswalk from the Bundestag's open master data (data/raw/MdB-Stammdaten;
*** https://www.bundestag.de/services/opendata), built by
*** 01_speaker_crosswalk.do. Unmatched speakers (non-MdB ministers,
*** Länder guests, chair strings) keep their name string as identity.
preserve
    import delimited using "${proc_dir}/speaker_crosswalk.csv", ///
        clear varnames(1) encoding(utf-8) bindquote(strict)
    keep speaker wp party mdb_id match_type
    gen str244 speaker_s = strtrim(speaker)
    drop speaker
    rename speaker_s speaker
    duplicates report speaker wp party
    assert `r(unique_value)' == `r(N)'
    tempfile cw
    save `cw'
restore
merge m:1 speaker wp party using `cw', keep(master match) gen(_mcw)
qui count if _mcw == 1
di as txt "panel obs without crosswalk row (expect 0): " r(N)
assert r(N) == 0
drop _mcw

gen str300 speaker_uid = cond(!missing(mdb_id), ///
    "MDB_" + string(mdb_id, "%12.0f"), "NM_" + speaker)
egen long speaker_id = group(speaker_uid)
label var speaker_uid "Stable speaker identity (MDB_<id> from Stammdaten, else NM_<name>)"
label var mdb_id      "Official MdB ID (Bundestag Stammdaten); missing for non-MdB"
qui duplicates report speaker
local n_str = r(unique_value)
qui duplicates report speaker_id
di as txt "speaker identities: " r(unique_value) " (from `n_str' name strings)"
gen int ym = mofd(speech_date)
format ym %tm

*** III.2 time to NEXT election (monotone countdown; ex-post actual dates)
gen long next_election = .
replace next_election = td(24sep2017) if speech_date <= td(24sep2017)
replace next_election = td(26sep2021) if speech_date >  td(24sep2017) & speech_date <= td(26sep2021)
replace next_election = td(23feb2025) if speech_date >  td(26sep2021) & speech_date <= td(23feb2025)
replace next_election = td(25mar2029) if speech_date >  td(23feb2025)
format next_election %tdDD.Mon.CCYY

gen days_to_next_election  = next_election - speech_date
assert days_to_next_election > 0
gen years_to_election = days_to_next_election / 365.25
label var years_to_election "Years to next election"

*** III.3 events
local d_crimea  = td(18mar2014)
local d_ns2     = td(21dec2019)
local d_ukraine = td(24feb2022)

gen byte post_crimea  = speech_date >= `d_crimea'
gen byte post_ns2     = speech_date >= `d_ns2'
gen byte post_ukraine = speech_date >= `d_ukraine'
label var post_crimea  "Post Crimea (18.03.2014)"
label var post_ns2     "Post NS2 sanctions (21.12.2019)"
label var post_ukraine "Post Ukraine invasion (24.02.2022)"

*** event time in exact DAYS and day-based quarters (for 05_eventstudy.do).
*** Calendar-month binning would code speeches given in the event month but
*** BEFORE the event day (44 Ukraine, 31 NS2) as post-event. Day-based bins
*** classify every speech by its true position relative to the event.
foreach e in crimea ns2 ukraine {
    gen int evd_`e' = speech_date - `d_`e''
    gen int evq_`e' = floor(evd_`e' / 91.3125)
    label var evd_`e' "Days relative to `e' event (exact)"
    label var evq_`e' "Quarters relative to `e' event (day-based, 91.3125d)"
}
*** check: no pre-event day may sit in a non-negative quarter
assert !(evd_ukraine < 0 & evq_ukraine >= 0)
assert !(evd_ns2     < 0 & evq_ns2     >= 0)
assert !(evd_crimea  < 0 & evq_crimea  >= 0)

*** III.4 cross-check against delivered nearest-distance variables
*** delivered var = distance to nearest election → equals our reconstruction
*** in the half-period BEFORE an election (where it is negative)
gen chk = -days_to_next_election
qui count if days_before_after_election < 0 & chk != days_before_after_election
di as txt "mismatches in pre-election half-windows (expect 0): " r(N)
assert r(N) == 0
drop chk

rename days_before_after_election   days_nearest_election_del
rename days_before_after_major_event days_nearest_event_del
label var days_nearest_election_del "DELIVERED: days to nearest election (do not use)"
label var days_nearest_event_del    "DELIVERED: days to nearest event (do not use)"


********************************************************************************
*** IV. MERGE WORD COUNTS (robustness control only)
********************************************************************************

preserve
    import delimited using "${proc_dir}/wordcount_speaker_day.csv", ///
        clear varnames(1) encoding(utf-8) bindquote(strict)
    *** merge keys must be str#, not strL
    gen str244 speaker_s = strtrim(speaker)
    drop speaker
    rename speaker_s speaker
    gen long date = date(speech_date, "YMD")
    assert !missing(date)
    duplicates report speaker speech_date
    assert `r(unique_value)' == `r(N)'
    drop speech_date
    rename date speech_date
    format speech_date %tdDD.Mon.CCYY
    tempfile wc
    save `wc'
restore

merge m:1 speaker speech_date using `wc', keep(master match) gen(_mwc)
tab _mwc
qui count if _mwc == 1
di as txt "panel obs with NO raw-corpus speaker-day match: " r(N)
drop _mwc

*** ambiguous speaker-days (>1 raw speech) carry missing word_count by design
gen ln_wc = ln(word_count) if !missing(word_count) & word_count > 0
label var word_count "Words in speech (only unambiguous speaker-day matches)"
label var ln_wc      "ln(word count)"
qui count if !missing(ln_wc)
di as txt "obs with usable word count: " r(N) " of " _N


********************************************************************************
*** V. LABEL, ORDER, SAVE
********************************************************************************

label var env_risk    "Speech invokes environmental risk (0/1)"
label var geo_risk    "Speech invokes geopolitical risk (0/1)"
label var social_risk "Speech invokes social risk (0/1)"
label var opposition  "Opposition"
label var wp          "Bundestag legislative period"
label var speaker_id  "Speaker group id"
label var ym          "Calendar month"

order speech_date wp period speaker speaker_uid mdb_id speaker_id ///
      party party_f speaker_role ///
      govt_speaker opposition env_risk geo_risk social_risk ///
      years_to_election days_to_next_election next_election ///
      post_crimea post_ns2 post_ukraine evd_crimea evd_ns2 evd_ukraine ///
      evq_crimea evq_ns2 evq_ukraine ///
      word_count ln_wc

compress
save "${proc_dir}/regression_panel.dta", replace

describe
summarize

log close