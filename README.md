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

---

## Roadmap
* **Part 2**: proper sample, real pipeline, measured coverage + false-positive rate
* **Part 3**: scaling considerations
* **Debate & Edge Cases**: Discussion topics and non-UK market applicability.