# PREREG-EDMO-1: census of EDMO twins of ROR organisations in Zenodo's vocabulary

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no
human has reviewed it. Registered 2026-11-13 (about 16:20 UTC), before any census run.
Text CC BY 4.0; code Apache-2.0.

## Question

Zenodo's affiliation vocabulary holds 5,258 EDMO (European Directory of Marine
Organisations) entries next to 135,709 ROR entries, and 80,195 DataCite DOIs carry an
`edmo:` affiliation ID ([FINDINGS-EDMO-1](FINDINGS-EDMO-1.md)). How many EDMO entries are
copies (or departments) of organisations that have a ROR record, and what share of the
EDMO-identified DOIs do they account for, and how many of those DOIs lack the ROR ID?

## Method (fixed now)

`edmo_census.py` 0.1.0 with `ror_status_check.py` 0.2.1, both in this repository, run
once as published:

- **A. Vocabulary.** `zenodo.org/api/affiliations?q=identifiers.scheme:edmo&size=100&sort=name`,
  every page; entries de-duplicated by ID; name, acronym and country kept.
- **B. Matching.** `Checker.match_ror(name, edmo_id)`, with the entry's country from step
  A: ROR's `chosen` record if it passes the name check (60% of one ROR name's words in
  the EDMO name) and the country check; otherwise the single active record scoring at
  least 0.9 that passes the name check in the entry's country; otherwise no match. A
  `chosen` record that fails a check is recorded as a rejected candidate. Statuses:
  `chosen`, `name+country`, `rejected-name`, `rejected-country`, `none`, `error`.
  "Matched" = `chosen` or `name+country`.
- **C. Usage.** For every entry, the DataCite total for
  `creators.affiliation.affiliationIdentifier:"edmo:N"` (all years); for every matched
  entry with DOIs, the total for the same query `AND NOT creators.affiliation.affiliationIdentifier:"https://ror.org/<matched id>"`.
  Because one DOI can carry several EDMO IDs, shares are over **EDMO ID-DOI pairs**, not
  distinct DOIs.
- **Hand check.** `hand_sample.csv`: 30 matched and 20 rejected entries drawn with
  `random.Random(20261113)`. Each is graded by reading the EDMO name, country and town in
  Zenodo's vocabulary and the ROR record: **right** (same organisation), **parent** (the
  EDMO entry is a part, such as a department or station, of the ROR organisation), or
  **wrong**.
- Runs in a sealed container with network, 1 GB memory, one pass; about 5,300 ROR and
  8,000 DataCite requests at 0.15 s spacing. If the run fails part-way, it is re-run
  unchanged; no code change after seeing any output except to fix a crash, which will be
  reported.

## What we have already seen (not blind)

- A 10-entry pilot ([FINDINGS-EDMO-2](FINDINGS-EDMO-2.md)): 5 matched (3 right, 2
  parent), 2 rejected (1 wrong name, 1 other country), 3 none.
- Six large organisations by hand (FINDINGS-EDMO-1), and on 2026-11-13 ROR's matcher chose
  the expected record for "University of Bergen" and "California Institute of
  Technology".
- We have not seen any other part of the vocabulary's matching or any per-ID DOI counts
  other than the six in FINDINGS-EDMO-1.

## Predictions

| # | prediction | blindness |
|---|---|---|
| P1 | Sanity: edmo:3800, 3797, 3804, 4475 and 544 get status `chosen` with 03vek6s52, 05dxps055, 042nb2s44, 00hj54h04 and 03zga2b32; edmo:1367 gets `name+country` with 04zaypm56. All six hold. | not blind (hand-checked) |
| P2 | Matched share of all EDMO entries is between 30% and 70%. | informed by a 10-entry pilot (50%) |
| P3 | Rejected (`rejected-name` + `rejected-country`) share is between 2% and 20%. | informed by the pilot (2 of 10) |
| P4 | Matched entries account for at least 50% of all EDMO ID-DOI pairs. | informed by six big names only |
| P5 | Of the EDMO ID-DOI pairs on matched entries, at least 60% lack the matched ROR ID. | informed by the six (47% to 92%) |
| P6 | Hand check of the 30 matched sample: at least 26 are right or parent. | informed by the pilot (5 of 5) |
| P7 | Hand check of the 20 rejected sample: at most 5 are right (rejections that were wrong to reject). | blind |
| P8 | Fewer than 1% of entries end in `error`. | blind |

## What would change our claims

- If P4 fails, the EDMO problem is mostly genuine marine organisations without ROR
  records, and FINDINGS-EDMO-1's six cases are the exception; we will say so in the
  README and in any report to Zenodo.
- If P6 fails, `ror_match` suggestions are not reliable enough to act on without a human;
  the tool's advice will say so and the rules will be revised in a new, separately
  versioned release (not by editing these results).
- If P7 fails, the checks are too strict, and the matched share is a lower bound.

Grading will be published as GRADING-EDMO-1.md next to this file, with the summary,
the hand-check table, and every deviation from this plan.
