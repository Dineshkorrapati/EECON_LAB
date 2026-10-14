"""
Classify each validation speech five times at temperature 0.5 and compute
the self-consistency of the labels.

Input:  validation/self_consistency_input.xlsx
Output: validation/self_consistency_output.xlsx
Run:    python code/validation/02_self_consistency.py

Requires a running Ollama server with the model (ollama pull qwen2.5:32b).
"""

import json
from pathlib import Path
import re
import requests
import pandas as pd
from collections import Counter


# =============================================================================
# CONFIGURATION
# =============================================================================

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "validation" / "self_consistency_input.xlsx"
SHEET = "Sheet1"

OUTPUT = ROOT / "validation" / "self_consistency_output.xlsx"

LLM_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:32b"

# Number of independent classifications per speech
RUNS_PER_SPEECH = 5

# Must be > 0 to obtain variation between runs
TEMP = 0.5

MAX_CHARS = 3500
TIMEOUT = 180


# =============================================================================
# VALID LABELS
# =============================================================================

VALID_TOPICS = [
    "nuclear",
    "energy_prices",
    "energy_security",
    "climate_policy",
    "renewables_and_grid",
    "coal_and_regions",
    "non_energy",
]

VALID_RISKS = [
    "environmental_risk",
    "geopolitical_risk",
    "social_risk",
]

VALID_SOURCES = [
    "wind",
    "natural_gas",
    "nuclear",
    "solar",
    "renewables_general",
    "coal",
]


# =============================================================================
# CHUNKING
# =============================================================================

def chunk_text(text, max_chars=MAX_CHARS):
    """
    Split long speeches into chunks.

    Paragraph boundaries are preferred so that chunks remain semantically
    meaningful.
    """

    text = str(text)

    chunks = []
    current = []
    current_length = 0

    paragraphs = re.split(r"\n{2,}", text)

    for para in paragraphs:

        # If a single paragraph itself is longer than max_chars,
        # split that paragraph directly.
        if len(para) > max_chars:

            if current:
                chunks.append("\n".join(current))
                current = []
                current_length = 0

            for start in range(0, len(para), max_chars):
                chunks.append(
                    para[start:start + max_chars]
                )

            continue

        if current_length + len(para) > max_chars:

            if current:
                chunks.append("\n".join(current))

            current = [para]
            current_length = len(para)

        else:

            current.append(para)
            current_length += len(para)

    if current:
        chunks.append("\n".join(current))

    if not chunks:
        chunks = [text[:max_chars]]

    return chunks


# =============================================================================
# PROMPT
# =============================================================================

def build_prompt(chunk):

    return f"""
You are classifying German Bundestag speeches about energy policy.

Follow the classification rules carefully.

STEP 1 — IS THIS SPEECH ABOUT ENERGY?

If energy is NOT the main subject, return:

{{"is_energy": false, "topics": ["non_energy"], "risk_types": [], "energy_sources": []}}


STEP 2 — TOPICS

This is a multi-label classification.

Assign ALL topics that clearly apply.

Available labels:

- nuclear
  AKW, Atomausstieg, Kernkraft, Endlager

- energy_prices
  Strompreis, EEG-Umlage, Energiekosten, Industriestrompreis

- energy_security
  Versorgungssicherheit, Gasabhängigkeit, Nord Stream,
  Russland-Gas

- climate_policy
  CO2-Ziele, Paris, COP, Klimaschutzgesetz, Emissionshandel

- renewables_and_grid
  EEG, Windausbau, Solarausbau, Netzausbau, Netzentgelte

- coal_and_regions
  Braunkohle, Steinkohle, Kohleausstieg, Lausitz,
  Strukturwandel

- non_energy
  Energy is not a main subject


STEP 3 — RISK TYPES

This is also multi-label.

Assign a risk type ONLY if the risk is explicitly argued in the speech.

Available labels:

- environmental_risk
  Climate damage, CO2, species loss, ecological harm

- geopolitical_risk
  Russia dependency, OPEC, supply disruption,
  dependence on foreign actors

- social_risk
  Energy poverty, household costs,
  worker/regional impact, fairness


STEP 4 — ENERGY SOURCES

Assign an energy source ONLY when the corresponding German term
appears in the speech text.

Available labels:

- wind
  Wind, Windkraft, Windrad, Windpark, Windenergie

- natural_gas
  Erdgas, Gas, Gasleitung, LNG, Nord Stream

- nuclear
  Atom, Kernkraft, AKW, Kernkraftwerk

- solar
  Solar, Photovoltaik, Solaranlage, PV

- renewables_general
  Erneuerbar, EEG, Ökostrom, Wasserstoff,
  Wärmepumpe, Elektroauto

- coal
  Braunkohle, Steinkohle, Kohlekraftwerk, Kohle


IMPORTANT:

Return ONLY valid JSON.

Do not provide explanations.
Do not use Markdown.
Do not add text before or after the JSON.

Required JSON format:

{{"is_energy": true, "topics": [...], "risk_types": [...], "energy_sources": [...]}}


Speech text:

\"\"\"{chunk}\"\"\"
"""


