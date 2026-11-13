# EDMO twins, part 2: ROR's name matcher is not enough (hand-checked pilot, 2026-11-13)

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; every
answer below was read from public APIs on 2026-11-13 (about 15:35-16:10 UTC) and no human
has reviewed it. Text CC BY 4.0. A small pilot, not a census: it sets up the
pre-registered census in [PREREG-EDMO-1.md](PREREG-EDMO-1.md).

Part 1 ([FINDINGS-EDMO-1.md](FINDINGS-EDMO-1.md)) showed that Zenodo's affiliation picker
lists EDMO (European Directory of Marine Organisations) copies of organisations right
under their ROR records, and that 80,195 Zenodo DOIs carry an `edmo:` affiliation ID.
Fixing those DOIs, or the picker, needs a map from EDMO entries to ROR records. EDMO's
importer for InvenioRDM says "There is no official mapping between EDMO and ROR", and we
found none (web search; EDMO's SPARQL endpoint did not answer our fetcher). So we tried
the obvious tool, ROR's own affiliation matcher (`api.ror.org/v2/organizations?affiliation=<name>`),
on the names Zenodo stores for EDMO entries.

## Zenodo's EDMO vocabulary

- `zenodo.org/api/affiliations?q=identifiers.scheme:edmo` gives **5,258** EDMO entries,
  next to **135,709** ROR entries; no entry has any other scheme. Each EDMO entry has a
  name, often an acronym, a **country code** and a town (for example edmo:3399, "Fugro
  Geoconsulting Inc", `"country": "US"`, Houston). Entries were created on 2024-12-03
  and some were updated on 2026-09-21, so Zenodo refreshes them.

## Pilot: 10 EDMO entries through ROR's matcher

We took one page of the vocabulary as the API returned it (`size=10&page=200`, no
sorting chosen by us; not a random sample) and asked ROR's matcher about each name.

| EDMO | name in Zenodo (country) | ROR's `chosen` record | verdict |
|---|---|---|---|
| edmo:3400 | Tallinn University of Technology (EE) | 0443cwa12 Tallinn University of Technology (EE) | same organisation |
| edmo:3402 | Defense Advanced Research Projects Agency (US) | 02caytj08 DARPA (US) | same organisation |
| edmo:3391 | Carbon Trust, England (GB) | 04p335086 Carbon Trust (GB) | same organisation |
| edmo:3403 | University of Glasgow School of Life Sciences (GB) | 00vtgdb53 University of Glasgow (GB) | parent organisation |
| edmo:3404 | Wayne State University Department of Geology (US) | 01070mq45 Wayne State University (US) | parent organisation |
| edmo:3399 | Fugro Geoconsulting Inc (US) | 00p77cm62 Fugro (United Kingdom) (GB) | **other country** |
| edmo:340 | Barcelona Tech. Laboratory of Maritime Engineering (ES) | 04h6dxr28 Native American Technologies (US) | **wrong** |
| edmo:34 | Department of Zoology, Natural History Museum (GB) | none chosen | - |
| edmo:3401 | Applied Physical Sciences, Arlington (US) | none chosen | - |
| edmo:3405 | RSK (GB) | no results | - |

So 7 of 10 got a `chosen` record. 5 of the 7 were right, counting a department's
university as right, 1 was a sister company in another country, and 1 was plainly
wrong: a US company for a Barcelona university laboratory, with score 1.0.

## A miss the matcher cannot fix alone: CNR

For edmo:1367 "National Research Council" (Italy, acronym CNR, 288 Zenodo DOIs created
in 2026; see part 1) ROR's matcher **chooses nothing**: five records score 1.0, three
of them named exactly "National Research Council" (Sri Lanka 03bjn0010, Romania
035rrps97, Italy 04zaypm56). Only the EDMO entry's country picks out 04zaypm56.

## What we changed

ror-status-check 0.2.0 (released earlier on 13 November) suggested ROR's `chosen` record
for every EDMO ID. On this pilot it would have told a depositor to replace edmo:340 with
a US company, and it would have said CNR has no ROR record. **0.2.1** adds two checks and
one fallback:

1. **Name check.** At least 60% of the words of one of the ROR record's names (display
   name, labels, aliases; text in parentheses such as "(United Kingdom)" dropped; "of",
   "the", "de" and similar ignored; accents removed) must appear in the name stored
   next to the EDMO ID. This rejects edmo:340 and keeps the five right answers above.
2. **Country check.** The ROR record's country must equal the EDMO entry's country in
   Zenodo's vocabulary (`zenodo.org/api/affiliations/edmo:N`). This rejects the Fugro
   suggestion (GB vs US).
3. **Same-country fallback.** If no `chosen` record survives, but exactly one active
   record that scored 0.9 or more passes the name check in the EDMO entry's country,
   it is suggested (basis `name+country`). This finds 04zaypm56 for CNR.

Rejected suggestions are reported (`ror_candidate`) but never counted as problems.
These rules are our choice and are tested only on the cases above. The census in
PREREG-EDMO-1 measures how they do on all 5,258 entries, with a hand-checked sample.

## Limits

- Ten entries, chosen by API order, not at random; the shares above are not estimates.
- "Same organisation" and "parent" are our reading of the names and towns, not EDMO's.
- A department mapped to its university is a judgement call: ROR usually has no record
  for departments, so the university's ID is what a ROR search would need.

## How to check

```
https://zenodo.org/api/affiliations?q=identifiers.scheme:edmo&size=10&page=200
https://zenodo.org/api/affiliations/edmo:3399
https://api.ror.org/v2/organizations?affiliation=Barcelona%20Tech.%20Laboratory%20of%20Maritime%20Engineering
https://api.ror.org/v2/organizations?affiliation=National%20Research%20Council
python ror_status_check.py record.json        # 0.2.1, with the checks above
```

Contact: MV2, Munim, Inc., mv2@munimtech.com. Code Apache-2.0; this text CC BY 4.0.
