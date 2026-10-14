"""
Build the speech-level panel used in the regressions.

For each energy-central speech by one of the six main parties, the panel
contains the risk labels, the party's government or opposition status, and
the distance to the nearest federal election and major event.

Input:  data/speaker_roles/output_{period}_with_roles.xlsx
Output: data/regression/Logit_panel_dataset.xlsx
Run:    python code/06_build_regression_panel.py
"""

import ast
import numpy as np
import pandas as pd
from datetime import date
from openpyxl import load_workbook
from openpyxl.styles import Font
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "data" / "speaker_roles"
OUTPUT_FILE = ROOT / "data" / "regression" / "Logit_panel_dataset.xlsx"

INPUT_FILES = {
    "18th": ROLES / "output_18th_with_roles.xlsx",
    "19th": ROLES / "output_19th_with_roles.xlsx",
    "20th": ROLES / "output_20th_with_roles.xlsx",
    "21st": ROLES / "output_21st_with_roles.xlsx",
}
MAIN_PARTIES = ["CDU/CSU", "SPD", "Grüne", "Linke", "AfD", "FDP"]


# Loading files
frames = []
for period, path in INPUT_FILES.items():
    fdf = pd.read_excel(path)
    for col in ["topics", "risk_types", "energy_sources"]:
        fdf[col] = fdf[col].apply(ast.literal_eval)
    frames.append(fdf)
df = pd.concat(frames, ignore_index=True)
df = df[df["is_energy"].notna()].copy()
df["is_energy"] = df["is_energy"].astype(bool)
print(f"1. Loaded {len(df)} speeches total")

# Cleaning party labels
df["party"] = df["party"].replace({"Fraktionslos": "fraktionslos"})
df = df[~df["party"].isin(["SPDCDU/CSU", "SPDSPD"])]  # 2 corrupted rows
print("2. Cleaned party labels")

# Parsing German dates: "Montag, den 18. November 2013" -> date(2013,11,18)
GERMAN_MONTHS = {
    "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6,
    "Juli": 7, "August": 8, "September": 9, "Oktober": 10,
    "November": 11, "Dezember": 12,
}

def parse_german_date(s):
    s = s.replace("\xa0", " ")
    s = " ".join(s.split())
    part = s.split(", den ")[1]
    day_str, month_str, year_str = part.replace(".", "").split()
    return date(int(year_str), GERMAN_MONTHS[month_str], int(day_str))

df["speech_date"] = df["Datetime"].apply(parse_german_date)
print(f"3. Parsed dates, example: '{df['Datetime'].iloc[0]}' -> {df['speech_date'].iloc[0]}")

# Building binary risk columns from risk_types list
df["env_risk"] = df["risk_types"].apply(lambda x: int("environmental_risk" in x))
df["geo_risk"] = df["risk_types"].apply(lambda x: int("geopolitical_risk" in x))
df["social_risk"] = df["risk_types"].apply(lambda x: int("social_risk" in x))
print("4. Built env_risk / geo_risk / social_risk columns")

# Restricting to energy-central speeches, main parties only
df_reg = df[(df["is_energy"]) & (df["party"].isin(MAIN_PARTIES))].copy()
print(f"5. Regression sample: {len(df_reg)} speeches "
      f"(dropped {len(df) - len(df_reg)}: non-energy or non-main-party)")

