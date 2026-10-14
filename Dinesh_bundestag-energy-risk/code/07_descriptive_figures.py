"""
Create the descriptive figures reported in the paper.

Input:  data/classified/output_{period}.jsonl (via data_loader.py)
Output: results/figures/
Run:    python code/07_descriptive_figures.py
"""

import numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "results" / "figures"
ADD_DIR = ROOT / "results" / "additional"
FIG_DIR.mkdir(parents=True, exist_ok=True)
ADD_DIR.mkdir(parents=True, exist_ok=True)
import matplotlib.pyplot as plt
from data_loader import (
    load_and_prepare_data, COLORS, PERIODS4, MAIN_PARTIES6, MAIN_PARTIES4,
    SOURCE_LABELS, TOPIC_LABELS, RISK_LABELS,
)

df, df_energy = load_and_prepare_data()

print("Total rows loaded:", len(df))
print("Energy-central rows:", len(df_energy))
print(df_energy["party"].value_counts())
print(df_energy["period"].value_counts())

# ============================================================================
# CHART 1: Total energy-central speeches per year, by party (lollipop chart)
# ============================================================================

df_main = df_energy[df_energy["party"].isin(MAIN_PARTIES6)]
pivot = df_main.groupby(["year", "party"]).size().unstack(fill_value=0)[MAIN_PARTIES6]
pivot.to_csv(ADD_DIR / "energy_speeches_by_party_year.csv")

fig, ax = plt.subplots(figsize=(14, 7.5), facecolor="white")
ax.set_facecolor("white")

years = pivot.index.values
n_parties = len(MAIN_PARTIES6)
width = 0.7
offsets = np.linspace(-width / 2, width / 2, n_parties)

for i, party in enumerate(MAIN_PARTIES6):
    x = years + offsets[i]
    y = pivot[party].values
    ax.vlines(x, 0, y, color=COLORS[party], linewidth=1.3, alpha=0.6, zorder=2)
    ax.scatter(x, y, color=COLORS[party], s=35, zorder=3, label=party)

ax.set_ylabel("Total energy speeches per year", fontsize=11)
ax.set_xticks(years)
ax.set_xticklabels(years, rotation=0, fontsize=9)
ax.grid(axis="y", color="#f0f0f0", linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=6,
          frameon=False, fontsize=10)

# Bundestag period brackets, drawn below the x-axis so they never
# collide with the lollipop sticks. Each bracket spans the actual
# year range that period covers in the data, with a horizontal line
# and small end-ticks, and the period label centered underneath.
period_spans = [
    (2012.6, 2017.4, "18th Bundestag"),
    (2017.6, 2021.4, "19th Bundestag"),
    (2021.6, 2024.4, "20th Bundestag"),
    (2024.6, 2025.4, "21st Bundestag"),
]
trans = ax.get_xaxis_transform()
bracket_y = -0.06
tick_h = 0.015
for x_start, x_end, label in period_spans:
    ax.plot([x_start, x_end], [bracket_y, bracket_y], transform=trans,
            color="gray", linewidth=0.9, clip_on=False)
    ax.plot([x_start, x_start], [bracket_y, bracket_y + tick_h], transform=trans,
            color="gray", linewidth=0.9, clip_on=False)
    ax.plot([x_end, x_end], [bracket_y, bracket_y + tick_h], transform=trans,
            color="gray", linewidth=0.9, clip_on=False)
    ax.text((x_start + x_end) / 2, bracket_y - 0.015, label, transform=trans,
            ha="center", va="top", fontsize=9, color="gray", style="italic")

