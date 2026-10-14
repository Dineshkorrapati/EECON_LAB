"""
Draw the stratified random validation sample of 100 speeches.

Input:  data/classified/, data/energy_filtered/
Output: validation/validation_sample_100.xlsx
Run:    python code/validation/01_draw_validation_sample.py
"""

import json
import re

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON_DIR = ROOT / "data" / "classified"
CORPUS_DIR = ROOT / "data" / "energy_filtered"
OUTPUT_FILE = ROOT / "validation" / "validation_sample_100.xlsx"

CLASSIFICATION_FILES = {"18th": JSON_DIR / "output_18th.jsonl",
                        "19th": JSON_DIR / "output_19th.jsonl",
                        "20th": JSON_DIR / "output_20th.jsonl",
                        "21st": JSON_DIR / "output_21st.jsonl"}
CORPUS_FILES = {"18th": CORPUS_DIR / "18th_bundestag_energy_speeches.xlsx",
                "19th": CORPUS_DIR / "19th_bundestag_energy_speeches.xlsx",
                "20th": CORPUS_DIR / "20th_bundestag_energy_speeches.xlsx",
                "21st": CORPUS_DIR / "21st_bundestag_energy_speeches.xlsx"}

SEED = 2026
PARTIES = ["Linke", "SPD", "Grüne", "FDP", "CDU/CSU", "AfD"]
MIN_WORDS, MAX_WORDS = 300, 1300
GAS_PATTERN = r"\b(?:erdgas|gas|lng|flüssiggas|nord ?stream|gasversorgung|gaspreis\w*|gasspeicher\w*)\b"

PILOT_CODING = {
    ("18th", 1965), ("18th", 2613), ("18th", 5035), ("18th", 6035), ("18th", 7984), ("18th", 10429),
    ("18th", 12342), ("19th", 2622), ("19th", 3735), ("19th", 3957), ("19th", 4045), ("19th", 12590),
    ("19th", 14352), ("19th", 18672), ("19th", 19623), ("19th", 19965), ("19th", 20516), ("19th", 25132),
    ("19th", 25294), ("20th", 3331), ("20th", 3554), ("20th", 3901), ("20th", 4498), ("20th", 7183),
    ("20th", 7305), ("20th", 8386), ("20th", 9568), ("20th", 10675), ("20th", 15267), ("20th", 15280),
    ("20th", 19211), ("20th", 23194), ("21st", 1053), ("21st", 1560), ("21st", 2124), ("21st", 2219),
    ("21st", 2379), ("21st", 3081), ("21st", 4280), ("21st", 4318), ("21st", 4790), ("21st", 4833),
    ("21st", 4926), ("21st", 5352)}


def load_corpus():
    rows = []
    for period, path in CLASSIFICATION_FILES.items():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    record["period"] = period
                    rows.append(record)
    llm = pd.DataFrame(rows)

    corpus = []
    for period, path in CORPUS_FILES.items():
        c = pd.read_excel(path, usecols=["speech_id", "Sentence"])
        c["period"] = period
        corpus.append(c)

    df = llm.merge(pd.concat(corpus), on=["period", "speech_id"], how="left")
    df["is_energy"] = df["is_energy"].fillna(False).astype(bool)
    df["text"] = df["Sentence"].astype(str).map(lambda s: re.sub(r"\s+", " ", s.replace("\u00ad", "")).strip())
    df["words"] = df["text"].str.split().str.len()
    df["year"] = df["Datetime"].astype(str).str.extract(r"(\d{4})", expand=False).astype(float)
    df["gas_keyword"] = df["text"].str.contains(GAS_PATTERN, case=False, regex=True)
    df["pilot"] = [(p, int(s)) in PILOT_CODING for p, s in zip(df["period"], df["speech_id"])]
    return df[df["party"].isin(PARTIES)].copy()


def main():
    df = load_corpus()
    pool = df[~df["pilot"] & df["words"].between(MIN_WORDS, MAX_WORDS)]

    rng = np.random.default_rng(SEED)
    draw = lambda frame, n: frame.sample(n=n, random_state=int(rng.integers(1e9)))

    stratum_a = pd.concat([draw(pool[pool["is_energy"] & (pool["period"] == p)], 20)
                           for p in ["18th", "19th", "20th", "21st"]])
    stratum_a["stratum"] = "A_random_energy"

    gas_pool = pool[pool["is_energy"] & (pool["period"] == "20th") & pool["year"].between(2022, 2024)
                    & pool["gas_keyword"] & ~pool.index.isin(stratum_a.index)]
    stratum_b = draw(gas_pool, 10)
    stratum_b["stratum"] = "B_gas_2022_2024"

    stratum_c = draw(pool[~pool["is_energy"]], 10)
    stratum_c["stratum"] = "C_relevance_check"

    sample = pd.concat([stratum_a, stratum_b, stratum_c]).sample(frac=1, random_state=SEED).reset_index(drop=True)
    sample["code"] = [f"S{i + 1:03d}" for i in range(len(sample))]

    out = sample[["code", "stratum", "period", "party", "speaker", "Datetime", "speech_id", "words", "text"]]
    out.sort_values("code").to_excel(OUTPUT_FILE, index=False)
    print(out.groupby(["stratum", "period"]).size().unstack(fill_value=0))
    print(f"\nSaved {len(out)} speeches to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