# =============================================================================
# CALL OLLAMA / QWEN
# =============================================================================

def call_llm(chunk):

    payload = {
        "model": MODEL_NAME,
        "prompt": build_prompt(chunk),
        "stream": False,
        "options": {
            "temperature": TEMP
        },
    }

    try:

        response = requests.post(
            LLM_URL,
            json=payload,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        raw = data.get("response", "").strip()

        # Extract JSON object even if the model accidentally adds text
        start = raw.index("{")
        end = raw.rindex("}") + 1

        parsed = json.loads(
            raw[start:end]
        )

        return parsed

    except Exception as e:

        print(
            f"        LLM ERROR: {e}"
        )

        return None


# =============================================================================
# FILTER LABELS
# =============================================================================

def filter_labels(labels, valid_labels):

    if not isinstance(labels, list):
        return []

    return sorted(
        set(
            label
            for label in labels
            if label in valid_labels
        )
    )


# =============================================================================
# AGGREGATE CHUNKS WITHIN ONE RUN
# =============================================================================

def aggregate_chunks(outputs):

    valid_outputs = [
        output
        for output in outputs
        if output is not None
    ]

    if not valid_outputs:
        return None

    # If every chunk says non-energy
    if all(
        not output.get("is_energy", False)
        for output in valid_outputs
    ):

        return {
            "is_energy": False,
            "topics": ["non_energy"],
            "risk_types": [],
            "energy_sources": [],
        }

    # Keep chunks classified as energy
    energy_outputs = [
        output
        for output in valid_outputs
        if output.get("is_energy", False)
    ]

    topics = []
    risks = []
    sources = []

    for output in energy_outputs:

        topics.extend(
            output.get("topics", [])
        )

        risks.extend(
            output.get("risk_types", [])
        )

        sources.extend(
            output.get("energy_sources", [])
        )

    topics = filter_labels(
        topics,
        VALID_TOPICS,
    )

    # If the speech has been classified as energy,
    # non_energy should not coexist with energy topics.
    topics = [
        topic
        for topic in topics
        if topic != "non_energy"
    ]

    risks = filter_labels(
        risks,
        VALID_RISKS,
    )

    sources = filter_labels(
        sources,
        VALID_SOURCES,
    )

    return {
        "is_energy": True,
        "topics": topics,
        "risk_types": risks,
        "energy_sources": sources,
    }


# =============================================================================
# MAJORITY VOTE / TUPLE CONSISTENCY
# =============================================================================

def majority_and_score(list_of_lists):
    """
    Finds the most frequently occurring complete label set.

    Example:

    Run 1 = ["wind", "solar"]
    Run 2 = ["wind", "solar"]
    Run 3 = ["wind"]
    Run 4 = ["wind", "solar"]
    Run 5 = ["wind"]

    Majority = ["wind", "solar"]
    Tuple consistency = 3/5 = 0.60

    Empty [] is a valid classification.

    Therefore, if all five runs return [],
    consistency = 1.0.
    """

    tuples = [
        tuple(sorted(labels))
        for labels in list_of_lists
    ]

    counts = Counter(tuples)

    majority_tuple, majority_count = (
        counts.most_common(1)[0]
    )

    consistency_score = (
        majority_count / len(tuples)
    )

    return (
        list(majority_tuple),
        consistency_score,
    )


# =============================================================================
# PER-LABEL CONSISTENCY
# =============================================================================

def per_label_consistency(
    list_of_lists,
    all_labels
):
    """
    Calculates agreement separately for each possible label.

    This is useful for multi-label classification because two runs may
    disagree on only one label while agreeing on all others.
    """

    if not all_labels:
        return 1.0

    scores = []

    for label in all_labels:

        presence = [
            1 if label in labels else 0
            for labels in list_of_lists
        ]

        number_present = sum(presence)

        number_absent = (
            len(presence) - number_present
        )

        majority_count = max(
            number_present,
            number_absent,
        )

        agreement = (
            majority_count / len(presence)
        )

        scores.append(agreement)

    return (
        sum(scores) / len(scores)
    )


# =============================================================================
# MAIN PROGRAM
# =============================================================================

def main():

    print()
    print("=" * 70)
    print("QWEN SELF-CONSISTENCY VALIDATION")
    print("=" * 70)

    print(f"Model            : {MODEL_NAME}")
    print(f"Runs per speech  : {RUNS_PER_SPEECH}")
    print(f"Temperature      : {TEMP}")
    print(f"Input            : {INPUT}")
    print(f"Output           : {OUTPUT}")

    print()
    print("Loading Excel file...")


    # =========================================================================
    # LOAD DATA
    # =========================================================================

    try:

        df = pd.read_excel(
            INPUT,
            sheet_name=SHEET,
        )

    except Exception as e:

        print()
        print("ERROR: Could not load Excel file.")
        print(e)

        return


    df = df.copy().reset_index(drop=True)


    print("Excel loaded successfully.")
    print(f"Number of rows: {len(df)}")
    print(
        f"Columns: {df.columns.tolist()}"
    )


    # =========================================================================
    # CHECK REQUIRED COLUMNS
    # =========================================================================

    required_columns = [
        "code",
        "period",
        "party",
        "speech_id",
        "speech_text",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        print()
        print(
            "ERROR: Required columns are missing:"
        )

        print(missing_columns)

        print()
        print(
            "Available columns:"
        )

        print(df.columns.tolist())

        return


    # =========================================================================
    # REMOVE EMPTY SPEECHES
    # =========================================================================

    empty_speeches = (
        df["speech_text"]
        .isna()
        .sum()
    )

    if empty_speeches > 0:

        print()
        print(
            f"WARNING: {empty_speeches} rows have empty speech_text."
        )

        print(
            "Those rows will be removed."
        )

        df = (
            df[
                df["speech_text"].notna()
            ]
            .copy()
            .reset_index(drop=True)
        )


    total_speeches = len(df)


    if total_speeches == 0:

        print(
            "ERROR: No speeches available."
        )

        return


    print()
    print(
        f"Beginning classification of "
        f"{total_speeches} speeches..."
    )

    print()


    # =========================================================================
    # OUTPUT CONTAINERS
    # =========================================================================

    majority_topics = []
    majority_risks = []
    majority_sources = []

    topic_tuple_consistency = []
    risk_tuple_consistency = []
    source_tuple_consistency = []

    topic_label_consistency = []
    risk_label_consistency = []
    source_label_consistency = []

    all_runs_topics = []
    all_runs_risks = []
    all_runs_sources = []


    # =========================================================================
    # PROCESS SPEECHES
    # =========================================================================

    for i, row in df.iterrows():

        speech_text = str(
            row["speech_text"]
        )

        chunks = chunk_text(
            speech_text
        )

        print("-" * 70)

        print(
            f"[{i + 1}/{total_speeches}] "
            f"code={row['code']} | "
            f"period={row['period']} | "
            f"party={row['party']} | "
            f"speech_id={row['speech_id']}"
        )

        print(
            f"    Speech length: "
            f"{len(speech_text):,} characters"
        )

        print(
            f"    Chunks: {len(chunks)}"
        )


        run_topics = []
        run_risks = []
        run_sources = []


        # =====================================================================
        # FIVE SELF-CONSISTENCY RUNS
        # =====================================================================

        for run_number in range(
            RUNS_PER_SPEECH
        ):

            print(
                f"    Run "
                f"{run_number + 1}/{RUNS_PER_SPEECH}...",
                end=" ",
                flush=True,
            )


            chunk_outputs = []

            for chunk_number, chunk in enumerate(
                chunks,
                start=1,
            ):

                result = call_llm(
                    chunk
                )

                chunk_outputs.append(
                    result
                )


            run_result = aggregate_chunks(
                chunk_outputs
            )


            if run_result is None:

                run_topics.append([])
                run_risks.append([])
                run_sources.append([])

                print("FAILED")

            else:

                run_topics.append(
                    run_result["topics"]
                )

                run_risks.append(
                    run_result["risk_types"]
                )

                run_sources.append(
                    run_result["energy_sources"]
                )

                print(
                    f"topics="
                    f"{run_result['topics']} | "
                    f"risks="
                    f"{run_result['risk_types']} | "
                    f"sources="
                    f"{run_result['energy_sources']}"
                )


        # =====================================================================
        # MAJORITY VOTE
        # =====================================================================

        maj_topics, tc_topics = (
            majority_and_score(
                run_topics
            )
        )

        maj_risks, tc_risks = (
            majority_and_score(
                run_risks
            )
        )

        maj_sources, tc_sources = (
            majority_and_score(
                run_sources
            )
        )


        # =====================================================================
        # PER-LABEL CONSISTENCY
        # =====================================================================

        lc_topics = (
            per_label_consistency(
                run_topics,
                VALID_TOPICS,
            )
        )

        lc_risks = (
            per_label_consistency(
                run_risks,
                VALID_RISKS,
            )
        )

        lc_sources = (
            per_label_consistency(
                run_sources,
                VALID_SOURCES,
            )
        )


        # =====================================================================
        # STORE RESULTS
        # =====================================================================

        majority_topics.append(
            json.dumps(
                maj_topics,
                ensure_ascii=False,
            )
        )

        majority_risks.append(
            json.dumps(
                maj_risks,
                ensure_ascii=False,
            )
        )

        majority_sources.append(
            json.dumps(
                maj_sources,
                ensure_ascii=False,
            )
        )


        topic_tuple_consistency.append(
            tc_topics
        )

        risk_tuple_consistency.append(
            tc_risks
        )

        source_tuple_consistency.append(
            tc_sources
        )


        topic_label_consistency.append(
            lc_topics
        )

        risk_label_consistency.append(
            lc_risks
        )

        source_label_consistency.append(
            lc_sources
        )


        all_runs_topics.append(
            json.dumps(
                run_topics,
                ensure_ascii=False,
            )
        )

        all_runs_risks.append(
            json.dumps(
                run_risks,
                ensure_ascii=False,
            )
        )

        all_runs_sources.append(
            json.dumps(
                run_sources,
                ensure_ascii=False,
            )
        )


        # =====================================================================
        # PRINT SPEECH RESULT
        # =====================================================================

        print()
        print(
            f"    MAJORITY TOPICS  : {maj_topics}"
        )

        print(
            f"    MAJORITY RISKS   : {maj_risks}"
        )

        print(
            f"    MAJORITY SOURCES : {maj_sources}"
        )

        print(
            f"    Tuple consistency: "
            f"topics={tc_topics:.2f} | "
            f"risks={tc_risks:.2f} | "
            f"sources={tc_sources:.2f}"
        )

        print(
            f"    Label consistency: "
            f"topics={lc_topics:.2f} | "
            f"risks={lc_risks:.2f} | "
            f"sources={lc_sources:.2f}"
        )


    # =========================================================================
    # ADD RESULTS TO DATAFRAME
    # =========================================================================

    df["LLM_topics_majority"] = (
        majority_topics
    )

    df["LLM_risks_majority"] = (
        majority_risks
    )

    df["LLM_sources_majority"] = (
        majority_sources
    )


    df["topic_tuple_consistency"] = (
        topic_tuple_consistency
    )

    df["risk_tuple_consistency"] = (
        risk_tuple_consistency
    )

    df["source_tuple_consistency"] = (
        source_tuple_consistency
    )


    df["topic_label_consistency"] = (
        topic_label_consistency
    )

    df["risk_label_consistency"] = (
        risk_label_consistency
    )

    df["source_label_consistency"] = (
        source_label_consistency
    )


    df["LLM_topics_all_runs"] = (
        all_runs_topics
    )

    df["LLM_risks_all_runs"] = (
        all_runs_risks
    )

    df["LLM_sources_all_runs"] = (
        all_runs_sources
    )


    # =========================================================================
    # SAVE EXCEL
    # =========================================================================

    print()
    print("=" * 70)
    print("Saving results...")
    print("=" * 70)


    try:

        df.to_excel(
            OUTPUT,
            index=False,
        )

    except PermissionError:

        print()
        print(
            "ERROR: Cannot save the output Excel file."
        )

        print(
            "The output file may currently be open in Excel."
        )

        print(
            "Close the Excel file and run the script again."
        )

        return

    except Exception as e:

        print()
        print(
            "ERROR while saving:"
        )

        print(e)

        return


    # =========================================================================
    # SUMMARY
    # =========================================================================

    avg_topic_tuple = (
        sum(topic_tuple_consistency)
        / len(topic_tuple_consistency)
    )

    avg_risk_tuple = (
        sum(risk_tuple_consistency)
        / len(risk_tuple_consistency)
    )

    avg_source_tuple = (
        sum(source_tuple_consistency)
        / len(source_tuple_consistency)
    )


    avg_topic_label = (
        sum(topic_label_consistency)
        / len(topic_label_consistency)
    )

    avg_risk_label = (
        sum(risk_label_consistency)
        / len(risk_label_consistency)
    )

    avg_source_label = (
        sum(source_label_consistency)
        / len(source_label_consistency)
    )


    print()
    print("=" * 70)
    print("SELF-CONSISTENCY RESULTS")
    print("=" * 70)

    print(
        f"Speeches : {total_speeches}"
    )

    print(
        f"Runs     : {RUNS_PER_SPEECH} per speech"
    )

    print(
        f"Model    : {MODEL_NAME}"
    )

    print(
        f"Temp     : {TEMP}"
    )


    print()
    print(
        "AVERAGE TUPLE CONSISTENCY"
    )

    print(
        f"Topics  : {avg_topic_tuple:.3f}"
    )

    print(
        f"Risks   : {avg_risk_tuple:.3f}"
    )

    print(
        f"Sources : {avg_source_tuple:.3f}"
    )


    print()
    print(
        "AVERAGE PER-LABEL CONSISTENCY"
    )

    print(
        f"Topics  : {avg_topic_label:.3f}"
    )

    print(
        f"Risks   : {avg_risk_label:.3f}"
    )

    print(
        f"Sources : {avg_source_label:.3f}"
    )


    print()
    print("=" * 70)

    print(
        f"RESULTS SAVED TO:\n{OUTPUT}"
    )

    print("=" * 70)
    print()


# =============================================================================
# RUN PROGRAM
# =============================================================================

if __name__ == "__main__":
    main()