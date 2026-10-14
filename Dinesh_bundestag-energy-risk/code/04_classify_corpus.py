"""
Classify each speech by energy policy topic, risk type and energy source.

The speeches are classified with Qwen2.5-32B, run locally through Ollama at
temperature 0 with a fixed seed. The prompt first checks whether energy is
the main subject of a speech and then assigns the labels. Results are saved
after every speech, so an interrupted run resumes where it stopped.

Input:  data/energy_filtered/{period}_bundestag_energy_speeches.xlsx
Output: data/classified/output_{period}.jsonl
Run:    python code/04_classify_corpus.py [--period 18th|19th|20th|21st]

Requires a running Ollama server with the model (ollama pull qwen2.5:32b).
"""

import argparse
import json
import os
import re
import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
PERIODS = ["18th", "19th", "20th", "21st"]
CORPUS_FILES = {p: ROOT / "data" / "energy_filtered" / f"{p}_bundestag_energy_speeches.xlsx" for p in PERIODS}
OUTPUT_FILES = {p: ROOT / "data" / "classified" / f"output_{p}.jsonl" for p in PERIODS}

LLM_URL    = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:32b"
SEED       = 42      # Fixed seed → identical results every run
TEMP       = 0       # Zero temperature → deterministic
MAX_CHARS  = 3500    # Max chars per chunk
TIMEOUT    = 180     # Seconds per LLM call

# ── Final validated taxonomy ───────────────────────────────────────────────────
VALID_TOPICS  = ["nuclear", "energy_prices", "energy_security",
                 "climate_policy", "renewables_and_grid", "coal_and_regions",
                 "non_energy"]
VALID_RISKS   = ["environmental_risk", "geopolitical_risk", "social_risk"]
VALID_SOURCES = ["wind", "natural_gas", "nuclear", "solar",
                 "renewables_general", "coal"]

# Party name normalisation
PARTY_MAP = {
    "BÜNDNIS 90/DIE GRÜNEN": "Grüne",
    "BÜNDNIS 90/DIE GR\u00dcNEN": "Grüne",
    "DIE LINKE": "Linke",
    "Die Linke": "Linke",
    "SPD": "SPD",
    "CDU/CSU": "CDU/CSU",
    "AfD": "AfD",
    "FDP": "FDP",
    "BSW": "BSW",
}

def norm_party(raw):
    if not isinstance(raw, str):
        return "unknown"
    raw = re.sub(r'\s+', ' ', raw).strip()
    return PARTY_MAP.get(raw, raw)

# ── Chunking ───────────────────────────────────────────────────────────────────
def chunk_text(text, max_chars=MAX_CHARS):
    chunks, current, length = [], [], 0
    for para in re.split(r"\n{2,}", str(text)):
        if length + len(para) > max_chars:
            if current:
                chunks.append("\n".join(current))
            current, length = [para], len(para)
        else:
            current.append(para)
            length += len(para)
    if current:
        chunks.append("\n".join(current))
    return chunks or [str(text)[:max_chars]]

# ── Prompt ─────────────────────────────────────────────────────────────────────
def build_prompt(chunk):
    return f"""You are classifying German Bundestag speeches about energy policy.

STEP 1 — IS THIS SPEECH ABOUT ENERGY?
If energy is NOT the main subject, return:
{{"is_energy": false, "topics": ["non_energy"], "risk_types": [], "energy_sources": []}}

STEP 2 — TOPICS (multi-label, assign ALL that clearly apply):
- nuclear            (AKW, Atomausstieg, Kernkraft, Endlager, Urananlage)
- energy_prices      (Strompreis, EEG-Umlage, Energiekosten, Industriestrompreis)
- energy_security    (Versorgungssicherheit, Gasabhängigkeit, Nord Stream, Russland-Gas)
- climate_policy     (CO2-Ziele, Paris, COP, Klimaschutzgesetz, Emissionshandel)
- renewables_and_grid(EEG, Windausbau, Solarausbau, Netzausbau, Netzentgelte)
- coal_and_regions   (Braunkohle, Steinkohle, Kohleausstieg, Lausitz, Strukturwandel)
- non_energy         (energy is not a main subject)

STEP 3 — RISK TYPES (multi-label, assign ALL that are EXPLICITLY ARGUED):
- environmental_risk (climate damage, CO2, species loss, ecological harm)
- geopolitical_risk  (Russia dependency, OPEC, supply disruption, foreign actors)
- social_risk        (energy poverty, household costs, worker/regional impact, fairness)
Only include a risk if the speaker actually argues it, not just implies it.

STEP 4 — ENERGY SOURCES (multi-label, ONLY if German word appears in the text):
- wind               (Wind, Windkraft, Windrad, Windpark, Windenergie)
- natural_gas        (Erdgas, Gas, Gasleitung, LNG, Nord Stream)
- nuclear            (Atom, Kernkraft, AKW, Kernkraftwerk)
- solar              (Solar, Photovoltaik, Solaranlage, PV)
- renewables_general (Erneuerbar, EEG, Ökostrom, Wasserstoff, Wärmepumpe, Elektroauto)
- coal               (Braunkohle, Steinkohle, Kohlekraftwerk, Kohle)

Return ONLY valid JSON, no explanation:
{{"is_energy": true, "topics": [...], "risk_types": [...], "energy_sources": [...]}}

Speech text:
\"\"\"{chunk}\"\"\"
"""

# ── LLM call ───────────────────────────────────────────────────────────────────
def call_llm(chunk):
    payload = {
        "model": MODEL_NAME,
        "prompt": build_prompt(chunk),
        "stream": False,
        "options": {"temperature": TEMP, "seed": SEED},
    }
    try:
        resp = requests.post(LLM_URL, json=payload, timeout=TIMEOUT)
        raw = resp.json().get("response", "")
        start = raw.index("{")
        end   = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception as e:
        return None  # will be marked as error

