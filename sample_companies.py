# Esantionare stratificata din registrul oficial Companies House (BasicCompanyData)
# Selectam un subset de companii active, distribuit pe grupe mari de coduri SIC (UK SIC 2007)
# pentru a analiza gradul de publicare a codurilor de TVA in diverse industrii.

import pandas as pd

CSV_PATH = "BasicCompanyDataAsOneFile-2026-08-01.csv"
SAMPLE_SIZE = 200
RANDOM_SEED = 42  # Seed fix pentru reproductibilitatea esantionului

# Categorii economice principale bazate pe primele 2 cifre din codul SIC
SIC_GROUPS = {
    "retail": ["47"],                                      # Comert cu amanuntul
    "manufacturing": ["10", "11", "13", "14", "20", "25", "28"],  # Industrie prelucratoare
    "professional_b2b": ["62", "63", "70", "73", "74"],   # IT, consultanta si servicii B2B
    "construction": ["41", "42", "43"],                   # Constructii
    "hospitality": ["55", "56"],                           # HoReCa
}

if __name__ == "__main__":
    print("Incarcare dataset Companies House (~2GB CSV)...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    # Sanitizare nume coloane (Companies House include adesea spatii precum ' CompanyNumber')
    df.columns = df.columns.str.strip()
    print(f"Total entitati in dataset: {len(df)}")

    # Filtram doar companiile active
    df = df[df["CompanyStatus"] == "Active"]
    print(f"Total companii active: {len(df)}")

    # Extragere prefix SIC din prima descriere economica (ex: '47110 - ...' -> '47')
    df["sic_prefix"] = df["SICCode.SicText_1"].astype(str).str[:2]

    samples = []
    per_group = SAMPLE_SIZE // len(SIC_GROUPS)

    # Esantionare proportionala per grupa economica
    for group_name, prefixes in SIC_GROUPS.items():
        group_df = df[df["sic_prefix"].isin(prefixes)]
        n = min(per_group, len(group_df))
        sample = group_df.sample(n=n, random_state=RANDOM_SEED).copy()
        sample["sample_group"] = group_name
        samples.append(sample)
        print(f"  [{group_name}] companii disponibile: {len(group_df)} | extrase: {n}")

    result = pd.concat(samples)

    # Pastram doar campurile necesare pentru discovery si validare
    result = result[[
        "CompanyName", "CompanyNumber", "sample_group",
        "SICCode.SicText_1", "RegAddress.PostTown", "RegAddress.PostCode",
    ]]

    result.to_csv("sample_companies.csv", index=False)
    print(f"\nEsantion salvat in sample_companies.csv: {len(result)} companii")
    print(result["sample_group"].value_counts())