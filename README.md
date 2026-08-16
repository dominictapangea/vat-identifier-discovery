# VAT Identifier Discovery — Veridion Tech Challenge

## Part 1: Research

### Verification (how do we check if a VAT number is real?)

**Official route (HMRC "Check a UK VAT Number" API v2) — dead end for this timeline.**
The API moved behind authentication in 2025 (v1, which was open, was retired 17 Feb 2025).
Registering for v2 access through HMRC's Developer Hub takes ~2 weeks according to their
own documentation. That doesn't fit a 5-day challenge window, so this route was ruled out
early — not because it doesn't work, but because it can't be ready in time.
Source: https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-registered-companies-api/2.0

**Working alternative: the public web checker.**
https://www.tax.service.gov.uk/check-vat-number/enter-vat-details is HMRC's own public,
unauthenticated form. No API key, no captcha encountered. Fully automatable:
- GET the entry page, extract a `csrfToken` from a hidden input
- POST `{csrfToken, target: <vat_number>, requester: ""}` back to the same path
- Result page URL ends in `/known` (valid) or `/unknown` (invalid) — cheap to check
  success without parsing the full page
- Valid responses include registered business name + address

**Verified with real data:** GB765970776 → valid → "GOOGLE UK LTD", 1 Chamberlain
Square, Birmingham B3 3AX. Confirms the parsing logic is correct, not just plausible.

**Rate limiting: none observed, but only tested at small scale.**
25 consecutive real POST checks (random 9-digit numbers, no delay) → all HTTP 200,
~0.29s/check average, total 7.2s. No throttling, no CAPTCHA challenge appeared.
Caveat: this is a short burst (~7 seconds). Sustained volume (hundreds/thousands of
checks over a longer period) is untested — noted as an open risk for Part 3, not a
confirmed safe limit.
Test date: 16 August 2026.

### Discovery (where do VAT numbers actually live on the open web?)

**Companies House bulk data — good for the company universe, not for VAT.**
Free monthly CSV snapshot of all live UK companies (name, company number, registered
address, SIC codes, incorporation date). No VAT numbers included. Useful as the base
population to sample from, not as a source of the identifier itself.

<!-- Following sections to fill in as we test each source: -->

**[TODO] Legal disclosure requirements (E-Commerce Regulations 2002 etc.)**

**[TODO] Common Crawl / bulk web corpora**

**[TODO] Adjacent identifiers (EORI etc.)**

**[TODO] Public records (insolvency notices, procurement/spend data)**

---

## Part 2: Proof of Concept
<!-- sample selection method, pipeline, coverage %, false-positive rate + how measured -->

---

## Part 3: At scale
<!-- cost per company, what breaks first, what to monitor -->

---

## Debate topics
<!-- checksum brute-force idea, keeping data current, detecting wrongness without
     a reference dataset, which sources you wouldn't trust in a commercial product -->

---

## Beyond the UK (optional)
<!-- Germany comparison, a country where VAT is barely "discoverable", hardest cases -->
