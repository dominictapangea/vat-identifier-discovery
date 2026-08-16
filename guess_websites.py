# Mapare euristica nume companie -> domeniu web oficial 
# Registrul Companies House nu contine URL-uri de website.
# Flux: Curatare sufixe juridice -> Generare slug & candidate TLD (.co.uk / .com)
# -> Verificare HTTP GET cu timeout scurt -> Salvare progresiva a rezultatelor.

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests

INPUT_CSV = "sample_companies.csv"
OUTPUT_CSV = "sample_companies_with_websites.csv"

HEADERS = {"User-Agent": "research test - Dominic Tapangea, Veridion tech challenge"}

# Sufixe juridice eliminate pentru a izola denumirea comerciala
LEGAL_SUFFIXES = [
    "limited", "ltd", "plc", "llp", "lp", "company", "co",
    "group", "holdings", "uk",
]


def clean_company_name(name: str) -> str:
    """Normalizeaza denumirea companiei prin eliminarea caracterelor speciale si formelor legale."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)  # eliminam punctuatia si simbolurile
    words = name.split()
    words = [w for w in words if w not in LEGAL_SUFFIXES]
    return "".join(words)


def guess_domains(company_name: str) -> list:
    """Genereaza variante candidate de domenii pe TLD-urile principale din UK."""
    slug = clean_company_name(company_name)
    if not slug:
        return []
    return [
        f"https://www.{slug}.co.uk",
        f"https://www.{slug}.com",
    ]


def check_domain(url: str) -> bool:
    """Verifica disponibilitatea domeniului printr-un GET rapid cu timeout de 3s.
    Evitam dublarea round-trip-urilor (HEAD + GET) pentru domenii inexistente."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=3, allow_redirects=True)
        return resp.status_code < 400
    except requests.RequestException:
        return False


def resolve_company(row: tuple) -> tuple:
    """Testeaza secvential candidatii de domeniu pentru o companie si returneaza primul URL valid."""
    idx, name = row
    for url in guess_domains(name):
        if check_domain(url):
            return idx, url
    return idx, None


if __name__ == "__main__":
    df = pd.read_csv(INPUT_CSV)
    print(f"Rulam rezolvarea de domenii pentru {len(df)} companii (pool de 15 thread-uri)...\n")

    results = {}
    tasks = list(zip(df.index, df["CompanyName"]))

    # Procesare asincrona pentru reducerea timpului total de I/O
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(resolve_company, task): task for task in tasks}
        done_count = 0

        for future in as_completed(futures):
            idx, found = future.result()
            results[idx] = found
            done_count += 1

            name = df.loc[idx, "CompanyName"]
            status = found if found else "-"
            print(f"  [{done_count}/{len(df)}] {name[:50]:50s} -> {status}")

            # Checkpoint periodic la fiecare 20 de interogari pentru persistenta datelor
            if done_count % 20 == 0:
                df["guessed_website"] = df.index.map(results)
                df.to_csv(OUTPUT_CSV, index=False)

    df["guessed_website"] = df.index.map(results)
    df.to_csv(OUTPUT_CSV, index=False)

    hit_rate = df["guessed_website"].notna().sum() / len(df) * 100
    print(f"\n=== Rezumat: domeniu identificat la {df['guessed_website'].notna().sum()}/{len(df)} companii ({hit_rate:.1f}%) ===")
    print(df.groupby("sample_group")["guessed_website"].apply(lambda x: x.notna().sum()))