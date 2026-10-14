"""
Clean the downloaded speeches and split them by Bundestag period.

Cleaning removes duplicate speeches, normalises whitespace in all text
columns, and corrects speaker names affected by known scraping errors.

Input:  data/raw/bundestag_plenary_speeches_2013_2025.xlsx
Output: data/interim/, one file per Bundestag period (18th to 21st)
Run:    python code/02_clean_and_split_periods.py
"""

import pandas as pd
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# =========================
# CONFIG
# =========================
INPUT_FILE = ROOT / "data" / "raw" / "bundestag_plenary_speeches_2013_2025.xlsx"

INTERIM = ROOT / "data" / "interim"
INTERIM.mkdir(parents=True, exist_ok=True)
OUTPUT_FILES = {
    "18": INTERIM / "18th_Bundestag_bundestag_plenary_speeches_2013_2017.xlsx",
    "19": INTERIM / "19th_Bundestag_bundestag_plenary_speeches_2017_2021.xlsx",
    "20": INTERIM / "20th_Bundestag_bundestag_plenary_speeches_2021_2025.xlsx",
    "21": INTERIM / "21st_Bundestag_bundestag_plenary_speeches_2025_Dec_2025.xlsx",
}

DATE_COL = "datetime"

# columns that hold free text and should get whitespace-normalized;
# only the ones actually present in the input are touched
TEXT_COLS = ["datetime", "speaker", "party", "speaker_role", "content_german"]

# =========================
# GERMAN MONTH MAP
# =========================
MONTHS = {
    "januar": "01", "februar": "02", "märz": "03", "maerz": "03",
    "april": "04", "mai": "05", "juni": "06", "juli": "07",
    "august": "08", "september": "09", "oktober": "10",
    "november": "11", "dezember": "12",
}


# =========================
# CLEANING HELPERS
# =========================
def norm_ws(s):
    """Collapse all whitespace/newlines to single spaces, drop soft
    hyphens, strip leading/trailing space."""
    if not isinstance(s, str):
        return s
    s = s.replace("\xad", "")          # invisible soft hyphen
    s = re.sub(r"\s+", " ", s)         # also folds \xa0, \u202f, \u2005, tabs, newlines
    return s.strip()


DUP_TOKEN_RE = re.compile(r"^(.{2,}?)\1+$")   # e.g. "SvenjaSvenja" -> "Svenja"
MERGE_ARTIFACT_RE = re.compile(r"[a-zäöüß][A-ZÄÖÜ]")  # e.g. "...UlrichAlexander..."

# words/abbreviations that legitimately appear as the middle token(s) of
# a real German name, e.g. "Hans-Georg von der Marwitz", "Philipp Graf
# Lerchenfeld", "Charles M. Huber" - anything else in that position is
# treated as a scraper artifact (another speaker's surname leaking in)
NAME_PARTICLES = {"von", "der", "van", "de", "zu", "graf", "freiherr",
                   "prinz", "vom", "du", "le", "la"}
INITIAL_RE = re.compile(r"^[A-ZÄÖÜ]\.$")


def dedupe_intratoken(tok):
    m = DUP_TOKEN_RE.match(tok)
    return m.group(1) if m else tok


def is_legit_multiword_name(tokens):
    """True if every token between the first (given name) and last
    (surname) is a recognised particle or a single-letter initial."""
    if len(tokens) <= 2:
        return True
    return all(t.lower() in NAME_PARTICLES or INITIAL_RE.match(t) for t in tokens[1:-1])


def clean_speaker(raw):
    if not isinstance(raw, str) or raw == "":
        return raw
    s = raw

    # keep only the part before ':' (drops leaked next-speaker fragments
    # glued onto a presiding officer's name)
    if ":" in s:
        s = s.split(":", 1)[0].strip()

    # drop parenthetical asides, e.g. "Christian Kühn ( Tübingen) (...)"
    s = re.sub(r"\([^)]*\)", "", s).strip()
    s = re.sub(r"\s+", " ", s)

    tokens = [dedupe_intratoken(t) for t in s.split(" ")]

    # collapse repeated trailing tokens, e.g.
    # "Kay Gottschalk Gottschalk Gottschalk" -> "Kay Gottschalk"
    seen, out = set(), []
    for t in tokens:
        if t in seen:
            break
        seen.add(t)
        out.append(t)

    # truncate trailing tokens that are OTHER real speakers' surnames
    # glued on by the scraper, e.g.
    # "Peter Beyer Haßelmann Korte Oppermann" -> "Peter Beyer"
    # while leaving genuine multi-word names (particles/initials) intact
    if len(out) >= 3 and not is_legit_multiword_name(out):
        out = out[:2]

    return " ".join(out).strip()


