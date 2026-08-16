# Test exploratoriu Common Crawl:
# Verificam daca URL-urile pe care am identificat deja date fiscale prin crawling direct
# exista in indexul CDX si pot fi parsate eficient prin HTTP Range Requests.

from io import BytesIO
import json
import re
import time
import requests
from warcio.archiveiterator import ArchiveIterator

HEADERS = {"User-Agent": "research test - Dominic Tapangea, Veridion tech challenge"}

VAT_PATTERN = re.compile(
    r"VAT[^0-9]{0,20}(GB)?\s?(\d{3}\s?\d{4}\s?\d{2}|\d{9})",
    re.IGNORECASE,
)

# Cazuri pozitive confirmate anterior in test_website_vat.py
KNOWN_VAT_PAGES = {
    "hotelchocolat.com": "https://www.hotelchocolat.com/terms",
    "cultbeauty.co.uk": "https://www.cultbeauty.co.uk/terms-and-conditions",
}

# Cuvinte-cheie pentru prioritizarea paginilor legale si de conformitate
LIKELY_PATH_HINTS = ["term", "contact", "about", "legal", "privacy", "delivery"]


def clean_path(url: str) -> str:
    """Elimina query params (tracking, UTM) pentru a pastra doar ruta de baza."""
    return url.split("?")[0]


def get_latest_crawl_id() -> str:
    """Preia identificatorul celui mai recent snapshot Common Crawl."""
    resp = requests.get("https://index.commoncrawl.org/collinfo.json", headers=HEADERS)
    crawls = resp.json()
    return crawls[0]["id"]


def query_cdx_exact(url: str, crawl_id: str) -> list:
    """Interogheaza indexul CDX pentru o ruta exacta, evitand scanarea pe tot domeniul."""
    index_url = f"https://index.commoncrawl.org/{crawl_id}-index"
    params = {"url": url, "output": "json"}
    resp = requests.get(index_url, params=params, headers=HEADERS)
    if resp.status_code != 200:
        print(f"    [debug] query CDX a esuat: status {resp.status_code}")
        return []

    if not resp.text.strip():
        return []

    return [json.loads(line) for line in resp.text.strip().split("\n") if line]


def fetch_record_text(record: dict) -> str:
    """Descarca strict segmentul WARC asociat paginii prin Range Request."""
    offset = int(record["offset"])
    length = int(record["length"])
    filename = record["filename"]

    range_header = {"Range": f"bytes={offset}-{offset + length - 1}"}

    # Retry cu backoff liniar pentru 429 (rate limits)
    for attempt in range(3):
        resp = requests.get(
            f"https://data.commoncrawl.org/{filename}",
            headers={**HEADERS, **range_header},
        )
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"    rate limited (429), pauza {wait}s inainte de retry...")
            time.sleep(wait)
            continue
        break

    stream = BytesIO(resp.content)
    for warc_record in ArchiveIterator(stream):
        if warc_record.rec_type == "response":
            return warc_record.content_stream().read().decode("utf-8", errors="ignore")
    return ""


if __name__ == "__main__":
    crawl_id = get_latest_crawl_id()
    print(f"Folosim crawl-ul: {crawl_id}\n")

    # Sanity check pe un URL indexat garantat pentru a valida endpoint-ul CDX
    print("=== sanity check: commoncrawl.org ===")
    sanity = query_cdx_exact("https://commoncrawl.org/", crawl_id)
    print(f"  {len(sanity)} capturi gasite\n")

    found_count = 0

    for domain, page_url in KNOWN_VAT_PAGES.items():
        print(f"=== {domain} ===")

        homepage = f"https://www.{domain}/"
        print(f"  test homepage: {homepage}")
        homepage_records = query_cdx_exact(homepage, crawl_id)
        print(f"  {len(homepage_records)} capturi pentru homepage")

        print(f"  cautam exact: {page_url}")
        records = query_cdx_exact(page_url, crawl_id)
        print(f"  {len(records)} capturi gasite pentru acest URL exact")

        if not records:
            print("  Common Crawl nu are aceasta pagina indexata")
            time.sleep(3)
            continue

        # Parsam cel mai recent snapshot capturat
        record = records[-1]
        print(f"  captura din: {record.get('timestamp')}, status {record.get('status')}")

        try:
            text = fetch_record_text(record)
        except Exception as e:
            print(f"    eroare la extragere: {e}")
            time.sleep(3)
            continue

        match = VAT_PATTERN.search(text)
        if match:
            print(f"    GASIT: {match.group(0)}")
            found_count += 1
        else:
            print(f"    VAT neidentificat in continutul extras")

        time.sleep(3)  # Throttling intre domenii conform politicii Common Crawl

    print(f"\n=== Rezumat: VAT identificat via Common Crawl la {found_count}/{len(KNOWN_VAT_PAGES)} companii ===")