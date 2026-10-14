********************************************************************************
* 01_speaker_crosswalk.do
*
* Link speaker names to the official IDs of the Members of the Bundestag.
*
* Input:  data/regression/Logit_panel_dataset.xlsx, data/raw/MdB-Stammdaten/
* Output: data/regression/speaker_crosswalk.csv
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
global xml      "${raw_dir}/MdB-Stammdaten/MDB_STAMMDATEN.XML"

log using "${log_dir}/01_speaker_crosswalk.log", replace text

*** helper: accent-folded, lower-cased, space-collapsed name normalization
capture program drop normvar
program define normvar
    args src dst
    gen `dst' = ustrlower(ustrregexra(ustrnormalize(`src', "nfd"), "\p{Mn}", ""))
    replace `dst' = stritrim(strtrim(`dst'))
end

********************************************************************************
*** I. PARSE STAMMDATEN XML (line-wise)
********************************************************************************

import delimited using "${xml}", delimiter("\t") varnames(nonames) ///
    encoding(utf-8) bindquote(nobind) stringcols(_all) clear
rename v1 line
replace line = strtrim(line)
di as txt "XML lines read: " _N

gen long mdb_n  = sum(line == "<MDB>")
gen long name_n = sum(line == "<NAME>")

foreach t in ID VORNAME ADEL PRAEFIX NACHNAME PARTEI_KURZ WP {
    gen str244 x_`t' = ustrregexs(1) if ustrregexm(line, "^<`t'>(.*)</`t'>$")
}

preserve     // --- MDB-level: id, party ---
    keep if !missing(x_ID) | !missing(x_PARTEI_KURZ)
    collapse (firstnm) mdb_id = x_ID pk = x_PARTEI_KURZ, by(mdb_n)
    replace pk = "" if missing(pk)
    tempfile mdbinfo
    save `mdbinfo'
restore

preserve     // --- WP memberships per MDB ---
    keep if !missing(x_WP)
    gen int wp = real(x_WP)
    keep mdb_n wp
    duplicates drop
    tempfile wps
    save `wps'

    * person-level flag: any seat since WP 14 (any-pool guard)
    gen byte w14 = wp >= 14
    collapse (max) has14 = w14, by(mdb_n)
    tempfile has14
    save `has14'
restore

*** --- name variants per NAME block ---
keep if !missing(x_VORNAME) | !missing(x_ADEL) | !missing(x_PRAEFIX) ///
      | !missing(x_NACHNAME)
collapse (firstnm) vor = x_VORNAME adel = x_ADEL prae = x_PRAEFIX ///
    nach = x_NACHNAME (max) mdb_n, by(name_n)
foreach v in vor adel prae nach {
    replace `v' = "" if missing(`v')
}
gen full = stritrim(strtrim(vor + " " + adel + " " + prae + " " + nach))
normvar full fn_norm
normvar vor  vn_norm

*** particle-stripped variant (same token list as 16.py; applied to the
*** normalized string, padded with spaces; 3 passes catch stacked particles)
gen fs = " " + fn_norm + " "
forvalues p = 1/3 {
    foreach t in von van de der den zu graf gräfin freiherr freifrau in {
        replace fs = subinstr(fs, " `t' ", " ", .)
    }
}
replace fs = stritrim(strtrim(fs))

keep mdb_n full fn_norm vn_norm fs
gen long vrow = _n
expand 2 if fs != fn_norm, gen(is_strip)
replace fn_norm = fs if is_strip == 1
drop fs is_strip vrow

merge m:1 mdb_n using `mdbinfo', keep(match) nogen

preserve     // --- pool A: variants x WP membership, WP 18–21 ---
    joinby mdb_n using `wps'
    keep if inrange(wp, 18, 21)
    keep wp fn_norm vn_norm mdb_id pk full
    duplicates drop
    tempfile pool_wp
    save `pool_wp'
restore

*** --- pool B: any-WP person pool (seat since WP 14) ---
merge m:1 mdb_n using `has14', keep(match) nogen
keep if has14 == 1
keep fn_norm vn_norm mdb_id pk full
duplicates drop
gen byte k1 = 1
tempfile pool_any
save `pool_any'

use `pool_wp', clear
forvalues w = 18/21 {
    qui duplicates report mdb_id if wp == `w'
    di as txt "WP `w': " r(unique_value) " MdBs in pool"
}

