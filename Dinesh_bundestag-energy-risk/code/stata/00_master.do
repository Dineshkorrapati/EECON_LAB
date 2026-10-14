********************************************************************************
* 00_master.do
*
* Run all regression analyses in order.
*
* Start Stata in the repository's main folder and run:
*     do code/stata/00_master.do
*
* Required packages: ssc install estout, ssc install ftools, ssc install reghdfe
********************************************************************************

clear all
set more off
global root "`c(pwd)'"

capture confirm file "$root/README.md"
if _rc {
    display as error "Run this file from the repository root (the folder containing README.md)."
    exit 601
}

capture mkdir "$root/results/logs"
capture mkdir "$root/results/tables"
capture mkdir "$root/results/figures"

do "$root/code/stata/01_speaker_crosswalk.do"
do "$root/code/stata/02_prep_regression.do"
do "$root/code/stata/03_logit_main.do"
do "$root/code/stata/04_hdfe.do"
do "$root/code/stata/05_eventstudy.do"
do "$root/code/stata/06_robustness_election_pooled.do"
do "$root/code/stata/07_robustness_election_clogit.do"
do "$root/code/stata/08_lpm_speaker_month_fe.do"
