#!/usr/bin/env python3
"""
generate_csv_lookup.py
======================
Generates the CSV_LOOKUP JavaScript object embedded in brugada-checker.html.

Input files (BCFI/FAMHP Belgian medication database, root of repository):
  - Stof.csv   : substance names (StofCV → NBase Dutch base name)
  - Sam.csv    : substance-per-package links (mppcv → Stofcv, mpcv_)
  - MPP.csv    : medication package products (mppcv → mppnm commercial name)
  - MP.csv     : medication products (MPcv → MPnm product name)

Output:
  Prints the CSV_LOOKUP JS object to stdout so you can paste it into
  brugada-checker.html. Run from the repository root:

      python3 scripts/generate_csv_lookup.py

How the mapping works:
  1. Stof.csv  → find StofCV codes for Brugada-risk substances by matching NBase.
  2. Sam.csv   → find all (mppcv, mpcv) pairs that contain those StofCV codes.
  3. MPP.csv   → get commercial name (mppnm) for each mppcv.
  4. MP.csv    → get product name (MPnm) for each MPcv.
  5. Extract brand name (text before dose/form info) and normalise to lowercase.
  6. Map normalised brand name → canonical Brugada generic name.

Entries already covered by the handmatig ALIASES table in brugada-checker.html
are included anyway (duplicates are harmless).
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Mapping: lowercase NBase (partial) → canonical generic name used in DB
BRUGADA_MAP: dict[str, str] = {
    # AVOID
    "ajmaline":        "Ajmaline",
    "bupivacaïne":     "Bupivacaïne",
    "bupivacaine":     "Bupivacaïne",
    "chlorpromazine":  "Chlorpromazine",
    "cibenzoline":     "Cibenzoline",
    "cocaine":         "Cocaine",
    "cocaïne":         "Cocaine",
    "desipramine":     "Desipramine",
    "flecaïnide":      "Flecaïnide",
    "flecainide":      "Flecaïnide",
    "imipramine":      "Imipramine",
    "isoprenaline":    "Isoprenaline",
    "isoproterenol":   "Isoprenaline",
    "ketamine":        "Ketamine",
    "esketamine":      "Ketamine",
    "lacosamide":      "Lacosamide",
    "levobupivacaïne": "Levobupivacaïne",
    "levobupivacaine": "Levobupivacaïne",
    "lidocaïne":       "Lidocaïne",
    "lidocaine":       "Lidocaïne",
    "oxcarbazepine":   "Oxcarbazepine",
    "pilsicainide":    "Pilsicainide",
    "procainamide":    "Procainamide",
    "propafenon":      "Propafenon",
    "propafenone":     "Propafenon",
    "quinidine":       "Quinidine",
    "tedisamil":       "Tedisamil",
    "vernakalant":     "Vernakalant",
    # PREF_AVOID
    "amitriptyline":   "Amitriptyline",
    "bupropion":       "Bupropion",
    "carbamazepine":   "Carbamazepine",
    "clomipramine":    "Clomipramine",
    "clozapine":       "Clozapine",
    "cyamemazine":     "Cyamemazine",
    "doxepine":        "Doxepine",
    "doxepin":         "Doxepine",
    "fluoxetine":      "Fluoxetine",
    "fluvoxamine":     "Fluvoxamine",
    "haloperidol":     "Haloperidol",
    "itraconazol":     "Itraconazol",
    "itraconazole":    "Itraconazol",
    "lithium":         "Lithium",
    "maprotiline":     "Maprotiline",
    "metoclopramide":  "Metoclopramide",
    "mexiletin":       "Mexiletine",
    "mexiletine":      "Mexiletine",
    "nortriptyline":   "Nortriptyline",
    "promethazine":    "Promethazine",
    "propranolol":     "Propranolol",
    "terfenadine":     "Terfenadine",
    "thioridazine":    "Thioridazine",
    # NO_CLEAR
    "brompheniramine": "Brompheniramine",
    "dasatinib":       "Dasatinib",
    "diltiazem":       "Diltiazem",
    "nicorandil":      "Nicorandil",
    "nifedipine":      "Nifedipine",
    "nitroglycerine":  "Nitroglycerine",
    "isosorbide":      "Sorbidnitrate",
}

FORM_KEYWORDS = re.compile(
    r"\s+\d|\s+\(|\s+filmomh|\s+tabl|\s+caps|\s+inj|\s+inf|\s+oploss"
    r"|\s+susp|\s+druppels|\s+transd|\s+rect|\s+or\.|\s+spuit|,",
    re.IGNORECASE,
)


def parse_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f, delimiter=";", quotechar='"'))


def extract_brand(name: str) -> str:
    """Extract the brand/product name before dosage/form information."""
    m = FORM_KEYWORDS.search(name)
    if m:
        return name[: m.start()].strip()
    return name.split()[0] if name else ""


def main() -> None:
    stof_rows = parse_csv(ROOT / "Stof.csv")
    sam_rows  = parse_csv(ROOT / "Sam.csv")
    mpp_rows  = parse_csv(ROOT / "MPP.csv")
    mp_rows   = parse_csv(ROOT / "MP.csv")

    # Step 1: StofCV → canonical generic
    stof_cv_to_generic: dict[str, str] = {}
    for row in stof_rows:
        nbase = row.get("NBase", "").lower().strip()
        stof_cv = row.get("StofCV", "").strip()
        if not stof_cv:
            continue
        for key, generic in BRUGADA_MAP.items():
            if nbase == key or nbase.startswith(key + " "):
                stof_cv_to_generic[stof_cv] = generic
                break

    # Step 2: mppcv + mpcv → generic via Sam.csv
    mppcv_to_generic: dict[str, str] = {}
    mpcv_to_generic:  dict[str, str] = {}
    for row in sam_rows:
        stof_cv = row.get("Stofcv", "").strip()
        if stof_cv not in stof_cv_to_generic:
            continue
        generic = stof_cv_to_generic[stof_cv]
        mppcv = row.get("mppcv", "").strip()
        mpcv  = row.get("mpcv_", "").strip()
        if mppcv:
            mppcv_to_generic[mppcv] = generic
        if mpcv:
            mpcv_to_generic[mpcv] = generic

    # Step 3: MPP.csv → brand names
    lookup: dict[str, str] = {}
    for row in mpp_rows:
        mppcv = row.get("mppcv", "").strip()
        mppnm = row.get("mppnm", "").strip()
        if mppcv in mppcv_to_generic and mppnm:
            brand = extract_brand(mppnm)
            if brand and len(brand) > 2:
                lookup[brand.lower()] = mppcv_to_generic[mppcv]

    # Step 4: MP.csv → brand names
    for row in mp_rows:
        mpcv = row.get("MPcv", "").strip()
        mpnm = row.get("MPnm", "").strip()
        if mpcv in mpcv_to_generic and mpnm:
            brand = extract_brand(mpnm)
            if brand and len(brand) > 2:
                lookup[brand.lower()] = mpcv_to_generic[mpcv]

    # Print as JS object
    lines = [f'  {json.dumps(k, ensure_ascii=False)}:{json.dumps(v, ensure_ascii=False)},' for k, v in sorted(lookup.items())]
    print("const CSV_LOOKUP = {")
    print("\n".join(lines))
    print("};")
    print(f"\n// Total entries: {len(lookup)}", file=sys.stderr)


if __name__ == "__main__":
    main()