********************************************************************************
*** II. PANEL CELLS
********************************************************************************

import excel using "${proc_dir}/Logit_panel_dataset.xlsx", ///
    firstrow case(preserve) clear
gen int wp = real(substr(period, 1, 2))
contract speaker wp party, freq(n_speeches)
normvar speaker cell_norm
gen long cellid = _n
di as txt "panel (speaker, wp, party) cells: " _N
tempfile unmatched
save `unmatched'

********************************************************************************
*** III. STAGED MATCHING (exact -> prefix -> firstnames -> *_any)
********************************************************************************

tempfile results
gen str12 match_type = ""
gen str244 mdb_id = ""
gen str244 official_name = ""
drop if 1     // empty results shell
save `results', emptyok

foreach kind in exact prefix firstnames exact_any prefix_any {

    use `unmatched', clear
    qui count
    if r(N) == 0 continue
    local base = subinstr("`kind'", "_any", "", .)

    if strpos("`kind'", "_any") {
        gen byte k1 = 1
        joinby k1 using `pool_any', unmatched(master)
        drop k1
    }
    else joinby wp using `pool_wp', unmatched(master)

    gen byte hit = 0
    if "`base'" == "exact"      replace hit = fn_norm == cell_norm
    if "`base'" == "prefix"     replace hit = strpos(fn_norm, cell_norm + " ") == 1
    if "`base'" == "firstnames" replace hit = vn_norm == cell_norm
    replace hit = 0 if _merge != 3
    drop _merge

    *** one candidate row per (cell, MdB id)
    gsort cellid mdb_id -hit
    by cellid mdb_id: replace hit = 0 if _n > 1 & !missing(mdb_id)

    *** lenient party compatibility (tie-break only)
    gen byte pok = hit & ( ///
        (party == "CDU/CSU" & inlist(pk, "CDU", "CSU")) | ///
        (party == "SPD"     & inlist(pk, "SPD", "Plos")) | ///
        (party == "Grüne"   & inlist(pk, "BÜNDNIS 90/DIE GRÜNEN", "Plos")) | ///
        (party == "Linke"   & inlist(pk, "DIE LINKE.", "BSW", "Plos", "Die PARTEI")) | ///
        (party == "AfD"     & inlist(pk, "AfD", "Plos", "LKR")) | ///
        (party == "FDP"     & inlist(pk, "FDP", "Plos")) )

    egen ncand = total(hit), by(cellid)
    egen npok  = total(pok), by(cellid)
    gen byte eff  = cond(npok >= 1, pok, hit)
    egen neff  = total(eff), by(cellid)

    gen byte winner = eff & neff == 1
    gen byte amb    = ncand > 0 & neff > 1

    gsort cellid -winner
    by cellid: keep if _n == 1

    *** matched and ambiguous cells -> results; the rest continue
    preserve
        keep if winner | amb
        gen str12 mt = cond(winner, "`kind'", "ambiguous")
        replace mdb_id = "" if amb
        replace full   = "" if amb
        keep speaker wp party n_speeches cellid mdb_id full mt
        rename (full mt) (official_name match_type)
        append using `results'
        save `results', replace
        qui count if match_type == "`kind'"
        di as txt "stage `kind': " r(N) " cells matched"
    restore
    keep if !winner & !amb
    keep speaker wp party n_speeches cellid cell_norm
    save `unmatched', replace
}

*** leftovers -> 'none'
use `unmatched', clear
qui count
if r(N) > 0 {
    gen str244 mdb_id = ""
    gen str244 official_name = ""
    gen str12 match_type = "none"
    drop cell_norm
    append using `results'
    save `results', replace
}

use `results', clear
sort speaker wp party
tab match_type
qui count if mdb_id != ""
di as txt "cells matched: " r(N) " of " _N
export delimited using "${proc_dir}/speaker_crosswalk.csv", replace

log close

