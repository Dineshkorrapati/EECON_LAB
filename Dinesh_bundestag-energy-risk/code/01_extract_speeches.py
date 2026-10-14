"""
Download all plenary speeches of the German Bundestag from 22 October 2013
to 31 December 2025, using the DIP API and the XML plenary protocols.

Input:  DIP API (https://search.dip.bundestag.de/api/v1)
Output: data/raw/bundestag_plenary_speeches_2013_2025.xlsx
Run:    python code/01_extract_speeches.py

Uses the public DIP API key by default. To use your own key, set the
environment variable DIP_API_KEY.
"""

import os
import time
import re
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# =========================
# CONFIG
# =========================
# Standard public key directly from DIP documentation:
PUBLIC_KEY = "R2BZaee.DjdCyihKZMf8AOjtScubP2EVydegzjmBIQ"

# Fallback to the public key if DIP_API_KEY environment variable is missing
RAW_KEY = os.environ.get("DIP_API_KEY", PUBLIC_KEY)
API_KEY = RAW_KEY.strip().strip("'").strip('"')

BASE_URL = "https://search.dip.bundestag.de/api/v1"

START_DATE = "2013-10-22"
END_DATE = "2025-12-31"

OUTPUT_FILE = ROOT / "data" / "raw" / "bundestag_plenary_speeches_2013_2025.xlsx"

SLEEP_SECONDS = 0.2
MIN_SPEECH_LEN = 200

# Regex fallback for legacy plain text entries
SPEAKER_LINE = re.compile(
    r"^(?P<title>Präsident(?:in)?|Vizepräsident(?:in)?|Alterspräsident(?:in)?|Bundesminister(?:in)?|Staatssekretär(?:in)?)?\s*"
    r"(?P<speaker>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß .\-]+)"
    r"(?:\s+\((?P<party>[^)]+)\))?:\s*$",
    re.MULTILINE
)

# =========================
# XML UTIL
# =========================
def safe_parse_xml(content: bytes):
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        return None

def find_first_text_by_localname(root: ET.Element, localname: str) -> str:
    for el in root.iter():
        if el.tag.endswith(localname) and el.text:
            return el.text.strip()
    return ""

def parse_real_btp_xml(xml_bytes: bytes, fallback_date: str = ""):
    rows = []
    root = safe_parse_xml(xml_bytes)
    if root is None:
        return rows

    date = find_first_text_by_localname(root, "datum") or fallback_date
    rede_elements = [el for el in root.iter() if el.tag.endswith("rede")]

    if rede_elements:
        for rede in rede_elements:
            speaker = ""
            party = ""
            role_lang = ""
            role_kurz = ""

            for el in rede.iter():
                tag = el.tag.lower()
                
                if tag.endswith("vorname") and el.text and not speaker:
                    speaker = el.text.strip()
                elif tag.endswith("nachname") and el.text:
                    speaker = f"{speaker} {el.text.strip()}".strip()
                elif tag.endswith("name") and el.text and not speaker:
                    speaker = el.text.strip()

                if tag.endswith("fraktion") and el.text and not party:
                    party = el.text.strip()

                if tag.endswith("rolle_lang") and el.text:
                    role_lang = el.text.strip()
                elif tag.endswith("rolle_kurz") and el.text:
                    role_kurz = el.text.strip()
                elif tag.endswith("rolle") and el.text and not role_lang:
                    role_lang = el.text.strip()

            parts = []
            for el in rede.iter():
                if el.tag.endswith("p") and el.text:
                    t = el.text.strip()
                    if t:
                        parts.append(t)

            speech = " ".join(parts).strip()
            if not speaker or len(speech) < MIN_SPEECH_LEN:
                continue

            final_role = role_lang if role_lang else (role_kurz if role_kurz else "MdB")

            rows.append({
                "datetime": date,
                "speaker": speaker,
                "party": party,
                "speaker_role": final_role,
                "content_german": speech
            })

        if rows:
            return rows

    lines = [t.strip() for t in root.itertext() if t and t.strip()]
    text = "\n".join(lines)

    matches = list(SPEAKER_LINE.finditer(text))
    if not matches:
        return rows

    for i, m in enumerate(matches):
        speaker = m.group("speaker").strip()
        party = (m.group("party") or "").strip()
        title = (m.group("title") or "").strip()
        
        final_role = title if title else "MdB"

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        speech = text[start:end].strip()

        if len(speech) < MIN_SPEECH_LEN:
            continue

        rows.append({
            "datetime": date,
            "speaker": speaker,
            "party": party,
            "speaker_role": final_role,
            "content_german": speech
        })

    return rows

# =========================
# MAIN
# =========================
def main():
    session = requests.Session()
    
    # Authenticate via Header and Query Parameter for maximum API compatibility
    session.headers.update({"Authorization": f"ApiKey {API_KEY}"})

    all_rows = []
    cursor = None

    processed = 0
    meta_fail = 0
    missing_xml_url = 0
    btp_fail = 0
    no_speeches = 0

    total = None

    print(f"Starting extraction using DIP API key: {API_KEY[:6]}...")

    while True:
        params = {
            "f.datum.start": START_DATE,
            "f.datum.end": END_DATE,
            "f.zuordnung": "BT",
            "apikey": API_KEY
        }
        if cursor:
            params["cursor"] = cursor

        r = session.get(f"{BASE_URL}/plenarprotokoll-text", params=params, timeout=60)

        if r.status_code != 200:
            print("Listing failed:", r.status_code, r.text[:300])
            break

        data = r.json()
        docs = data.get("documents", [])
        cursor_new = data.get("cursor")

        if total is None:
            total = data.get("numFound", 0)
            print("Total protocols:", total)

        print(f"Fetched {len(docs)} protocol IDs")

        if not docs:
            break

        for doc in docs:
            pid = doc.get("id")
            if not pid:
                continue

            processed += 1

            r_meta = session.get(
                f"{BASE_URL}/plenarprotokoll-text/{pid}",
                params={"apikey": API_KEY, "format": "xml"},
                timeout=60
            )
            time.sleep(SLEEP_SECONDS)

            meta_root = safe_parse_xml(r_meta.content)
            if meta_root is None:
                meta_fail += 1
                continue

            xml_url = find_first_text_by_localname(meta_root, "xml_url")
            fallback_date = find_first_text_by_localname(meta_root, "datum")

            if not xml_url:
                missing_xml_url += 1
                continue

            r_btp = requests.get(xml_url, timeout=60)
            time.sleep(SLEEP_SECONDS)

            rows = parse_real_btp_xml(r_btp.content, fallback_date=fallback_date)

            if not rows:
                if r_btp.status_code != 200:
                    btp_fail += 1
                else:
                    no_speeches += 1
                continue

            all_rows.extend(rows)

            if processed % 25 == 0 and total:
                print(f"   → processed {processed}/{total} protocols | speeches so far: {len(all_rows)}")

        if cursor_new == cursor:
            break
        cursor = cursor_new

    df = pd.DataFrame(all_rows, columns=["datetime", "speaker", "party", "speaker_role", "content_german"])
    df.to_excel(OUTPUT_FILE, index=False)

    print("\nExtraction complete.")
    print("Total speeches extracted:", len(df))
    print("Saved file:", OUTPUT_FILE)

if __name__ == "__main__":
    main()