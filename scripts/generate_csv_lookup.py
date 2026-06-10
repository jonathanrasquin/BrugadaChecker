#!/usr/bin/env python3
"""
Genereer de CSV_LOOKUP tabel voor de Brugada-checker.

Dit script leest de BCFI/FAMHP CSV-bestanden uit de root van de repository
en genereert een JavaScript-object dat Belgische productnamen koppelt aan
de generieke stofnamen in de Brugada-checker.

Gebruik:
    python3 scripts/generate_csv_lookup.py > /tmp/csv_lookup_snippet.js

Plak daarna de inhoud van /tmp/csv_lookup_snippet.js in brugada-checker.html
ter vervanging van het bestaande CSV_LOOKUP-blok (gemarkeerd met
/* BEGIN CSV_LOOKUP */ en /* END CSV_LOOKUP */).

Vereiste CSV-bestanden (in de root van de repository):
  - Stof.csv  : stofcodes → generieke stofnaam (Nederlands)
  - Sam.csv   : verpakkingscode (mppcv) → stofcode + productcode (mpcv_)
  - MP.csv    : productcode (MPcv) → productnaam (MPnm)

De CSV-bestanden zijn afkomstig van het Belgisch Centrum voor Farmacotherapeutische
Informatie (BCFI) / Federaal Agentschap voor Geneesmiddelen en Gezondheidsproducten
(FAMHP) – zie https://www.bcfi.be/.
"""

import csv
import sys
import os
from collections import defaultdict

# Pad naar de CSV-bestanden (één niveau boven dit script)
ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_stof(path):
    """Laad Stof.csv: stofcode → Nederlandse basisnaam."""
    result = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            code = row["StofCV"].strip('"')
            nbase = row["NBase"].strip('"').strip()
            result[code] = nbase
    return result


def load_sam(path):
    """Laad Sam.csv: stofcode → set van productcodes (mpcv_)."""
    result = defaultdict(set)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            stofcv = row["Stofcv"].strip('"')
            mpcv = row["mpcv_"].strip('"')
            if mpcv:
                result[stofcv].add(mpcv)
    return result


def load_mp(path):
    """Laad MP.csv: productcode (MPcv) → productnaam (MPnm)."""
    result = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            mpcv = row["MPcv"].strip('"')
            mpnm = row["MPnm"].strip('"')
            result[mpcv] = mpnm
    return result


