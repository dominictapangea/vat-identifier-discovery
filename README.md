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

## Roadmap
* **Part 3**: scaling considerations
* **Debate & Edge Cases**: Discussion topics and non-UK market applicability.