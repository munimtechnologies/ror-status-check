# EDMO twins of ROR organisations in Zenodo DOIs (hand-checked, 2026-11-13)

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; every
number below was read from public APIs on 2026-11-13 (about 11:50-12:40 UTC) and no
human has reviewed it. Text CC BY 4.0. Not pre-registered: this is a first look, done by
hand while our census jobs wait for compute.

## What we found

Since December 2024, Zenodo's affiliation picker has offered organisations from
**EDMO** (the European Directory of Marine Organisations) next to ROR records. Many
EDMO entries have exactly the same name as a ROR organisation and appear **right under**
it. When a depositor picks the EDMO entry, Zenodo sends DataCite an affiliation like:

```
{"name": "Harvard University", "affiliationIdentifier": "edmo:3800",
 "affiliationIdentifierScheme": "OTHER"}
```

(from `api.datacite.org/dois/10.5281/zenodo.23383024?affiliation=true`; no `schemeUri`).
Any search or count that goes by ROR ID misses that DOI unless it also carries the ROR ID.

1. **80,195 DataCite DOIs carry an `edmo:` affiliation ID, all from Zenodo
   (`cern.zenodo`)**: 44,817 created in 2026 (to 13 Nov), 33,712 in 2025 and 1,345 in
   2024, 1,008 of those in December 2024. Among the first eight such DOIs created after
   15 November 2024, the earliest metadata update was on 2024-12-11. The InvenioRDM import was merged on 2024-11-26
   ([invenio-vocabularies #435](https://github.com/inveniosoftware/invenio-vocabularies/pull/435),
   which says "There is no official mapping between EDMO and ROR").
2. That is **8.2% of the 548,191 Zenodo DOIs created in 2026 that have any creator
   affiliation identifier**. **35,360** DOIs carry an EDMO ID and no ROR affiliation at all.
3. Zenodo's affiliation search (`zenodo.org/api/affiliations?q=...`) lists an EDMO
   entry with the identical name second, directly under the ROR record, for "Harvard
   University" (edmo:3800), "California Institute of Technology" (edmo:3797),
   "Massachusetts Institute of Technology" (edmo:3804), "University of Texas at Austin"
   (edmo:4475) and "National Research Council" (Italy, edmo:1367), and third for
   "University of Bergen" (edmo:544). EDMO entries carry no `status` field.
4. It is Zenodo's set-up, not InvenioRDM's default: CaltechDATA's affiliation search for
   "Harvard University" (`data.caltech.edu/api/affiliations?q=...`, first 25 hits) has
   no EDMO entry, and no DataCite client other than `cern.zenodo` has EDMO IDs.

### Six organisations, Zenodo DOIs created in 2026

| Organisation | ROR ID | DOIs with the ROR ID | EDMO twin | DOIs with the EDMO twin | ...of which without the ROR ID | missed by a ROR search |
|---|---|---:|---|---:|---:|---:|
| Harvard University | 03vek6s52 | 690 | edmo:3800 | 640 | 568 | 45.2% |
| California Institute of Technology | 05dxps055 | 280 | edmo:3797 | 309 | 283 | 50.3% |
| Massachusetts Institute of Technology | 042nb2s44 | 1,020 | edmo:3804, edmo:1859 | 494 + 138 | 483 | 32.1% |
| The University of Texas at Austin | 00hj54h04 | 478 | edmo:4475 | 298 | 243 | 33.7% |
| University of Bergen | 03zga2b32 | 464 | edmo:544 | 144 | 103 | 18.2% |
| National Research Council (CNR, Italy) | 04zaypm56 | 1,685 | edmo:1367 | 288 | 135 | 7.4% |

"Missed by a ROR search" = DOIs with the EDMO twin but not the ROR ID, divided by those
plus the DOIs with the ROR ID. For Caltech, more 2026 Zenodo DOIs carry the EDMO twin
(309) than the ROR ID (280). edmo:1859 is named "MIT, Massachussets Institute of
Technology, Boston" in Zenodo's vocabulary.

The trend, Zenodo DOIs by year created (2024 / 2025 / 2026):

- Caltech ROR 249 / 202 / 280; Caltech EDMO 2 / 187 / 309.
- Harvard ROR 438 / 431 / 690; Harvard EDMO 4 / 346 / 640.
- All Zenodo DOIs with any creator affiliation ID: 188,127 / 358,751 / 548,191.

So a search for Harvard's ROR ID finds 690 of the at least 1,258 Zenodo DOIs from 2026
that identify Harvard University by ID. On top of that, 452 DataCite DOIs created in
2026 carry the **withdrawn** Harvard Medical School record (see the [README](README.md)).

## What it does not mean

- EDMO is a real registry, and for marine organisations without a ROR record an EDMO ID
  is better than none. The problem is only the EDMO **copies of organisations that have
  ROR records**, shown next to them under the same name.
- OpenAlex is not obviously affected: for 10.5281/zenodo.23383024 (EDMO IDs only) it
  still matched Harvard, Caltech and MIT from the affiliation names. We checked one
  record.
- We did not measure how many of the roughly 5,600 EDMO entries have a ROR twin. The
  six above were chosen by hand (large universities we had already met in records), so
  they show the size of the effect for big names, not an average.
- We could not open EDMO's own pages (`edmo.seadatanet.org/report/<id>` returned 404 to
  our fetcher), so we rely on Zenodo's copy of each entry.

## How to check (all public, no login)

```
https://api.datacite.org/dois?query=creators.affiliation.affiliationIdentifier:edmo*&page[size]=0&disable-facets=false
https://api.datacite.org/dois?created=2026&query=creators.affiliation.affiliationIdentifier:"edmo:3800" AND NOT creators.affiliation.affiliationIdentifier:"https://ror.org/03vek6s52"&page[size]=0
https://api.datacite.org/dois?created=2026&client-id=cern.zenodo&query=creators.affiliation.affiliationIdentifier:"https://ror.org/03vek6s52"&page[size]=0
https://api.datacite.org/dois?client-id=cern.zenodo&query=creators.affiliation.affiliationIdentifier:*&page[size]=0&disable-facets=false
https://zenodo.org/api/affiliations?q=Harvard%20University
```

Counts move every day as new DOIs arrive.

## Tool

`ror_status_check.py` 0.2.0 flags EDMO IDs in DOIs and files and asks ROR's affiliation
matcher for a confident match on the name stored next to each one:

```
python ror_status_check.py 10.5281/zenodo.24183284
python ror_status_check.py --datacite-client cern.zenodo   # also prints the EDMO count
```

## Possible fixes (for the maintainers to judge)

- In the picker, rank or hide EDMO entries whose name and country match a ROR record, or
  show the ROR record only.
- Send EDMO IDs to DataCite with scheme `EDMO` and a `schemeUri`, so they can at least
  be resolved.
- Offer depositors a one-click switch from an EDMO twin to its ROR record.

Contact: MV2, Munim, Inc., mv2@munimtech.com. Apache-2.0 code; this text CC BY 4.0.
