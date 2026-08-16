# Test exploratoriu endpoint public HMRC:
# - extragere token CSRF si sesiune din formularul web
# - validare payload returnat (status valid/invalid, detalii entitate)
# - verificare comportament la request-uri repetate (rate limits / captcha)

import random
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://www.tax.service.gov.uk"
ENTRY_URL = f"{BASE}/check-vat-number/enter-vat-details"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (research test - Dominic Tapangea, Veridion tech challenge)"
})


def check_vat(vat_number: str) -> dict:
    # 1. Initializam sesiunea si extragem token-ul CSRF din HTML
    resp = session.get(ENTRY_URL)
    soup = BeautifulSoup(resp.text, "html.parser")

    csrf_input = soup.find("input", {"name": "csrfToken"})
    csrf_token = csrf_input["value"] if csrf_input else None

    form = soup.find("form")
    action = form["action"] if form else None

    print(f"  [debug] status GET: {resp.status_code}")
    print(f"  [debug] csrf token gasit: {bool(csrf_token)}")
    print(f"  [debug] form action: {action}")

    if form:
        print("  [debug] campuri gasite in formular:")
        all_fields = {}
        for tag in form.find_all(["input", "select", "textarea"]):
            name = tag.get("name")
            if not name:
                continue
            field_type = tag.get("type", tag.name)
            value = tag.get("value", "")
            print(f"    - name='{name}' type='{field_type}' value='{value}'")
            all_fields[name] = value

    if not csrf_token or not action:
        return {"error": "Nu am gasit form/csrf - pagina difera de ce ne asteptam. Inspecteaza manual HTML-ul."}

    post_url = action if action.startswith("http") else BASE + action

    payload = {
        "csrfToken": csrf_token,
        "target": vat_number,
        "requester": "",
    }

    print(f"  [debug] payload trimis: {payload}")

    # 2. Trimitem formularul si urmarim redirect-ul
    resp2 = session.post(post_url, data=payload)
    print(f"  [debug] status POST: {resp2.status_code}")
    print(f"  [debug] final URL dupa POST: {resp2.url}")

    # 3. Parsare rapida a continutului util din pagina rezultata
    result_soup = BeautifulSoup(resp2.text, "html.parser")
    main = result_soup.find("main")
    result_text = main.get_text(separator=" | ", strip=True) if main else resp2.text[:1000]

    return {
        "status_code": resp2.status_code,
        "final_url": resp2.url,
        "result_text": result_text,
    }


def check_vat_silent(vat_number: str) -> dict:
    # Versiune fara logs pentru testul de volum/viteza
    resp = session.get(ENTRY_URL)
    soup = BeautifulSoup(resp.text, "html.parser")

    csrf_input = soup.find("input", {"name": "csrfToken"})
    csrf_token = csrf_input["value"] if csrf_input else None
    form = soup.find("form")
    action = form["action"] if form else None

    if not csrf_token or not action:
        return {"status_code": resp.status_code, "final_url": resp.url, "error": "no csrf/form"}

    post_url = action if action.startswith("http") else BASE + action
    payload = {"csrfToken": csrf_token, "target": vat_number, "requester": ""}

    resp2 = session.post(post_url, data=payload)
    return {"status_code": resp2.status_code, "final_url": resp2.url}


if __name__ == "__main__":
    # Baseline check: companie cunoscuta vs. numar inexistent
    test_numbers = ["942017895", "000000000"]

    for vat in test_numbers:
        print(f"\n=== Testare VAT: {vat} ===")
        result = check_vat(vat)
        print(result)
        time.sleep(2)

    # Verificare comportament la burst de 25 request-uri consecutive
    print("\n=== Test rate-limiting: 25 verificari REALE (POST) la rand ===")
    start = time.time()
    status_codes = []
    for i in range(25):
        fake_vat = f"{random.randint(100000000, 999999999)}"
        t0 = time.time()
        result = check_vat_silent(fake_vat)
        elapsed = time.time() - t0
        status_codes.append(result["status_code"])
        print(f"  verificare {i+1}: vat={fake_vat} status={result['status_code']} "
              f"url_final={result['final_url'].split('/')[-1]} timp={elapsed:.2f}s")

    total_time = time.time() - start
    print(f"\n  Total: {total_time:.1f}s pentru 25 verificari "
          f"({total_time/25:.2f}s/verificare in medie)")
    print(f"  Status codes distincte intalnite: {set(status_codes)}")