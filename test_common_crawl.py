# Test exploratoriu Common Crawl: verificam daca identificatorii fiscali (VAT)
# pot fi extrasi direct din arhiva publica fara crawling activ pe domeniile tinta.
# Flux: Interogare CDX Index -> Range Request pe fisierul WARC -> Regex search.

from io import BytesIO
import json
import re
import time
import requests
from warcio.archiveiterator import ArchiveIterator

HEADERS = {"User-Agent": "research test - Dominic Tapangea, Veridion tech challenge"}

# Pattern standard GB VAT (9 cifre, cu/fara prefix GB si separatori)
VAT_PATTERN = re.compile(
    r"VAT[^0-9]{0,20}(GB)?\s?(\d{3}\s?\d{4}\s?\d{2}|\d{9})",
    re.IGNORECASE,
)

DOMAINS = [
    "gymshark.com",
    "bloomandwild.com",
    "hotelchocolat.com",
    "cultbeauty.co.uk",
    "brompton.com",
    "cognism.com",
    "gocardless.com",
    "thoughtmachine.net",
    "propellernet.co.uk",
    "hays.co.uk",
    "renishaw.com",
    "morganadvancedmaterials.com",
    "dualit.com",
    "dssmith.com",
]

# Cuvinte-cheie pentru prioritizarea paginilor legale si de contact
LIKELY_PATH_HINTS = ["term", "contact", "about", "legal", "privacy", "delivery"]


def get_latest_crawl_id() -> str:
    """Preia identificatorul celui mai recent snapshot Common Crawl disponibil."""
    resp = requests.get("https://index.commoncrawl.org/collinfo.json", headers=HEADERS)
    crawls = resp.json()
    return crawls[0]["id"]


def query_cdx(domain: str, crawl_id: str) -> list:
    """Interogheaza indexul CDX pentru a lista URL-urile capturate pe un domeniu."""
    url = f"https://index.commoncrawl.org/{crawl_id}-index"
    params = {
        "url": f"{domain}/*",
        "output": "json",
        "limit": 50,
    }
    resp = requests.get(url, params=params, headers=HEADERS)
    if resp.status_code != 200:
        return []

    records = []
    for line in resp.text.strip().split("\n"):
        if line:
            records.append(json.loads(line))
    return records


def fetch_record_text(record: dict) -> str:
    """Extrage HTML-ul paginii folosind HTTP Range Request pe segmentul WARC dedicat."""
    offset = int(record["offset"])
    length = int(record["length"])
    filename = record["filename"]

    range_header = {"Range": f"bytes={offset}-{offset + length - 1}"}
    resp = requests.get(
        f"https://data.commoncrawl.org/{filename}",
        headers={**HEADERS, **range_header},
    )

    stream = BytesIO(resp.content)
    for warc_record in ArchiveIterator(stream):
        if warc_record.rec_type == "response":
            return warc_record.content_stream().read().decode("utf-8", errors="ignore")
    return ""


if __name__ == "__main__":
    crawl_id = get_latest_crawl_id()
    print(f"Snapshot Common Crawl activ: {crawl_id}\n")

    found_count = 0

    for domain in DOMAINS:
        print(f"=== {domain} ===")
        records = query_cdx(domain, crawl_id)
        print(f"  {len(records)} rute indexate gasite")

        if not records:
            time.sleep(2)
            continue

        # Filtram cu prioritate rutele legale / termeni / contact
        candidates = [
            r for r in records
            if any(hint in r["url"].lower() for hint in LIKELY_PATH_HINTS)
        ]
        target_records = candidates[:2] if candidates else records[:1]

        vat_found = False
        for record in target_records:
            print(f"  scanare: {record['url']} (status {record.get('status')})")
            try:
                text = fetch_record_text(record)
            except Exception as e:
                print(f"    eroare la parsare WARC: {e}")
                continue

            match = VAT_PATTERN.search(text)
            if match:
                print(f"    IDENTIFICAT: {match.group(0)}")
                vat_found = True
                found_count += 1
                break

        if not vat_found:
            print("    VAT neidentificat in segmentele scanate")

        time.sleep(2)  # Delay preventiv conform regulilor de acces Common Crawl

    print(f"\n=== Rezumat: VAT extras via Common Crawl la {found_count}/{len(DOMAINS)} companii ===")