# Government / opposition lookup, coded by exact day
gov_periods = [
    ("CDU/CSU", date(2013, 10, 22), date(2017, 10, 24), 1),
    ("SPD",     date(2013, 10, 22), date(2013, 12, 16), 0),
    ("SPD",     date(2013, 12, 17), date(2017, 10, 24), 1),
    ("Grüne",   date(2013, 10, 22), date(2017, 10, 24), 0),
    ("Linke",   date(2013, 10, 22), date(2017, 10, 24), 0),

    ("CDU/CSU", date(2017, 10, 24), date(2021, 10, 26), 1),
    ("SPD",     date(2017, 10, 24), date(2021, 10, 26), 1),
    ("Grüne",   date(2017, 10, 24), date(2021, 10, 26), 0),
    ("Linke",   date(2017, 10, 24), date(2021, 10, 26), 0),
    ("AfD",     date(2017, 10, 24), date(2021, 10, 26), 0),
    ("FDP",     date(2017, 10, 24), date(2021, 10, 26), 0),

    ("CDU/CSU", date(2021, 10, 26), date(2021, 12, 7),  1),  # caretaker
    ("CDU/CSU", date(2021, 12, 8), date(2025, 3, 25),   0),
    ("SPD",     date(2021, 10, 26), date(2025, 3, 25),  1),  # caretaker -> Ampel -> minority
    ("Grüne",   date(2021, 10, 26), date(2021, 12, 7),  0),
    ("Grüne",   date(2021, 12, 8), date(2025, 3, 25),   1),
    ("FDP",     date(2021, 10, 26), date(2021, 12, 7),  0),
    ("FDP",     date(2021, 12, 8), date(2024, 11, 5),   1),
    ("FDP",     date(2024, 11, 6), date(2025, 3, 25),   0),  # left the coalition
    ("Linke",   date(2021, 10, 26), date(2025, 3, 25),  0),
    ("AfD",     date(2021, 10, 26), date(2025, 3, 25),  0),

    ("SPD",     date(2025, 3, 25), date(2025, 5, 5),    1),  # caretaker minority
    ("SPD",     date(2025, 5, 6), date(2029, 12, 31),   1),
    ("Grüne",   date(2025, 3, 25), date(2029, 12, 31),  0),
    ("CDU/CSU", date(2025, 3, 25), date(2025, 5, 5),    0),
    ("CDU/CSU", date(2025, 5, 6), date(2029, 12, 31),   1),
    ("Linke",   date(2025, 3, 25), date(2029, 12, 31),  0),
    ("AfD",     date(2025, 3, 25), date(2029, 12, 31),  0),
]
gov_df = pd.DataFrame(gov_periods, columns=["party", "start", "end", "in_government"])

def lookup_government(party, speech_date):
    match = gov_df[(gov_df["party"] == party) &
                    (gov_df["start"] <= speech_date) &
                    (gov_df["end"] >= speech_date)]
    return match["in_government"].iloc[0] if len(match) else np.nan

df_reg["opposition"] = 1 - df_reg.apply(
    lambda r: lookup_government(r["party"], r["speech_date"]), axis=1)
print(f"6. Built opposition column ({df_reg['opposition'].isna().sum()} missing)")

# Building days_before_after_election
ELECTIONS = [date(2013, 9, 22), date(2017, 9, 24), date(2021, 9, 26), date(2025, 2, 23)]

def signed_days_to_nearest_election(d):
    distances = [(d - e).days for e in ELECTIONS]
    return min(distances, key=abs)

df_reg["days_before_after_election"] = df_reg["speech_date"].apply(signed_days_to_nearest_election)
print(f"7. Built days_before_after_election column (0 blank -- signed, negative = before nearest election)")

# Building days_before_after_major_event: signed relative time to nearest shock
# Event dates verified: Crimea (27 Feb 2014), Nord Stream 2 (20 Dec 2019), Ukraine (24 Feb 2022)
EVENTS = [date(2014, 2, 27), date(2019, 12, 20), date(2022, 2, 24)]

def signed_days_to_nearest_event(d):
    distances = [(d - e).days for e in EVENTS]
    return min(distances, key=abs)

df_reg["days_before_after_major_event"] = df_reg["speech_date"].apply(signed_days_to_nearest_event)
print(f"8. Built days_before_after_major_event column (0 blank -- signed, negative = before nearest event)")

# Saving as Excel
out_cols = ["period", "speech_date", "speaker", "party", "speaker_role",
            "env_risk", "geo_risk", "social_risk", "opposition",
            "days_before_after_election", "days_before_after_major_event"]
final = df_reg[out_cols].sort_values(["period", "speech_date"]).reset_index(drop=True)

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    final.to_excel(writer, sheet_name="panel_data", index=False)

# Applying Arial font and formatting throughout worksheet
wb = load_workbook(OUTPUT_FILE)
ws = wb["panel_data"]
for row in ws.iter_rows():
    for cell in row:
        cell.font = Font(name="Arial", bold=(cell.row == 1))
for col_cells in ws.columns:
    width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells) + 2
    ws.column_dimensions[col_cells[0].column_letter].width = min(width, 30)
ws.freeze_panes = "A2"
wb.save(OUTPUT_FILE)

print(f"\nSaved {OUTPUT_FILE} with {len(final)} rows, {len(out_cols)} columns")
