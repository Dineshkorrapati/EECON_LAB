"""
Create the descriptive tables reported in the paper.

Input:  data/classified/output_{period}.jsonl (via data_loader.py)
Output: results/tables/descriptive/
Run:    python code/08_descriptive_tables.py
"""

import os
from pathlib import Path
import pandas as pd
from data_loader import (
    load_and_prepare_data, PERIODS4, MAIN_PARTIES6, MAIN_PARTIES4,
    TOPIC_LABELS, RISK_LABELS, SOURCE_LABELS,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "tables" / "descriptive"
os.makedirs(OUT_DIR, exist_ok=True)

df, df_energy = load_and_prepare_data()

print("=" * 70)
print(f"Total rows loaded: {len(df)}")
print(f"Energy-central rows: {len(df_energy)}")
print(f"Party breakdown (energy-central):\n{df_energy['party'].value_counts()}")
print("=" * 70)


def save_tex(name, body):
    path = os.path.join(OUT_DIR, f"{name}.tex")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"  -> wrote {path}")


# ============================================================================
# TABLE 1 (tab:corpus): Corpus overview by Bundestag period
# ============================================================================

print("\n--- Table: Corpus overview by Bundestag period ---")

period_years = {
    "18th": "2013--2017", "19th": "2017--2021",
    "20th": "2021--2025", "21st": "2025",
}

# Raw speeches per period = rows in the cleaned files written by
# code/02_clean_and_split_periods.py. Those files are not in the repository
# (size), so the recorded counts are used when they are absent.
INTERIM = Path(__file__).resolve().parents[1] / "data" / "interim"
RAW_FILES = {
    "18th": "18th_Bundestag_bundestag_plenary_speeches_2013_2017.xlsx",
    "19th": "19th_Bundestag_bundestag_plenary_speeches_2017_2021.xlsx",
    "20th": "20th_Bundestag_bundestag_plenary_speeches_2021_2025.xlsx",
    "21st": "21st_Bundestag_bundestag_plenary_speeches_2025_Dec_2025.xlsx",
}
RAW_RECORDED = {"18th": 18391, "19th": 26801, "20th": 26381, "21st": 6075}


def raw_count(period):
    f = INTERIM / RAW_FILES[period]
    return len(pd.read_excel(f, usecols=[0])) if f.exists() else RAW_RECORDED[period]


df6 = df[df["party"].isin(MAIN_PARTIES6)]
df6_energy = df_energy[df_energy["party"].isin(MAIN_PARTIES6)]

corpus_rows = []
for period in PERIODS4:
    raw = raw_count(period)
    keyword = len(df6[df6["period"] == period])
    energy_central = len(df6_energy[df6_energy["period"] == period])
    rate = 100 * energy_central / keyword if keyword else float("nan")
    corpus_rows.append((period, period_years[period], raw, keyword, energy_central, rate))

corpus_df = pd.DataFrame(
    corpus_rows, columns=["period", "years", "raw", "keyword", "energy_central", "rate"]
)
print(corpus_df.to_string(index=False))

raw_all = corpus_df["raw"].sum()
keyword_all = corpus_df["keyword"].sum()
energy_all = corpus_df["energy_central"].sum()
rate_all = 100 * energy_all / keyword_all

tex = r"""\begin{table}[H]
\centering
\caption{Corpus construction by Bundestag period}
\label{tab:corpus}
\begin{threeparttable}
\begin{tabular}{lrrrrr}
\toprule
Period & Years & Raw speeches & Keyword-filtered & Energy-central & Central rate \\
\midrule
"""
for _, r in corpus_df.iterrows():
    tex += (f"{r['period']} Bundestag & {r['years']} & {r['raw']:,} & "
            f"{r['keyword']:,} & {r['energy_central']:,} & "
            f"{r['rate']:.1f}\\% \\\\\n")
tex += r"\midrule" + "\n"
tex += (f"\\textbf{{Total}} & 2013--2025 & \\textbf{{{raw_all:,}}} & "
        f"\\textbf{{{keyword_all:,}}} & \\textbf{{{energy_all:,}}} & "
        f"\\textbf{{{rate_all:.1f}\\%}} \\\\\n")
tex += r"""\bottomrule
\end{tabular}
\end{threeparttable}
\end{table}
"""
save_tex("tab_corpus", tex)


