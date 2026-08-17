# VAT Identifier Discovery

## Part 1 — Research & Feasibility

### 1. Validating a VAT Number
* **Official HMRC API**: The open v1 endpoint was deprecated in Feb 2025. The current v2 API requires a formal developer registration process (~2 weeks lead time), which did not fit the timeframe of this challenge.
* **Public HMRC Web Checker**: Automated requests against HMRC's public web form (`https://www.tax.service.gov.uk/check-vat-number/enter-vat-details`) by extracting the session CSRF token on initial GET and posting the payload. 
  * *Debugging note*: Initial POST returned `400 Bad Request` due to assuming the field name was `vatNumber`; the form actually expects `target`.
* **Sanity Checks**:
  * Positive test: `765970776` (Google UK Ltd) returned valid with matching entity metadata.
  * Negative test: `000000000` correctly resolved as invalid.
* **Rate-Limit Probing**: Ran 25 consecutive POST requests without artificial delays (~0.29s latency/request). Encountered zero Captchas, blocks, or 429s. (Note: Represents a burst test, not a long-term sustained load).

### 2. VAT Discovery & Footprint Extraction
Finding the identifier remains the core challenge:
* **Companies House Data**: Provides name, registered address, SIC code, and incorporation dates, but lacks VAT identifiers and official website URLs. Useful for baseline company seeding, not direct discovery.
* **Website Scraping**: Under UK regulations (*Electronic Commerce Regulations 2002* & *Trading Disclosures Regulations 2008*), businesses selling online must disclose their VAT number. 
  * Tested an exploratory sample of 14 UK businesses across B2C retail, B2B/SaaS, and manufacturing across their homepage and legal subpaths (`/terms`, `/contact`, `/about`).
  * Yielded **2/14 matches** (Hotel Chocolat and Cult Beauty, both on their Terms pages). Zero matches on B2B SaaS and manufacturing websites.
  * *Manual sanity check*: Manually inspected Gymshark to confirm whether client-side JavaScript rendering hid the identifier from the script. Confirmed the VAT number was genuinely omitted from the static footer/terms.

### 3. Alternative Vector: EORI Numbers
For UK VAT-registered businesses, the EORI standard follows `GB` + `[9-digit VAT]` + `000`. 
* *Constraint*: There is no central public directory mapping company names to EORIs.
* *Observation*: Third-party directories like `eorichecker.eu` block automated access and lack clear data provenance, making them unreliable for a production pipeline without verified sourcing.


### 4. Alternative Vector: Common Crawl Archive
Tested querying Common Crawl's public CDX index to extract target pages via HTTP Range requests without directly hitting company servers.

* **Initial Probing & Edge Cases**:
  * Domain-level wildcard queries returned excessive noise (e.g., third-party Klarna terms, tracking URLs with UTM parameters).
  * Triggered HTTP `429 Too Many Requests` due to missing delays between consecutive WARC byte-range fetches.
* **Refined Approach**:
  * Implemented request throttling and targeted exact URL paths rather than domain wildcards.
  * Validated the query mechanism with a sanity check on `commoncrawl.org` (43 captures confirmed).
  * Queried exact `/terms` subpaths for verified positive cases (Hotel Chocolat, Cult Beauty).
* **Key Finding (Breadth vs. Depth Trade-Off)**:
  * While homepages were present (ex: 3 captures for Hotel Chocolat), the deeper `/terms` pages containing the actual VAT disclosure were not indexed.
  * **Conclusion**: Common Crawl prioritizes domain breadth over site depth. One-off lookups are unreliable for discovering identifiers located several clicks deep; leveraging this data source effectively would require batch-processing bulk WARC extracts on dedicated infrastructure.
---

## Part 2 - Proper sample, Real pipeline, Measured coverage + false-positive rate

### Data Quality & Edge Case: Validated Web Disclosures vs. Regulatory Truth

During HMRC cross-validation of discovered numbers, an edge case highlighted the difference between extracted web data and ground truth:

* **Observation**: The VAT identifier extracted for *Snowbird Foods* (`927328019`) returned `Invalid` from HMRC.
* **Sanity Check**: Manually audited the live webpage to verify whether the extraction script parsed corrupted text or invalid tokens. The number was rendered cleanly and verbatim in the website's footer (no regex or scraping bug).
* **Root Cause**: The company is publicly displaying a non-valid or stale VAT number (likely due to a legacy typo during web development, corporate restructuring, or VAT deregistration without updating static footer assets).
* **Engineering Takeaway**: Proves that "public disclosure" cannot be equated with "valid active status." Pipeline ingestion must treat web-extracted identifiers as unverified candidates until validated against the official HMRC registry.