def canon_party(raw):
    if not isinstance(raw, str) or raw == "":
        return raw
    s = raw.strip()

    # leaked interjection text after a colon, e.g. "CDU/CSU: Ich glaube..."
    if ":" in s:
        s = s.split(":", 1)[0].strip()

    # exact doubled string, e.g. "SPDSPD" -> "SPD"
    if len(s) % 2 == 0 and s[: len(s) // 2] == s[len(s) // 2 :]:
        s = s[: len(s) // 2]

    key = re.sub(r"\s+", "", s).upper()

    mapping = {
        "CDU/CSU": "CDU/CSU",
        "SPD": "SPD",
        "AFD": "AfD",
        "FDP": "FDP",
        "BSW": "BSW",
        "DIELINKE": "DIE LINKE",
        "FRAKTIONSLOS": "fraktionslos",
        "BÜNDNIS90/DIEGRÜNEN": "BÜNDNIS 90/DIE GRÜNEN",
    }
    if key in mapping:
        return mapping[key]

    # unresolvable / not a real party (e.g. two parties merged, or a
    # Land name leaked into the field) -> treat as missing
    if key in ("SPDCDU/CSU", "BREMEN"):
        return pd.NA

    return s


def extract_german_date(text):
    if not isinstance(text, str):
        return None
    m = re.search(r"(\d{1,2})\.\s*([a-zäöü]+)\s*(\d{4})", text.lower())
    if not m:
        return None
    day, month_name, year = m.groups()
    month = MONTHS.get(month_name)
    if not month:
        return None
    return f"{year}-{month}-{int(day):02d}"


def assign_bundestag(date):
    if date <= pd.Timestamp("2017-10-23"):
        return "18"
    elif date <= pd.Timestamp("2021-10-25"):
        return "19"
    elif date <= pd.Timestamp("2025-03-25"):
        return "20"
    else:
        return "21"


# =========================
# LOAD DATA
# =========================
df = pd.read_excel(INPUT_FILE)
orig_rows = len(df)
print("Columns:", list(df.columns))
print("Total rows (raw):", orig_rows)

present_text_cols = [c for c in TEXT_COLS if c in df.columns]

# =========================
# 1. DROP EXACT DUPLICATE ROWS
# =========================
n_dupes = df.duplicated().sum()
df = df.drop_duplicates().reset_index(drop=True)
print(f"Dropped {n_dupes} exact duplicate rows ({orig_rows} -> {len(df)})")

# =========================
# 2. WHITESPACE NORMALIZATION
# =========================
for col in present_text_cols:
    df[col] = df[col].apply(norm_ws)

# =========================
# 3. CLEAN SPEAKER COLUMN
# =========================
speaker_before = df["speaker"].copy()
df["speaker"] = df["speaker"].apply(clean_speaker)
n_speaker_changed = (df["speaker"] != speaker_before).sum()
print(f"Cleaned {n_speaker_changed} speaker values (repeated-token / stray-fragment / "
      f"other-real-speaker-glued-on bug)")

# drop rows whose speaker still shows an irrecoverable two-name merge
merge_mask = df["speaker"].astype(str).str.contains(MERGE_ARTIFACT_RE, regex=True, na=False)
print(f"Dropping {merge_mask.sum()} rows with an unresolvable merged speaker name "
      f"(two different speakers' names/parties glued together by a scraper bug)")
df = df[~merge_mask].reset_index(drop=True)

# =========================
# 4. CLEAN PARTY COLUMN
# =========================
if "party" in df.columns:
    party_before = df["party"].copy()
    df["party"] = df["party"].apply(canon_party)
    n_party_changed = ((df["party"] != party_before) & ~(df["party"].isna() & party_before.isna())).sum()
    print(f"Normalized {n_party_changed} party values (whitespace/casing/line-break/duplication fixes)")

# =========================
# 5. PARSE DATE / ASSIGN BUNDESTAG
# =========================
df["__parsed_date"] = df[DATE_COL].astype(str).apply(extract_german_date)
missing = df["__parsed_date"].isna().sum()
print("Unparsed dates:", missing)
if missing > 0:
    print("Warning: sample unparsed values:")
    print(df.loc[df["__parsed_date"].isna(), DATE_COL].head(5))

df["__parsed_date"] = pd.to_datetime(df["__parsed_date"], errors="raise")
df["Bundestag"] = df["__parsed_date"].apply(assign_bundestag)

print("\nBundestag counts:")
print(df["Bundestag"].value_counts())

# =========================
# 6. EXPORT FILES
# =========================
for bt, out_file in OUTPUT_FILES.items():
    subset = (
        df[df["Bundestag"] == bt]
        .sort_values("__parsed_date", ascending=True)
        .drop(columns=["Bundestag", "__parsed_date"])
    )
    subset.to_excel(out_file, index=False)
    print(f"Saved {bt}th Bundestag: {len(subset)} rows")

print("\nCleaning + Bundestag-wise split completed successfully")