plt.subplots_adjust(bottom=0.26)
plt.savefig(FIG_DIR / "energy_speeches_by_party.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig)
print("Saved: energy_speeches_by_party.png")

# ============================================================================
# CHART 2: Risk invocation by energy source, party, and period (heatmap)
# ============================================================================

df_energy6 = df_energy[df_energy["party"].isin(MAIN_PARTIES6)].copy()
SOURCE_TITLES = ["Coal", "Natural Gas", "Nuclear", "Wind"]

risk_plot = [
    ("environmental_risk", "Environmental", "Greens"),
    ("social_risk", "Social", "Oranges"),
    ("geopolitical_risk", "Geopolitical", "Blues"),
]

fig2, axes = plt.subplots(4, 3, figsize=(20, 17))

for row, period in enumerate(PERIODS4):
    for col, (risk, rlabel, cmap) in enumerate(risk_plot):
        ax = axes[row, col]
        matrix = []
        for src in SOURCE_LABELS:
            r = []
            for p in MAIN_PARTIES6:
                sub = df_energy6[
                    (df_energy6["party"] == p)
                    & (df_energy6["period"] == period)
                    & (df_energy6["energy_sources"].apply(lambda x: src in x))
                ]
                r.append(sub[risk].mean() * 100 if len(sub) else np.nan)
            matrix.append(r)
        matrix = np.array(matrix)

        im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=90, aspect="auto")
        ax.set_xticks(range(6))
        ax.set_xticklabels(MAIN_PARTIES6, rotation=30, ha="right", fontsize=8)
        ax.set_yticks(range(4))
        ax.set_yticklabels(SOURCE_TITLES, fontsize=9)
        if row == 0:
            ax.set_title(rlabel + " Risk", fontsize=12, fontweight="bold")
        if col == 0:
            ax.set_ylabel(f"{period} Bundestag", fontsize=11, fontweight="bold")
        for i in range(4):
            for j in range(6):
                v = matrix[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                            fontsize=7.5, fontweight="bold",
                            color="white" if v > 45 else "#333")
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(labelsize=7)

plt.tight_layout()
plt.savefig(FIG_DIR / "risk_source_heatmap_full.png", dpi=150, bbox_inches="tight")
plt.close(fig2)
print("Saved: risk_source_heatmap_full.png")

# ============================================================================
# CHART 3: Geopolitical risk invocation by party across periods
#    (grouped bar chart) -> geo_silo_collapse.png
#
# Uses five parties (Linke, SPD, Grüne, FDP, CDU/CSU), not the global
# MAIN_PARTIES4, so FDP is included, it was part of the governing
# coalition (SPD-Grüne-FDP) through the 2022 Ukraine invasion the
# annotation refers to. FDP has no seats in the 18th or 21st
# Bundestag, so its bar is simply absent in those two period groups.
# AfD is excluded here since it has no data for the 18th Bundestag at
# all, which would leave an empty gap in that period's group; AfD
# appears in the other party-ordered figures instead.
# ============================================================================

SILO_PARTIES = ["Linke", "SPD", "Grüne", "FDP", "CDU/CSU"]
df_energy_silo = df_energy[df_energy["party"].isin(SILO_PARTIES)].copy()

geo_matrix = []
for party in SILO_PARTIES:
    row = []
    for period in PERIODS4:
        sub = df_energy_silo[(df_energy_silo["party"] == party) & (df_energy_silo["period"] == period)]
        row.append(sub["geopolitical_risk"].mean() * 100 if len(sub) else np.nan)
    geo_matrix.append(row)
geo_matrix = np.array(geo_matrix)

fig3, ax3 = plt.subplots(figsize=(15, 6.5), facecolor="white")
ax3.set_facecolor("white")

n_parties_max = len(SILO_PARTIES)
n_periods = len(PERIODS4)
bar_width = 0.85 / n_parties_max
x = np.arange(n_periods)

# Bars are packed tightly within each period group using only the
# parties actually present that period, so a missing party (FDP in
# the 18th/21st Bundestag) leaves no empty gap rather than a blank
# reserved slot.
group_edges = {}  # period_idx -> (left_edge_x, right_edge_x) of the group
bar_positions = {}  # (period_idx, party) -> x position, for the bracket step below