# Koppeling: generieke sleutel → exacte Nederlandse stofnamen in Stof.csv.
# Gebruik exacte namen om verkeerde koppelingen (bijv. 'citalopram' ↔ 'escitalopram')
# te vermijden.
BRUGADA_DRUG_SUBSTANCES = {
    # Antiaritmica
    "flecainide":        ["flecaïnide"],
    "propafenone":       ["propafenon"],
    "procainamide":      ["procainamide"],
    "disopyramide":      ["disopyramide"],
    "amiodarone":        ["amiodaron"],
    "sotalol":           ["sotalol"],
    "dronedarone":       ["dronedarone"],
    "vernakalant":       ["vernakalant"],
    # Lokale anesthetica
    "lidocaine":         ["lidocaïne"],
    "bupivacaine":       ["bupivacaïne"],
    "levobupivacaine":   ["levobupivacaïne"],
    "procaine":          ["procaïne"],
    # Anesthesie / analgetica
    "ketamine":          ["ketamine"],
    "esketamine":        ["esketamine"],
    "propofol":          ["propofol"],
    "tramadol":          ["tramadol"],
    # Calciumantagonisten
    "verapamil":         ["verapamil"],
    # Anti-epileptica
    "lamotrigine":       ["lamotrigine"],
    "oxcarbazepine":     ["oxcarbazepine"],
    "carbamazepine":     ["carbamazepine"],
    # Maagdarmmiddelen
    "metoclopramide":    ["metoclopramide"],
    "domperidone":       ["domperidon"],
    # Antihistaminica
    "diphenhydramine":   ["difenhydramine"],
    "dimenhydrinate":    ["dimenhydrinaat"],
    "fexofenadine":      ["fexofenadine"],
    # Diuretica / cardiovasculair
    "indapamide":        ["indapamide"],
    "propranolol":       ["propranolol"],
    "ranolazine":        ["ranolazine"],
    # Antidepressiva
    "bupropion":         ["bupropion"],
    "amitriptyline":     ["amitriptyline"],
    "clomipramine":      ["clomipramine"],
    "nortriptyline":     ["nortriptyline"],
    "imipramine":        ["imipramine"],
    "fluoxetine":        ["fluoxetine"],
    "paroxetine":        ["paroxetine"],
    "citalopram":        ["citalopram"],
    "escitalopram":      ["escitalopram"],
    "sertraline":        ["sertraline"],
    "venlafaxine":       ["venlafaxine"],
    # Antipsychotica
    "haloperidol":       ["haloperidol"],
    "quetiapine":        ["quetiapine"],
    "olanzapine":        ["olanzapine"],
    "risperidone":       ["risperidon"],
    "aripiprazole":      ["aripiprazol"],
    # Lithium
    "lithium":           ["lithium"],
    # Anti-emetica (5-HT3-antagonisten)
    "ondansetron":       ["ondansetron"],
    # Antibiotica / schimmelwerende middelen
    "clarithromycin":    ["clarithromycine"],
    "azithromycin":      ["azithromycine"],
    "erythromycin":      ["erythromycine"],
    "itraconazole":      ["itraconazol"],
    "fluconazole":       ["fluconazol"],
    "moxifloxacin":      ["moxifloxacine"],
    # Antimalarica / reumatologie
    "hydroxychloroquine": ["hydroxychloroquine"],
    "chloroquine":        ["chloroquine"],
}


def find_products(drug_substances, stof, sam_by_stof, mp):
    """
    Bouw een dict: generieke sleutel → gesorteerde lijst van Belgische productnamen.

    Alleen exacte overeenkomsten van de basisnaam worden gebruikt om
    verkeerde koppelingen te vermijden.
    """
    # Bouw een omgekeerde index: exacte stofnaam (lower) → stofcode
    name_to_codes = defaultdict(list)
    for code, name in stof.items():
        name_to_codes[name.lower()].append(code)

    results = {}
    for drug, substnames in drug_substances.items():
        product_names = set()
        for sname in substnames:
            for code in name_to_codes.get(sname.lower(), []):
                for mpcv in sam_by_stof.get(code, set()):
                    if mpcv in mp:
                        product_names.add(mp[mpcv])
        results[drug] = sorted(product_names)
    return results


def format_js(results):
    """Formatteer het resultaat als een JavaScript-object."""
    lines = []
    lines.append("/* BEGIN CSV_LOOKUP */")
    lines.append("// Automatisch gegenereerd door scripts/generate_csv_lookup.py")
    lines.append("// Bron: BCFI/FAMHP Stof.csv, Sam.csv, MP.csv")
    lines.append("const CSV_LOOKUP = {")
    for drug in sorted(results):
        names = results[drug]
        if names:
            js_names = ", ".join(f'"{n}"' for n in names)
            lines.append(f'  "{drug}": [{js_names}],')
    lines.append("};")
    lines.append("/* END CSV_LOOKUP */")
    return "\n".join(lines)


def main():
    stof_path = os.path.join(ROOT, "Stof.csv")
    sam_path  = os.path.join(ROOT, "Sam.csv")
    mp_path   = os.path.join(ROOT, "MP.csv")

    for path in [stof_path, sam_path, mp_path]:
        if not os.path.exists(path):
            print(f"Bestand niet gevonden: {path}", file=sys.stderr)
            sys.exit(1)

    stof = load_stof(stof_path)
    sam_by_stof = load_sam(sam_path)
    mp = load_mp(mp_path)

    results = find_products(BRUGADA_DRUG_SUBSTANCES, stof, sam_by_stof, mp)
    print(format_js(results))


if __name__ == "__main__":
    main()