## Part 3 — Scaling Considerations & Production Architecture

### What I’d Change with Real Resources
The primary bottleneck isn't compute or scraping speed—it is **discovery accuracy**. Two targeted upgrades:

* **SERP API for Domain Resolution**: Replace heuristic domain-guessing with programmatic search lookups.This correctly maps companies whose trading domains differ entirely from their registered legal entity names.
* **Headless Browser Rendering**: Plain HTTP requests miss client-side JavaScript footers on modern SPAs and e-commerce platforms. Adding headless rendering  eliminates this visibility gap.
* **Unit Economics**: $0.002 (search) + $0.01–$0.02 (rendered subpaths) = **$0.01–$0.03 discovery cost per company**. Running a full pass across ~4.2M live UK companies requires an estimated **$40k–$120k** in third-party API spend.


### Failure Modes (What Breaks First)
* **HMRC Verification Throttling**: The public form was only burst-tested (25 requests in 7s). At sustained production volumes (thousands/day), it will likely hit IP blocks, CAPTCHAs, or rate limits. Without access to the authenticated v2 API, this step remains the pipeline's fragile dependency.
* **DOM & Form Fragility**: Unannounced layout shifts (input names changing from `vatNumber` to `target`) silently break automated submission and extraction scripts.

### Production Observability & Maintenance
* **Source Hit Rates Over Time**: Track discovery yield per SIC group. Sudden downward trends indicate broken scrapers, blocked IPs, or layout changes.
* **Rolling Quality & Sanity Audits**: As seen in the *Snowbird Foods* case (clean scraping, but stale/invalid number on the live site), "published by the company" does not guarantee active registry validity. Regular manual sampling of verified records is required to catch drift.
* **Regulatory Tracking**: Monitor post-Brexit UK corporate disclosure laws to ensure the legal basis for public web disclosure remains intact.

## Part 4 — Debate Topics & Edge Cases

### 1. The Checksum Dilemma: Coverage vs. Ethics
* **The Math**: UK VAT numbers use a modulus 97 checksum.
* **The Opportunity**: Generating all valid checksums and querying HMRC would theoretically reconstruct the entire national registry without crawling a single website. Crucially, this is the only automated method capable of capturing sole traders.
* **The Reality**: At 0.29s per check, running 10.3M queries requires 35 days of nonstop traffic against a free public service meant for single invoice lookups. This crosses into abusive scraping and legal risk (Computer Misuse Act). It is technically the highest-coverage vector, but structurally unusable in a production product.

---

### 2. Pipeline Freshness & Churn
* **Decoupled Registries**: Companies House status and HMRC VAT status are completely independent—companies register for VAT without triggering a Companies House event.
* **Stream Maintenance**:
  * **New Entities**: Stream daily Companies House change feeds to trigger web discovery only on newly incorporated businesses.
  * **Existing Pool**: Periodically re-run the HMRC checker over previously discovered numbers. This catches silent deregistrations cheaply via API hits without re-crawling websites.

---

### 3. Error Detection Without Ground Truth
* **Cross-Registry Matching**: Check the name and postcode returned by HMRC against the registered address in Companies House. Any discrepancy flags an invalid match immediately.
* **Multi-Source Corroboration**: Boost confidence scores when the same identifier turns up across distinct touchpoints (website terms page + corporate PDF filing).
* **Drift Monitoring**: Track rolling discovery rates per sector over time—a sharp drop signals layout changes, crawler blocks, or regulatory shifts.
* **Client Feedback Loops**: Monitor customer dispute and correction rates in production as the ultimate data quality indicator.

---

### 4. Data Provenance & Blacklisted Sources
* **Excluded**:
  * *Checksum brute-forcing*: Abusive traffic profile and unacceptable legal risk.
  * *Third-party scrapers (eorichecker.eu)*: Unknown data origin and aggressive anti-bot protection. Ingesting unverified third-party records breaks data lineage and risks corrupting downstream database joins.
* **Trusted**: Direct first-party disclosures (legal terms/footers) cross-validated against authoritative government registries (HMRC, Companies House), where provenance is fully transparent and auditable.