# ── Filter to valid taxonomy labels ───────────────────────────────────────────
def filter_labels(lst, valid):
    if not isinstance(lst, list):
        return []
    return sorted(set(x for x in lst if x in valid))

# ── Aggregate multi-chunk results ─────────────────────────────────────────────
def aggregate_chunks(outputs):
    valid_outputs = [o for o in outputs if o is not None]
    if not valid_outputs:
        return None  # all chunks errored

    # If all say non-energy → non-energy
    if all(not o.get("is_energy", False) for o in valid_outputs):
        return {
            "is_energy":     False,
            "topics":        ["non_energy"],
            "risk_types":    [],
            "energy_sources":[],
        }

    # Aggregate energy outputs
    topics, risks, sources = [], [], []
    for o in valid_outputs:
        if o.get("is_energy", False):
            topics.extend(o.get("topics", []))
            risks.extend(o.get("risk_types", []))
            sources.extend(o.get("energy_sources", []))

    return {
        "is_energy":      True,
        "topics":         filter_labels(topics,  VALID_TOPICS),
        "risk_types":     filter_labels(risks,   VALID_RISKS),
        "energy_sources": filter_labels(sources, VALID_SOURCES),
    }

# ── Load already-done speech IDs (for resume) ─────────────────────────────────
def load_done_ids(output_path):
    done = set()
    if not os.path.exists(output_path):
        return done
    with open(output_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    done.add(rec["speech_id"])
                except:
                    pass
    return done

# ── Classify one Bundestag period ──────────────────────────────────────────────
def classify_period(period):
    corpus_path = CORPUS_FILES[period]
    output_path = OUTPUT_FILES[period]

    if not os.path.exists(corpus_path):
        print(f"  ERROR: {corpus_path} not found — skipping {period}")
        return

    print(f"\n{'='*60}")
    print(f"Period: {period}  |  {corpus_path}")
    print(f"Output: {output_path}")

    df = pd.read_excel(corpus_path)
    total = len(df)

    done_ids = load_done_ids(output_path)
    remaining = df[~df["speech_id"].isin(done_ids)]
    print(f"Total: {total}  |  Already done: {len(done_ids)}  |  Remaining: {len(remaining)}")

    if len(remaining) == 0:
        print("  All speeches already classified.")
        return

    t0 = time.time()
    errors = 0

    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, (_, row) in enumerate(remaining.iterrows(), 1):
            sid    = int(row["speech_id"])
            text   = str(row["Sentence"])
            party  = norm_party(row.get("party", ""))
            date   = str(row.get("Datetime", ""))
            speaker= str(row.get("speaker", ""))
            kw     = str(row.get("matched_keywords", ""))

            # Classify
            chunks  = chunk_text(text)
            outputs = [call_llm(c) for c in chunks]
            result  = aggregate_chunks(outputs)

            # Build record
            if result is None:
                record = {
                    "speech_id":      sid,
                    "period":         period,
                    "Datetime":       date,
                    "speaker":        speaker,
                    "party":          party,
                    "matched_keywords": kw,
                    "error":          "all_chunks_failed",
                    "is_energy":      None,
                    "topics":         [],
                    "risk_types":     [],
                    "energy_sources": [],
                }
                errors += 1
            else:
                record = {
                    "speech_id":      sid,
                    "period":         period,
                    "Datetime":       date,
                    "speaker":        speaker,
                    "party":          party,
                    "matched_keywords": kw,
                    "is_energy":      result["is_energy"],
                    "topics":         result["topics"],
                    "risk_types":     result["risk_types"],
                    "energy_sources": result["energy_sources"],
                }

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            # Progress
            done_total = len(done_ids) + i
            pct = 100 * done_total / total
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 1
            eta_s = (len(remaining) - i) / rate
            eta_m = eta_s / 60

            status = "energy" if (result and result.get("is_energy")) else "filtered"
            topics_str = ",".join(record["topics"][:2]) if record["topics"] else "—"
            print(f"  [{done_total:>5}/{total}] {pct:5.1f}%  sid={sid:<6}  "
                  f"{party:<8}  {status:<8}  topics={topics_str:<25}  "
                  f"ETA={eta_m:.0f}m")

    elapsed_total = (time.time() - t0) / 60
    print(f"\n  Done. {len(remaining)} speeches in {elapsed_total:.1f} min  |  Errors: {errors}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Classify Bundestag energy speeches")
    parser.add_argument("--period", choices=["18th","19th","20th","21st"],
                        help="Classify only one period (default: all)")
    args = parser.parse_args()

    # Check Ollama is reachable
    try:
        requests.get("http://localhost:11434", timeout=5)
    except Exception:
        print("ERROR: Ollama not running. Start it with: ollama serve")
        return

    print(f"Model:  {MODEL_NAME}")
    print(f"Seed:   {SEED}  (results are identical on every run)")
    print(f"Temp:   {TEMP}")
    print(f"Taxonomy: {len(VALID_TOPICS)-1} topics | {len(VALID_RISKS)} risks | {len(VALID_SOURCES)} sources")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    periods = [args.period] if args.period else ["18th","19th","20th","21st"]

    for period in periods:
        classify_period(period)

    print(f"\nAll done. Output files:")
    for period in periods:
        path = OUTPUT_FILES[period]
        if os.path.exists(path):
            with open(path) as f:
                n = sum(1 for line in f if line.strip())
            print(f"  {path}  ({n} records)")

if __name__ == "__main__":
    main()