# ============================================================================
# TABLE (tab:risk_period): Risk type distribution across Bundestag periods
# (% of ALL energy-central speeches, not restricted to six main parties)
# ============================================================================

print("\n--- Table: Risk type distribution across Bundestag periods ---")

risk_period_rows = []
for risk in RISK_LABELS:
    row = [risk]
    for period in PERIODS4:
        sub = df_energy[df_energy["period"] == period]
        pct = 100 * sub[risk].mean() if len(sub) else float("nan")
        row.append(pct)
    risk_period_rows.append(row)

risk_period_df = pd.DataFrame(
    risk_period_rows, columns=["risk_type"] + PERIODS4
).set_index("risk_type")
print(risk_period_df.round(1).to_string())

label_map = {
    "environmental_risk": "Environmental risk [\\%]",
    "geopolitical_risk": "Geopolitical risk [\\%]",
    "social_risk": "Social risk [\\%]",
}
tex = r"""\begin{table}[H]
    \centering
    \begin{tabular}{lcccc}
        \toprule
        Risk type & 18th & 19th & 20th & 21st \\
        \midrule
"""
for risk in RISK_LABELS:
    vals = " & ".join(f"{risk_period_df.loc[risk, p]:.1f}" for p in PERIODS4)
    tex += f"        {label_map[risk]} & {vals} \\\\\n"
tex += r"""        \bottomrule
    \end{tabular}
    \caption{Risk type distribution across Bundestag periods
    (\% of energy-central speeches)}
    \label{tab:risk_period}
\end{table}
"""
save_tex("tab_risk_period", tex)


# ============================================================================
# TABLE (tab:topic_period): Topic distribution across Bundestag periods
# (% of energy-central speeches, six main parties)
# ============================================================================

print("\n--- Table: Topic distribution across Bundestag periods (six main parties) ---")

df6 = df_energy[df_energy["party"].isin(MAIN_PARTIES6)]

topic_period_rows = []
for topic in TOPIC_LABELS:
    row = [topic]
    for period in PERIODS4:
        sub = df6[df6["period"] == period]
        has_topic = sub["topics"].apply(lambda x: topic in x)
        pct = 100 * has_topic.mean() if len(sub) else float("nan")
        row.append(pct)
    topic_period_rows.append(row)

topic_period_df = pd.DataFrame(
    topic_period_rows, columns=["topic"] + PERIODS4
).set_index("topic")
print(topic_period_df.round(1).to_string())

topic_label_map = {
    "renewables_and_grid": "Renewables and grid [\\%]",
    "climate_policy": "Climate policy [\\%]",
    "coal_and_regions": "Coal and regions [\\%]",
    "energy_prices": "Energy prices [\\%]",
    "energy_security": "Energy security [\\%]",
    "nuclear": "Nuclear [\\%]",
}
tex = r"""\begin{table}[H]
    \centering
    \begin{tabular}{lcccc}
        \toprule
        Topic & 18th & 19th & 20th & 21st \\
        \midrule
"""
for topic in TOPIC_LABELS:
    vals = " & ".join(f"{topic_period_df.loc[topic, p]:.1f}" for p in PERIODS4)
    tex += f"        {topic_label_map[topic]} & {vals} \\\\\n"
tex += r"""        \bottomrule
    \end{tabular}
    \caption{Topic distribution across Bundestag periods
    (\% of energy-central speeches, six main parties)}
    \label{tab:topic_period}
\end{table}
"""
save_tex("tab_topic_period", tex)


# ============================================================================
# TABLE (tab:risk_party / Table 6): Risk invocation by party and period
# ============================================================================

print("\n--- Table: Risk invocation by party and period ---")

PARTY_ORDER = ["Linke", "SPD", "Grüne", "FDP", "CDU/CSU", "AfD"]

risk_party_data = {}
for risk in RISK_LABELS:
    for party in PARTY_ORDER:
        for period in PERIODS4:
            sub = df_energy[
                (df_energy["party"] == party) & (df_energy["period"] == period)
            ]
            pct = 100 * sub[risk].mean() if len(sub) else None
            risk_party_data[(risk, party, period)] = pct

