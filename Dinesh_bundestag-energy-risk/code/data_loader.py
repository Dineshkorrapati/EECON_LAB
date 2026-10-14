"""
Load and prepare the classifications for the descriptive analyses.

Shared by 07_descriptive_figures.py and 08_descriptive_tables.py, so that
all figures and tables are based on the same data.
"""

import json
from pathlib import Path
import pandas as pd

PARTY_CORRECTIONS = {
    "Sigmar Gabriel": "SPD", "Barbara Hendricks": "SPD", "Andrea Nahles": "SPD",
    "Heiko Maas": "SPD", "Manuela Schwesig": "SPD", "Iris Gleicke": "SPD",
    "Uwe Beckmeyer": "SPD", "Florian Pronold": "SPD", "Rita Schwarzelühr-Sutter": "SPD",
    "Olaf Scholz": "SPD", "Christine Lambrecht": "SPD", "Hubertus Heil": "SPD",
    "Franziska Giffey": "SPD", "Svenja Schulze": "SPD", "Brigitte Zypries": "SPD",
    "Kerstin Griese": "SPD", "Nancy Faeser": "SPD", "Karl Lauterbach": "SPD",
    "Klara Geywitz": "SPD", "Boris Pistorius": "SPD", "Wolfgang Schmidt": "SPD",
    "Sarah Ryglewski": "SPD", "Johann Saathoff": "SPD", "Niels Annen": "SPD",
    "Nils Schmid": "SPD", "Cansel Kiziltepe": "SPD", "Bärbel Kofler": "SPD",
    "Rita Hagl-Kehl": "SPD", "Carsten Schneider": "SPD", "Elisabeth Kaiser": "SPD",
    "Lars Klingbeil": "SPD", "Stefanie Hubig": "SPD", "Bärbel Bas": "SPD",
    "Reem Alabali": "SPD", "Verena Hubertz": "SPD", "Carsten Träger": "SPD",

    "Peter Altmaier": "CDU/CSU", "Gerd Müller": "CDU/CSU", "Oliver Wittke": "CDU/CSU",
    "Julia Klöckner": "CDU/CSU", "Enak Ferlemann": "CDU/CSU", "Angela Merkel": "CDU/CSU",
    "Wolfgang Schäuble": "CDU/CSU", "Johanna Wanka": "CDU/CSU", "Christian Schmidt": "CDU/CSU",
    "Alexander Dobrindt": "CDU/CSU", "Norbert Barthle": "CDU/CSU", "Christian Hirte": "CDU/CSU",
    "Thomas Rachel": "CDU/CSU", "Michael Meister": "CDU/CSU", "Ole Schröder": "CDU/CSU",
    "Günter Krings": "CDU/CSU", "Hans-Joachim Fuchtel": "CDU/CSU", "Maria Flachsbarth": "CDU/CSU",
    "Thomas Silberhorn": "CDU/CSU", "Horst Seehofer": "CDU/CSU", "Anja Karliczek": "CDU/CSU",
    "Jens Spahn": "CDU/CSU", "Andreas Scheuer": "CDU/CSU", "Elisabeth Winkelmeier-Becker": "CDU/CSU",
    "Thomas Bareiß": "CDU/CSU", "Marco Wanderwitz": "CDU/CSU", "Stephan Mayer": "CDU/CSU",
    "Helge Braun": "CDU/CSU", "Thomas Gebhart": "CDU/CSU", "Thomas Jarzombek": "CDU/CSU",
    "Annette Widmann-Mauz": "CDU/CSU", "Friedrich Merz": "CDU/CSU", "Dorothee Bär": "CDU/CSU",
    "Katherina Reiche": "CDU/CSU", "Nina Warken": "CDU/CSU", "Alois Rainer": "CDU/CSU",
    "Patrick Schnieder": "CDU/CSU", "Thorsten Frei": "CDU/CSU", "Johann Wadephul": "CDU/CSU",
    "Karin Prien": "CDU/CSU", "Steffen Bilger": "CDU/CSU", "Michael Kretschmer": "CDU/CSU",
    "Johann David": "CDU/CSU",

    "Robert Habeck": "Grüne", "Annalena Baerbock": "Grüne", "Cem Özdemir": "Grüne",
    "Lisa Paus": "Grüne", "Steffi Lemke": "Grüne", "Michael Kellner": "Grüne",
    "Franziska Brantner": "Grüne", "Oliver Krischer": "Grüne", "Christian Kühn": "Grüne",
    "Bettina Hoffmann": "Grüne", "Jan-Niclas Gesenhues": "Grüne", "Ophelia Nick": "Grüne",

    "Christian Lindner": "FDP", "Marco Buschmann": "FDP", "Volker Wissing": "FDP",
    "Bettina Stark-Watzinger": "FDP", "Katja Hessel": "FDP", "Florian Toncar": "FDP",
    "Benjamin Strasser": "FDP", "Jens Brandenburg": "FDP", "Michael Theurer": "FDP",
    "Oliver Luksic": "FDP",
}

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILES = [ROOT / "data" / "classified" / f"output_{p}.jsonl"
               for p in ["18th", "19th", "20th", "21st"]]

PERIODS4 = ["18th", "19th", "20th", "21st"]
# Party order follows the political spectrum, left to right, matching
# the convention already established in Table 6's footnote.
# Party order follows the actual Bundestag hemicycle seating (left to
# right), matching the official seat-distribution chart: Linke, SPD,
# Grüne, FDP, CDU/CSU, AfD. This reflects the December 2021 seating
# swap, after which CDU/CSU sits adjacent to AfD and FDP sits
# adjacent to Grüne.
MAIN_PARTIES6 = ["Linke", "SPD", "Grüne", "FDP", "CDU/CSU", "AfD"]
MAIN_PARTIES4 = ["Linke", "SPD", "Grüne", "CDU/CSU"]

TOPIC_LABELS = [
    "renewables_and_grid", "climate_policy", "nuclear",
    "coal_and_regions", "energy_prices", "energy_security",
]
RISK_LABELS = ["environmental_risk", "geopolitical_risk", "social_risk"]
SOURCE_LABELS = ["coal", "natural_gas", "nuclear", "wind"]

COLORS = {
    "CDU/CSU": "#000000", "SPD": "#E3000F", "Grüne": "#409A3C",
    "Linke": "#BE3075", "AfD": "#00A2DE", "FDP": "#FFED00",
}


def parse_year(datetime_str):
    """Extract the year from a German date string like
    'Montag, den 18. November 2013'."""
    s = datetime_str.replace("\xa0", " ")
    s = " ".join(s.split())
    part = s.split(", den ")[1]
    _, _, year_str = part.replace(".", "").split()
    return int(year_str)


def load_and_prepare_data(input_files=None):
    """Load all JSONL files, apply party corrections, parse years, and
    flag each of the three risk types as its own boolean column.
    Returns the FULL frame (df) and the energy-central subset
    (df_energy), both with corrected party and parsed year.
    """
    if input_files is None:
        input_files = INPUT_FILES

    records = []
    for f in input_files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    records.append(json.loads(line))
    df = pd.DataFrame(records)

    df["party"] = df.apply(
        lambda r: PARTY_CORRECTIONS.get(r["speaker"], r["party"]), axis=1
    )
    df["year"] = df["Datetime"].apply(parse_year)
    for risk in RISK_LABELS:
        df[risk] = df["risk_types"].apply(lambda x: risk in x)

    df_energy = df[df["is_energy"] == True].copy()
    return df, df_energy
