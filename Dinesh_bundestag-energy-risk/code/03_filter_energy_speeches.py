"""
Keep the speeches that match the energy keyword dictionary.

Each retained speech receives a speech ID and a list of the keywords that
matched it.

Input:  data/interim/, data/energy_filtered/keyword_list.xlsx
Output: data/energy_filtered/{period}_bundestag_energy_speeches.xlsx
Run:    python code/03_filter_energy_speeches.py
"""

import re
import pandas as pd
from pathlib import Path


# ── CONFIG ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
FILTERED = ROOT / "data" / "energy_filtered"
KEYWORDS_PATH = FILTERED / "keyword_list.xlsx"

PERIODS = {
    "18th": INTERIM / "18th_Bundestag_bundestag_plenary_speeches_2013_2017.xlsx",
    "19th": INTERIM / "19th_Bundestag_bundestag_plenary_speeches_2017_2021.xlsx",
    "20th": INTERIM / "20th_Bundestag_bundestag_plenary_speeches_2021_2025.xlsx",
    "21st": INTERIM / "21st_Bundestag_bundestag_plenary_speeches_2025_Dec_2025.xlsx",
}

# Column names in the speeches file
TEXT_COL      = "content_german"   # column containing speech text
DATE_COL      = "datetime"         # column containing date


# ── KEYWORD LOADER ────────────────────────────────────────────────
def load_keywords(keywords_path: str) -> list[str]:
    """
    Load keywords from an Excel file.
    Handles any layout:
      - Single column, no header
      - Multi-column (keywords spread across columns)
      - Multi-sheet (reads all sheets)
    Returns a sorted, deduplicated list of lowercased keyword strings.
    Skips blank cells, URLs, and single-character strings.
    """
    xl = pd.ExcelFile(keywords_path)
    all_values = []

    for sheet in xl.sheet_names:
        df = xl.parse(sheet, header=None)
        # Flatten all cells across all rows and columns
        all_values.extend(df.values.ravel().tolist())

    keywords = []
    for val in all_values:
        if not isinstance(val, str):
            continue
        val = val.strip()
        if not val:
            continue
        if val.startswith("http"):      # skip URLs
            continue
        if len(val) <= 1:               # skip single chars
            continue
        keywords.append(val.lower())

    # Deduplicate preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    print(f"Keywords loaded: {len(unique)} unique terms from '{keywords_path}'")
    return unique


# ── SPEECH MATCHER ────────────────────────────────────────────────
def find_matching_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return all keywords found in the text (lowercased match)."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]


def filter_speeches(
    speeches_path: str,
    keywords_path: str,
    output_path: str,
    text_col: str = "content_german",
    date_col: str = "datetime",
) -> pd.DataFrame:
    """
    Load speeches, filter by keyword match, write to Excel.

    Returns the matched DataFrame.
    """
    # ── 1. Load speeches ──
    speeches_df = pd.read_excel(speeches_path)
    print(f"\nSource file   : {speeches_path}")
    print(f"Total speeches: {len(speeches_df)}")
    print(f"Columns       : {speeches_df.columns.tolist()}")

    # ── 2. Validate required column ──
    if text_col not in speeches_df.columns:
        raise ValueError(
            f"Column '{text_col}' not found in {speeches_path}. "
            f"Available columns: {speeches_df.columns.tolist()}"
        )

    # ── 3. Add 1-based speech_id before any filtering ──
    #    This is the key fix — unambiguous ID for downstream joining
    speeches_df = speeches_df.reset_index(drop=True)
    speeches_df.insert(0, "speech_id", speeches_df.index + 1)

    # ── 4. Standardise column names for output ──
    rename_map = {}
    if date_col in speeches_df.columns and date_col != "Datetime":
        rename_map[date_col] = "Datetime"
    if text_col in speeches_df.columns and text_col != "Sentence":
        rename_map[text_col] = "Sentence"
    if rename_map:
        speeches_df = speeches_df.rename(columns=rename_map)

    # ── 5. Load keywords ──
    keywords = load_keywords(keywords_path)
    if not keywords:
        raise ValueError(f"No keywords found in {keywords_path}")

    # ── 6. Match speeches ──
    print("\nMatching speeches against keywords...")

    # Work on a copy to avoid SettingWithCopyWarning
    text_lower = speeches_df["Sentence"].astype(str).str.lower()

    # Boolean mask: True if any keyword found in speech text
    mask = text_lower.apply(lambda s: any(kw in s for kw in keywords))

    matched_df = speeches_df[mask].copy()

    # ── 7. Add matched_keywords column (audit trail) ──
    matched_df["matched_keywords"] = matched_df["Sentence"].apply(
        lambda s: " | ".join(find_matching_keywords(str(s), keywords))
    )

    # ── 8. Drop duplicates on speech_id (safety net) ──
    before = len(matched_df)
    matched_df = matched_df.drop_duplicates(subset=["speech_id"])
    if len(matched_df) < before:
        print(f"  Dropped {before - len(matched_df)} duplicate speech_id rows")

    # ── 9. Summary ──
    print(f"\nResults")
    print(f"  Matched   : {len(matched_df)} / {len(speeches_df)} speeches")
    print(f"  Excluded  : {len(speeches_df) - len(matched_df)} speeches")

    if not matched_df.empty:
        print(f"\n  Party breakdown:")
        party_col = next(
            (c for c in matched_df.columns if c.lower() == "party"), None
        )
        if party_col:
            for party, count in matched_df[party_col].value_counts().items():
                pct = 100 * count / len(matched_df)
                print(f"    {party:30s}: {count:3d}  ({pct:.1f}%)")

        print(f"\n  Date breakdown:")
        date_col_out = "Datetime" if "Datetime" in matched_df.columns else date_col
        if date_col_out in matched_df.columns:
            years = matched_df[date_col_out].astype(str).str.extract(r"(\d{4})")[0]
            for yr, cnt in years.value_counts().sort_index().items():
                print(f"    {yr}: {cnt} speeches")

    # ── 10. Save ──
    matched_df.to_excel(output_path, index=False)
    print(f"\n  Saved to  : {output_path}")

    return matched_df


# ── MAIN ─────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("Bundestag Energy Speech Keyword Filter")
    print("=" * 55)

    for term, speeches_path in PERIODS.items():
        output_path = FILTERED / f"{term}_bundestag_energy_speeches.xlsx"
        print(f"\n--- {term} Bundestag ---")
        filter_speeches(
            speeches_path = speeches_path,
            keywords_path = KEYWORDS_PATH,
            output_path   = output_path,
            text_col      = TEXT_COL,
            date_col      = DATE_COL,
        )
        print(f"Saved {output_path}")


if __name__ == "__main__":
    main()