risk_party_df = pd.DataFrame(
    [(r, p, per, v) for (r, p, per), v in risk_party_data.items()],
    columns=["risk_type", "party", "period", "pct"],
)
print(risk_party_df.pivot_table(
    index=["risk_type", "party"], columns="period", values="pct"
)[PERIODS4].round(1).to_string())

risk_type_titles = {
    "environmental_risk": "Environmental [\\%]",
    "geopolitical_risk": "Geopolitical [\\%]",
    "social_risk": "Social [\\%]",
}
tex = r"""\begin{table}[H]
    \centering
    \begin{tabular}{llcccc}
        \toprule
        Risk type & Party & 18th & 19th & 20th & 21st \\
        \midrule
"""
for risk in RISK_LABELS:
    tex += f"        \\multirow{{6}}{{*}}{{{risk_type_titles[risk]}}}\n"
    for party in PARTY_ORDER:
        vals = []
        for period in PERIODS4:
            v = risk_party_data[(risk, party, period)]
            vals.append("---" if v is None else f"{v:.1f}")
        vals_str = " & ".join(vals)
        party_tex = party.replace("Grüne", "Gr\\\"{u}ne")
        tex += f"        & {party_tex}     & {vals_str} \\\\\n"
    tex += "        \\midrule\n"
tex = tex.rstrip("\\midrule\n") + "\n"
tex += r"""        \bottomrule
    \end{tabular}
    \caption{Risk invocation by party and period
    (\% of each party's energy speeches). Party order follows the
    political spectrum, left to right. AfD entered parliament in the
    19th Bundestag; FDP held no seats in the 18th or 21st Bundestag.}
    \label{tab:risk_party}
\end{table}
"""
save_tex("tab_risk_party", tex)


# ============================================================================
# TABLE (tab:risk_source / Table 7): Risk invocation by energy source,
# party, and period, CDU/CSU vs Grüne
# ============================================================================

print("\n--- Table: Risk invocation by energy source, CDU/CSU vs Grüne ---")

TWO_PARTIES = ["Grüne", "CDU/CSU"]

source_rows = []
for source in SOURCE_LABELS:
    for period in PERIODS4:
        row = {"source": source, "period": period}
        for risk in RISK_LABELS:
            for party in TWO_PARTIES:
                sub = df_energy[
                    (df_energy["party"] == party)
                    & (df_energy["period"] == period)
                    & (df_energy["energy_sources"].apply(lambda x: source in x))
                ]
                pct = 100 * sub[risk].mean() if len(sub) else float("nan")
                n = len(sub)
                row[f"{risk}_{party}"] = pct
                row[f"{risk}_{party}_n"] = n
        source_rows.append(row)

source_df = pd.DataFrame(source_rows)
print(source_df.round(1).to_string(index=False))

source_title_map = {
    "coal": "Coal", "natural_gas": "Natural gas",
    "nuclear": "Nuclear", "wind": "Wind",
}
tex = r"""\begin{table}[H]
    \centering
    \begin{threeparttable}
    \begin{tabular}{llcccccc}
        \toprule
        & & \multicolumn{2}{c}{Environmental [\%]}
        & \multicolumn{2}{c}{Geopolitical [\%]}
        & \multicolumn{2}{c}{Social [\%]} \\
        \cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}
        Source & Period & Gr\"{u}ne & CDU/CSU & Gr\"{u}ne & CDU/CSU
               & Gr\"{u}ne & CDU/CSU \\
        \midrule
"""
min_n, max_n, min_cell, max_cell = None, None, None, None
for source in SOURCE_LABELS:
    tex += f"        \\multirow{{4}}{{*}}{{{source_title_map[source]}}}\n"
    for _, r in source_df[source_df["source"] == source].iterrows():
        vals = []
        for risk in RISK_LABELS:
            for party in TWO_PARTIES:
                v = r[f"{risk}_{party}"]
                n = r[f"{risk}_{party}_n"]
                vals.append(f"{v:.0f}" if not pd.isna(v) else "---")
                if not pd.isna(v):
                    if min_n is None or n < min_n:
                        min_n, min_cell = n, (source, r["period"], risk, party)
                    if max_n is None or n > max_n:
                        max_n, max_cell = n, (source, r["period"], risk, party)
        vals_str = " & ".join(vals)
        tex += f"        & {r['period']} & {vals_str} \\\\\n"
    tex += "        \\midrule\n"