for period_idx in range(n_periods):
    present = [(i, party) for i, party in enumerate(SILO_PARTIES)
               if not np.isnan(geo_matrix[i, period_idx])]
    n_present = len(present)
    local_offsets = (np.arange(n_present) - (n_present - 1) / 2) * bar_width
    for (i, party), offset in zip(present, local_offsets):
        x_pos = x[period_idx] + offset
        v = geo_matrix[i, period_idx]
        bar = ax3.bar(x_pos, v, width=bar_width, color=COLORS[party],
                       label=party if period_idx == 0 else None)
        ax3.text(x_pos, v + 0.6, f"{v:.0f}", ha="center", va="bottom", fontsize=10)
        bar_positions[(period_idx, party)] = x_pos
    if n_present:
        group_edges[period_idx] = (
            x[period_idx] + local_offsets[0] - bar_width / 2,
            x[period_idx] + local_offsets[-1] + bar_width / 2,
        )

ax3.set_xticks(x)
ax3.set_xticklabels(PERIODS4, fontsize=13)
ax3.set_ylabel("% of energy speeches with geopolitical risk", fontsize=11)
ax3.grid(axis="y", color="#e8e8e8", linewidth=0.8, linestyle="-", zorder=0)
ax3.set_axisbelow(True)
for spine in ["top", "right"]:
    ax3.spines[spine].set_visible(False)
ax3.spines["left"].set_color("#333333")
ax3.spines["bottom"].set_color("#333333")

# Build the legend from unique handles (avoids duplicate FDP/CDU-etc.
# entries since labels were only set on the first period's bars).
handles, labels = ax3.get_legend_handles_labels()
by_label = dict(zip(labels, handles))
ordered_labels = [p for p in SILO_PARTIES if p in by_label]
ax3.legend([by_label[l] for l in ordered_labels], ordered_labels,
           loc="upper right", ncol=5, frameon=False, fontsize=11,
           bbox_to_anchor=(0.98, 1.02))

# Give extra headroom above the tallest bar so the bracket and
# annotation never overlap a data label.
ymax_bar = np.nanmax(geo_matrix)
ax3.set_ylim(0, ymax_bar * 1.42)

# Bracket spanning the full 20th Bundestag group (Linke through
# CDU/CSU), rather than an arrow pointing at a single party's bar,
# since the "silo collapse" narrative applies to the whole period,
# not just one party.
period_20th_idx = PERIODS4.index("20th")
left_edge, right_edge = group_edges[period_20th_idx]
bracket_y = ymax_bar * 1.12
tick_h = ymax_bar * 0.02

ax3.plot([left_edge, right_edge], [bracket_y, bracket_y],
         color="#c0392b", linewidth=1.3, clip_on=False)
ax3.plot([left_edge, left_edge], [bracket_y - tick_h, bracket_y],
         color="#c0392b", linewidth=1.3, clip_on=False)
ax3.plot([right_edge, right_edge], [bracket_y - tick_h, bracket_y],
         color="#c0392b", linewidth=1.3, clip_on=False)
ax3.text((left_edge + right_edge) / 2, bracket_y + ymax_bar * 0.02,
         "Silo collapse — 2022 Ukraine war", ha="center", va="bottom",
         fontsize=11, color="#c0392b")

