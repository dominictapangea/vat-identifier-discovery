# Test de fezabilitate: extragerea codului de TVA direct de pe site-urile companiilor
# Verificam daca identificatorii fiscali sunt expusi public pe homepage sau paginile legale
# (Terms, Privacy, Contact), conform reglementarilor de e-commerce din UK.

import re
import time
from urllib.parse import urljoin
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research test - Dominic Tapangea, Veridion tech challenge)"
}

# Esantion de test: mix de ecommerce, servicii B2B si productie industriala
COMPANY_SITES = [
    "https://www.gymshark.com",
    "https://www.bloomandwild.com",
    "https://www.hotelchocolat.com",
    "https://www.cultbeauty.co.uk",
    "https://www.brompton.com",
    "https://www.cognism.com",
    "https://www.gocardless.com",
    "https://www.thoughtmachine.net",
    "https://www.propellernet.co.uk",
    "https://www.hays.co.uk",
    "https://www.renishaw.com",
    "https://www.morganadvancedmaterials.com",
    "https://www.dualit.com",
    "https://www.dssmith.com",
]

# Rute uzuale unde apar de regula datele de inregistrare si identificatorii fiscali
CANDIDATE_PATHS = [
    "",
    "/terms",
    "/terms-and-conditions",
    "/terms-conditions",
    "/contact",
    "/contact-us",
    "/about",
    "/delivery",
    "/privacy",
]

# Pattern pentru coduri GB VAT: keyword "VAT" urmat de 9 cifre (cu/fara prefix GB si spatiere)
VAT_PATTERN = re.compile(
    r"VAT[^0-9]{0,20}(GB)?\s?(\d{3}\s?\d{4}\s?\d{2}|\d{9})",
    re.IGNORECASE,
)


def find_vat_on_site(base_url: str) -> dict:
    """Scaneaza paginile candidate ale unui domeniu pentru a identifica codul de TVA."""
    for path in CANDIDATE_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
        except requests.RequestException:
            continue  # ignoram paginile inactive sau timeout-urile

        if resp.status_code != 200:
            continue

        match = VAT_PATTERN.search(resp.text)
        if match:
            return {
                "found": True,
                "page": url,
                "matched_text": match.group(0),
            }

    return {"found": False, "page": None, "matched_text": None}


if __name__ == "__main__":
    results = []
    for site in COMPANY_SITES:
        print(f"\nTestare: {site}")
        result = find_vat_on_site(site)
        print(f"  {result}")
        results.append((site, result))
        time.sleep(1)  # rate limit preventiv

    found_count = sum(1 for _, r in results if r["found"])
    print(f"\n=== Rezumat: {found_count}/{len(results)} companii au VAT gasit pe site ===")