tex = tex.rstrip("\\midrule\n") + "\n"
note = (f"Each cell shows the percentage of a party's speeches discussing "
        f"that source which invoke the corresponding risk type, by Bundestag "
        f"period. Sample sizes vary considerably by cell, from $n={min_n}$ "
        f"({min_cell[3]}, {min_cell[0].replace('_', ' ')}, {min_cell[1]}) to "
        f"$n={max_n}$ ({max_cell[3]}, {max_cell[0].replace('_', ' ')}, "
        f"{max_cell[1]}).")
tex += r"""    \end{tabular}
    \begin{tablenotes}
    \small
    \item """ + note + r"""
    \end{tablenotes}
    \end{threeparttable}
    \caption{Risk invocation by energy source, party, and period,
    Gr\"{u}ne vs. CDU/CSU}
    \label{tab:risk_source}
\end{table}
"""
save_tex("tab_risk_source", tex)


# ============================================================================
# TABLE (tab:geo_gas / Table 8): Natural gas speeches within the broader
# energy debate, by year (main four parties)
# ============================================================================

print("\n--- Table: Natural gas speeches within the broader energy debate (4-party) ---")

df4 = df_energy[df_energy["party"].isin(MAIN_PARTIES4)]
gas4 = df4[df4["energy_sources"].apply(lambda x: "natural_gas" in x)]

years = sorted(gas4["year"].unique())
total_N_by_year = df4.groupby("year").size()
n_by_year = gas4.groupby("year").size()
share_by_year = 100 * n_by_year / total_N_by_year
pct_by_year = 100 * gas4.groupby("year")["geopolitical_risk"].mean()

gas_year_df = pd.DataFrame({
    "total_N": total_N_by_year, "gas_n": n_by_year,
    "gas_share_pct": share_by_year, "geo_risk_pct": pct_by_year,
})
print(gas_year_df.round(1).to_string())

# Only the three events with a defined date elsewhere in this codebase
# (matching post_crimea/post_ns2/post_ukraine in the regression
# pipeline) are filled in automatically. Every other year's "Key
# Event" cell is left blank on purpose.
DATED_EVENTS = {
    2014: "Crimea annexation (18.03.2014)",
    2019: "US Nord Stream 2 sanctions (21.12.2019)",
    2022: "Ukraine invasion; supply cut (24.02.2022)",
}

tex = r"""\begin{table}[t]
    \centering
    \small
    \begin{threeparttable}
    \begin{tabularx}{\linewidth}{l c c c c >{\raggedright\arraybackslash}X}
        \toprule
        Year & \makecell{Total Energy\\Speeches ($N$)} & \makecell{Gas Speeches\\($n$)} & \makecell{Gas Share\\(\%)\tnote{a}} & \makecell{Geopolitical\\Risk (\%)\tnote{b}} & Key Event \\
        \midrule
"""
for year in years:
    N = int(total_N_by_year.get(year, 0))
    n = int(n_by_year.get(year, 0))
    share = share_by_year.get(year, float("nan"))
    pct = pct_by_year.get(year, float("nan"))
    event = DATED_EVENTS.get(year, "")
    N_str = f"{N:,}".replace(",", "{,}")
    share_str = f"{share:.1f}" if not pd.isna(share) else "---"
    pct_str = f"{pct:.1f}" if not pd.isna(pct) else "---"
    tex += f"        {year} & {N_str} & {n} & {share_str} & {pct_str} & {event} \\\\\n"
tex += r"""        \bottomrule
    \end{tabularx}
    \begin{tablenotes}
        \footnotesize
        \item\tnote{a} Gas Share (\%) = $(n_{\text{gas}} / N_{\text{energy}}) \times 100$ (salience of gas within general energy debates).
        \item\tnote{b} Geopolitical Risk (\%) = percentage of gas speeches ($n$) containing geopolitical risk frames.
    \end{tablenotes}
    \caption{Natural gas speeches within the broader energy debate, by year (main four parties)}
    \label{tab:geo_gas}
    \end{threeparttable}
\end{table}
"""
save_tex("tab_geo_gas", tex)

print("\n" + "=" * 70)
print(f"All tables written to {OUT_DIR}")
print("=" * 70)