plt.tight_layout()
plt.savefig(FIG_DIR / "geo_silo_collapse.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig3)
print("Saved: geo_silo_collapse.png")

# ============================================================================
# CHART 4: Geopolitical risk in natural gas speeches, 2014-2025
#    (dual-axis: geopolitical risk % on left, gas share % of total
#    energy speeches on right) -> geo_gas_timeline.png
#
# Right axis now matches Table 8's "Gas Share (%)" column exactly
# (gas speeches / total energy-central speeches that year, same four
# parties), replacing the earlier raw speech-count axis, so the
# figure and table tell the same story with the same metric.
# ============================================================================

df_energy4 = df_energy[df_energy["party"].isin(MAIN_PARTIES4)].copy()
df_gas4 = df_energy4[
    df_energy4["energy_sources"].apply(lambda x: "natural_gas" in x)
].copy()

years = sorted(df_gas4["year"].unique())
pct_by_year = df_gas4.groupby("year")["geopolitical_risk"].mean() * 100
n_by_year = df_gas4.groupby("year").size()
total_n_by_year = df_energy4.groupby("year").size()
gas_share_by_year = 100 * n_by_year / total_n_by_year

fig4, ax_pct = plt.subplots(figsize=(15, 7.8), facecolor="white")
ax_pct.set_facecolor("white")
ax_share = ax_pct.twinx()

# By default, a twinx() axis renders ABOVE the original axis
# regardless of individual zorder values, since they are separate
# layers. Swap the layering explicitly so the line (on ax_pct) draws
# in front of the bars (on ax_share), and make ax_pct's own background
# patch transparent so it doesn't cover the bars.
ax_share.set_zorder(1)
ax_pct.set_zorder(2)
ax_pct.patch.set_visible(False)

share_values = [gas_share_by_year.get(y, 0) for y in years]
ax_share.bar(years, share_values, width=0.6, color="#d9d9d9", zorder=1,
             label="Gas share of total energy speeches (%)")
ax_share.set_ylabel("Gas share of total energy speeches (%)", fontsize=11,
                     color="#666666")
ax_share.tick_params(axis="y", labelcolor="#666666")
ax_share.spines["top"].set_visible(False)
# Headroom fix: give the bar axis 25% extra space above the tallest bar
ax_share.set_ylim(0, max(share_values) * 1.25 if share_values else 10)

pct_values = [pct_by_year.get(y, np.nan) for y in years]
ax_pct.plot(years, pct_values, color="black", linewidth=2, zorder=3)
ax_pct.scatter(years, pct_values, s=90, facecolor="white",
                edgecolor="black", linewidth=2, zorder=4)

# Only the labels whose data point sits directly on an event line
# (2014, 2019, 2022) actually have a line running through them, so
# only those three get a white background box.
event_years = {2014, 2019, 2022}

for x, v in zip(years, pct_values):
    if not np.isnan(v):
        if x in event_years:
            ax_pct.text(x, v + 4, f"{v:.1f}%", ha="center", fontsize=10, zorder=6,
                        bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
        else:
            ax_pct.text(x, v + 4, f"{v:.1f}%", ha="center", fontsize=10, zorder=6)

ax_pct.set_ylabel("% of natural gas speeches with geopolitical risk", fontsize=11)
ax_pct.set_xticks(years)
ax_pct.set_xticklabels(years, rotation=45, ha="right")
ax_pct.grid(axis="y", color="#f0f0f0", linewidth=0.8, zorder=0)
ax_pct.set_axisbelow(True)
ax_pct.spines["top"].set_visible(False)
valid_pct = [v for v in pct_values if not np.isnan(v)]
ax_pct.set_ylim(0, max(valid_pct) * 1.35 if valid_pct else 100)

events = [
    (2014, "Crimea\nannexation"),
    (2019, "US sanctions\nNord Stream 2"),
    (2022, "Ukraine war\nsupply cut"),
]
for xv, label in events:
    ax_pct.axvline(xv, color="#555555", linestyle="--", linewidth=1.2, zorder=2)
    ax_pct.text(xv + 0.15, ax_pct.get_ylim()[1] * 0.97, label,
                fontsize=10, color="#555555", va="top", ha="left")

period_bounds = [2017.5, 2021.5, 2024.5]
for xb in period_bounds:
    ax_pct.axvline(xb, color="#cccccc", linestyle=":", linewidth=1, zorder=1)

# Bundestag period brackets (same style as the lollipop chart), drawn
# below the x-axis using a blended transform so they stay put
# regardless of the y-data range.
period_spans = [
    (years[0] - 0.4, 2017.4, "18th Bundestag"),
    (2017.6, 2021.4, "19th Bundestag"),
    (2021.6, 2024.4, "20th Bundestag"),
    (2024.6, years[-1] + 0.4, "21st Bundestag"),
]
trans = ax_pct.get_xaxis_transform()
bracket_y = -0.18
tick_h = 0.015
for x_start, x_end, label in period_spans:
    ax_pct.plot([x_start, x_end], [bracket_y, bracket_y], transform=trans,
                color="gray", linewidth=0.9, clip_on=False)
    ax_pct.plot([x_start, x_start], [bracket_y, bracket_y + tick_h], transform=trans,
                color="gray", linewidth=0.9, clip_on=False)
    ax_pct.plot([x_end, x_end], [bracket_y, bracket_y + tick_h], transform=trans,
                color="gray", linewidth=0.9, clip_on=False)
    ax_pct.text((x_start + x_end) / 2, bracket_y - 0.02, label, transform=trans,
                ha="center", va="top", fontsize=9, color="gray", style="italic")

plt.subplots_adjust(bottom=0.30)
plt.savefig(FIG_DIR / "geo_gas_timeline.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig4)
print("Saved: geo_gas_timeline.png")

# ============================================================================
# CHART 5: Risk type distribution across four Bundestag periods
#    (grouped bar chart, all energy-central speeches) -> risk_by_period.png
# ============================================================================

RISK_ORDER = ["environmental_risk", "social_risk", "geopolitical_risk"]
RISK_TITLES = {"environmental_risk": "Environmental Risk",
               "social_risk": "Social Risk",
               "geopolitical_risk": "Geopolitical Risk"}
RISK_COLORS = {"environmental_risk": "#3fa34d",
               "social_risk": "#e08a1e",
               "geopolitical_risk": "#3776ab"}

risk_period_matrix = []
for risk in RISK_ORDER:
    vals = [df_energy[df_energy["period"] == p][risk].mean() * 100 for p in PERIODS4]
    risk_period_matrix.append(vals)
risk_period_matrix = np.array(risk_period_matrix)

fig5b, ax5b = plt.subplots(figsize=(11, 5.5), facecolor="white")
ax5b.set_facecolor("white")

n_risks = len(RISK_ORDER)
bar_width = 0.75 / n_risks
x = np.arange(len(PERIODS4))

for i, risk in enumerate(RISK_ORDER):
    offset = (i - (n_risks - 1) / 2) * bar_width
    bars = ax5b.bar(x + offset, risk_period_matrix[i], width=bar_width,
                     color=RISK_COLORS[risk], label=RISK_TITLES[risk])
    for b, v in zip(bars, risk_period_matrix[i]):
        ax5b.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}",
                   ha="center", va="bottom", fontsize=9)

ax5b.set_xticks(x)
ax5b.set_xticklabels(PERIODS4, fontsize=12)
ax5b.set_ylabel("% of energy speeches", fontsize=11)
ax5b.grid(axis="y", color="#e8e8e8", linewidth=0.8, zorder=0)
ax5b.set_axisbelow(True)
for spine in ["top", "right"]:
    ax5b.spines[spine].set_visible(False)

ax5b.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=3,
            frameon=False, fontsize=10)
