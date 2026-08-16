import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin
from difflib import SequenceMatcher

INPUT_CSV = "sample_companies_with_websites.csv"
OUTPUT_CSV = "pipeline_results.csv"

HEADERS = {"User-Agent": "research test - Dominic Tapangea, Veridion tech challenge"}

CANDIDATE_PATHS = ["", "/terms", "/terms-and-conditions", "/terms-conditions",
                    "/contact", "/contact-us", "/about", "/delivery", "/privacy"]

VAT_PATTERN = re.compile(
    r"VAT[^0-9]{0,20}(GB)?\s?(\d{3}\s?\d{4}\s?\d{2}|\d{9})",
    re.IGNORECASE
)

HMRC_ENTRY_URL = "https://www.tax.service.gov.uk/check-vat-number/enter-vat-details"

LEGAL_SUFFIXES = ["limited", "ltd", "plc", "llp", "lp", "company", "co", "group", "holdings", "uk"]


def find_vat_on_site(base_url):
    for path in CANDIDATE_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=6)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        match = VAT_PATTERN.search(resp.text)
        if match:
            vat_digits = re.sub(r"\D", "", match.group(0))[-9:]
            return {"found": True, "page": url, "vat_number": vat_digits}
    return {"found": False, "page": None, "vat_number": None}


def verify_vat_hmrc(vat_number):
    # aceeasi logica din test.py - CSRF token + POST pe "target"
    session = requests.Session()
    resp = session.get(HMRC_ENTRY_URL, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrfToken"})
    if not csrf_input:
        return {"valid": False, "registered_name": None}

    payload = {"csrfToken": csrf_input["value"], "target": vat_number, "requester": ""}
    resp2 = session.post(HMRC_ENTRY_URL, data=payload)

    if "/known" not in resp2.url:
        return {"valid": False, "registered_name": None}

    text = BeautifulSoup(resp2.text, "html.parser").get_text(separator="|", strip=True)
    registered_name = None
    if "Registered business name" in text:
        after = text.split("Registered business name")[1]
        registered_name = after.split("|")[1] if "|" in after else after[:100]

    return {"valid": True, "registered_name": registered_name}


def clean_name(n):
    n = n.lower()
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    return " ".join(w for w in n.split() if w not in LEGAL_SUFFIXES)


def name_similarity(name1, name2):
    return SequenceMatcher(None, clean_name(name1), clean_name(name2)).ratio()


df = pd.read_csv(INPUT_CSV)
df_with_site = df[df["guessed_website"].notna()].copy()
print(f"{len(df_with_site)} companii au site gasit, rulez pipeline-ul pe ele\n")

results = []

for _, row in df_with_site.iterrows():
    name = row["CompanyName"]
    site = row["guessed_website"]
    print(f"--- {name} ({site}) ---")

    vat_result = find_vat_on_site(site)
    if not vat_result["found"]:
        print("  nimic gasit pe site")
        results.append({"CompanyName": name, "website": site, "vat_found_on_site": None,
                         "hmrc_valid": None, "registered_name": None, "name_match_score": None})
        time.sleep(0.5)
        continue

    vat_num = vat_result["vat_number"]
    print(f"  gasit {vat_num} pe {vat_result['page']}")

    hmrc_result = verify_vat_hmrc(vat_num)
    if not hmrc_result["valid"]:
        print("  HMRC zice invalid")
        results.append({"CompanyName": name, "website": site, "vat_found_on_site": vat_num,
                         "hmrc_valid": False, "registered_name": None, "name_match_score": None})
        time.sleep(1)
        continue

    registered_name = hmrc_result["registered_name"]
    score = name_similarity(name, registered_name) if registered_name else 0
    print(f"  HMRC valid, nume inregistrat: '{registered_name}' (match {score:.2f})")

    results.append({"CompanyName": name, "website": site, "vat_found_on_site": vat_num,
                     "hmrc_valid": True, "registered_name": registered_name, "name_match_score": score})

    time.sleep(1)

results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_CSV, index=False)

total_sample = len(df)
found_on_site = results_df["vat_found_on_site"].notna().sum()
hmrc_valid = (results_df["hmrc_valid"] == True).sum()
# 0.5 e un prag ales cu ochiul, nu are o justificare matematica - de verificat
# manual in pipeline_results.csv daca separa bine cazurile reale de cele suspecte
true_positive = (results_df["name_match_score"] >= 0.5).sum()
suspect_fp = ((results_df["hmrc_valid"] == True) & (results_df["name_match_score"] < 0.5)).sum()

print("\n=== rezumat ===")
print(f"esantion: {total_sample}")
print(f"site gasit: {len(df_with_site)}")
print(f"VAT gasit pe site: {found_on_site} ({found_on_site/total_sample*100:.1f}% din esantion)")
print(f"valid la HMRC: {hmrc_valid}")
print(f"nume corespunde (match >= 0.5): {true_positive}")
print(f"suspecte fals-pozitiv: {suspect_fp}")
if hmrc_valid > 0:
    print(f"rata fals-pozitiv: {suspect_fp/hmrc_valid*100:.1f}%")