plt.tight_layout()
plt.savefig(FIG_DIR / "risk_by_period.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig5b)
print("Saved: risk_by_period.png")

# ============================================================================
# CHART 6: Risk type invocation by party across periods (2x3 grid,
#    all six main parties, matching the paper's own party order)
#    -> risk_by_party.png
# ============================================================================

GRID_PARTIES = ["Linke", "Grüne", "SPD", "FDP", "CDU/CSU", "AfD"]

fig6b, axes6 = plt.subplots(2, 3, figsize=(17, 9), facecolor="white")
axes6 = axes6.flatten()

for idx, party in enumerate(GRID_PARTIES):
    ax = axes6[idx]
    ax.set_facecolor("white")
    sub_party = df_energy[df_energy["party"] == party]

    matrix = []
    for risk in RISK_ORDER:
        vals = [sub_party[sub_party["period"] == p][risk].mean() * 100
                if len(sub_party[sub_party["period"] == p]) else np.nan
                for p in PERIODS4]
        matrix.append(vals)
    matrix = np.array(matrix)

    for i, risk in enumerate(RISK_ORDER):
        offset = (i - (n_risks - 1) / 2) * bar_width
        ax.bar(x + offset, matrix[i], width=bar_width,
               color=RISK_COLORS[risk], label=RISK_TITLES[risk])

    ax.set_xticks(x)
    ax.set_xticklabels(PERIODS4, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_title(party, fontsize=12, fontweight="bold")
    ax.grid(axis="y", color="#e8e8e8", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    if idx % 3 == 0:
        ax.set_ylabel("% of energy speeches", fontsize=10)

handles, labels = axes6[0].get_legend_handles_labels()
fig6b.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.02),
             ncol=3, frameon=False, fontsize=11)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig(FIG_DIR / "risk_by_party.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig6b)
print("Saved: risk_by_party.png")

# ============================================================================
# CHART 7: Topic and risk prevalence over time (2014-2025)
#    two stacked panels sharing an x-axis -> topic_risk_timeline.png
# ============================================================================

TIMELINE_TOPICS = ["coal_and_regions", "energy_prices", "energy_security", "nuclear"]
TOPIC_TITLES = {"coal_and_regions": "Coal & Regions", "energy_prices": "Energy Prices",
                 "energy_security": "Energy Security", "nuclear": "Nuclear"}
TOPIC_STYLES = {
    "coal_and_regions": dict(color="#333333", marker="o", linestyle="-"),
    "energy_prices": dict(color="#e08a1e", marker="s", linestyle="-"),
    "energy_security": dict(color="#3776ab", marker="^", linestyle="--"),
    "nuclear": dict(color="#b1003a", marker="D", linestyle=":"),
}
RISK_STYLES = {
    "environmental_risk": dict(color="#3fa34d", marker="o", linestyle="-"),
    "geopolitical_risk": dict(color="#3776ab", marker="^", linestyle="--"),
    "social_risk": dict(color="#e08a1e", marker="s", linestyle=":"),
}

df6_all = df_energy[df_energy["party"].isin(MAIN_PARTIES6)]
years_tl = sorted(df6_all[df6_all["year"] >= 2014]["year"].unique())
df_tl = df6_all[df6_all["year"] >= 2014]

fig7b, (ax_top, ax_bot) = plt.subplots(
    2, 1, figsize=(13, 10.5), facecolor="white", sharex=False
)

for ax in (ax_top, ax_bot):
    ax.set_facecolor("white")
    ax.grid(axis="y", color="#f0f0f0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

# Event markers: Crimea (2014), NS2 sanctions (2019), Ukraine war (2022),
# same neutral gray dashed-line style used in geo_gas_timeline.png.
timeline_events = [
    (2014, "Crimea\nannexation"),
    (2019, "NS2\nsanctions"),
    (2022, "Ukraine\nwar"),
]
for ax in (ax_top, ax_bot):
    for xv, _ in timeline_events:
        ax.axvline(xv, color="#555555", linestyle="--", linewidth=1.2, zorder=2)

for topic in TIMELINE_TOPICS:
    vals = [df_tl[df_tl["year"] == y]["topics"].apply(lambda x: topic in x).mean() * 100
            for y in years_tl]
    ax_top.plot(years_tl, vals, label=TOPIC_TITLES[topic], markersize=5,
                linewidth=1.6, **TOPIC_STYLES[topic])
ax_top.set_ylabel("% of energy speeches", fontsize=10)
ax_top.set_xticks(years_tl)
ax_top.set_xticklabels(years_tl, rotation=45, ha="right")
# Legend placed fully above the axes (not overlapping data or the top
# spine), with headroom reserved via subplots_adjust below.
ax_top.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=4,
              frameon=False, fontsize=9)

# Event labels sit just below the legend row on both panels, using a
# fixed axes-fraction y-position so they never collide with either the
# legend or a data line regardless of each panel's own y-range.
for xv, label in timeline_events:
    ax_top.text(xv + 0.1, 0.97, label, transform=ax_top.get_xaxis_transform(),
                fontsize=8, color="#555555", va="top", ha="left")

for risk in RISK_ORDER:
    vals = [df_tl[df_tl["year"] == y][risk].mean() * 100 for y in years_tl]
    ax_bot.plot(years_tl, vals, label=RISK_TITLES[risk], markersize=5,
                linewidth=1.6, **RISK_STYLES[risk])
ax_bot.set_ylabel("% of energy speeches", fontsize=10)
ax_bot.set_xlabel("Year", fontsize=10)
ax_bot.set_xticks(years_tl)
ax_bot.set_xticklabels(years_tl, rotation=45, ha="right")
ax_bot.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=3,
              frameon=False, fontsize=9)

for xv, label in timeline_events:
    ax_bot.text(xv + 0.1, 0.97, label, transform=ax_bot.get_xaxis_transform(),
                fontsize=8, color="#555555", va="top", ha="left")

plt.subplots_adjust(top=0.93, hspace=0.55)
plt.savefig(FIG_DIR / "topic_risk_timeline.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig7b)
print("Saved: topic_risk_timeline.png")

# ============================================================================
# CHART 8: Geopolitical vs social risk in natural gas speeches, by year
#    (paired bars) -> geo_vs_social_gas.png
# ============================================================================

df_gas_all = df_energy[
    (df_energy["party"].isin(MAIN_PARTIES4))
    & (df_energy["energy_sources"].apply(lambda x: "natural_gas" in x))
].copy()

years_gvs = sorted(df_gas_all["year"].unique())
geo_vals = [df_gas_all[df_gas_all["year"] == y]["geopolitical_risk"].mean() * 100
            for y in years_gvs]
soc_vals = [df_gas_all[df_gas_all["year"] == y]["social_risk"].mean() * 100
            for y in years_gvs]

fig8b, ax8 = plt.subplots(figsize=(14, 6), facecolor="white")
ax8.set_facecolor("white")

xg = np.arange(len(years_gvs))
w = 0.38
ax8.bar(xg - w / 2, geo_vals, width=w, color="#3776ab", label="Geopolitical risk")
ax8.bar(xg + w / 2, soc_vals, width=w, color="#e08a1e", hatch="//",
        edgecolor="white", label="Social risk")

event_years = {2014: "Crimea", 2019: "NS2 sanctions", 2022: "Ukraine war"}
for yr, label in event_years.items():
    if yr in years_gvs:
        xi = years_gvs.index(yr)
        ax8.axvline(xi, color="#555555", linestyle="--", linewidth=1.2, zorder=2)
        ax8.text(xi, ax8.get_ylim()[1] if ax8.get_ylim()[1] else 100,
                  label, fontsize=8, color="#555555", rotation=0, va="bottom", ha="center")

ax8.set_xticks(xg)
ax8.set_xticklabels(years_gvs, rotation=45, ha="right")
ax8.set_ylabel("% of natural gas speeches", fontsize=11)
ax8.grid(axis="y", color="#f0f0f0", linewidth=0.8, zorder=0)
ax8.set_axisbelow(True)
for spine in ["top", "right"]:
    ax8.spines[spine].set_visible(False)
ax8.set_ylim(0, 105)

ax8.legend(loc="upper left", ncol=2, frameon=False, fontsize=10)
plt.tight_layout()
plt.savefig(FIG_DIR / "geo_vs_social_gas.png", dpi=150,
            facecolor="white", bbox_inches="tight")
plt.close(fig8b)
print("Saved: geo_vs_social_gas.png")
