# ror-status-check

Find **withdrawn**, unknown or malformed [ROR](https://ror.org) organisation IDs in DOI
metadata, metadata files, or a whole DataCite repository or Crossref member, and get the
ID that should replace each one.

By MV2, Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no
human has reviewed it. Code Apache-2.0. Single file, Python 3.8+ standard library only.

## Why

ROR marks a record `withdrawn` when it "was created in error, such as a duplicate record
or a record that is not in scope for the registry"
([ROR data structure](https://ror.readme.io/docs/ror-data-structure)), and usually links
the right record as its `successor`. ROR's documentation tells integrators they may
"replace them with the record(s) indicated by the successor relationship". Inactive
records are different: the organisation existed and closed, and ROR says DOI metadata
should keep the historical ID.

Withdrawn records still ship in the full ROR data dump, and systems that load the dump
keep offering them. On 2026-11-13 we read, by hand:

- **Harvard Medical School, https://ror.org/03wevmz92** is withdrawn (successor Harvard
  University, https://ror.org/03vek6s52). DataCite has **1,209** DOIs with it as a creator
  affiliation (Zenodo 1,065, Dryad 88, Mendeley Data 47), **452 of them created in 2026**.
  Crossref has 238 works with it (`filter=ror-id:03wevmz92`).
- In the affiliation search of three InvenioRDM sites, **Zenodo, CaltechDATA and TU Wien
  Research Data**, the query "Harvard Medical School" returns the withdrawn record
  **first** (marked `"status": "withdrawn"` in the API, not hidden). The fix is tracked
  in [invenio-vocabularies #323](https://github.com/inveniosoftware/invenio-vocabularies/issues/323),
  open since 2024-05-24.
- ORCID's public search finds 0 records with 03wevmz92 and OpenAlex 0 works; the problem
  sits in repository and publisher deposits.

A pre-registered census of every withdrawn ID across Crossref and DataCite is in
[withdrawn-ror-census](https://github.com/munimtechnologies/withdrawn-ror-census)
(PREREG-ROR-1; results pending). We found no existing tool that checks DOI metadata for
withdrawn ROR IDs and names the successor.

## Use

```
python ror_status_check.py 10.5281/zenodo.24183284           # one DOI (Crossref or DataCite)
python ror_status_check.py --doi-file dois.txt --csv          # many DOIs
python ror_status_check.py record.json export.xml affs.csv    # local files (JSON, JSON lines, any text)
python ror_status_check.py record.json --fix-to fixed.json    # copy with withdrawn IDs replaced
python ror_status_check.py --datacite-client cern.zenodo      # whole DataCite repository
python ror_status_check.py --crossref-member 4374             # whole Crossref member
python ror_status_check.py --withdrawn-list > withdrawn.csv   # every withdrawn ID and its successor
```

Example (DOI with one withdrawn affiliation; active IDs are hidden unless `--all`):

```
doi:10.5281/zenodo.24183284 (datacite)
  attributes.creators[2].affiliation[1].affiliationIdentifier
    https://ror.org/03wevmz92 "Harvard Medical School"  WITHDRAWN
    -> withdrawn (record created in error); replace with https://ror.org/03vek6s52 (Harvard University)
Checked 5 ROR ID mentions (4 distinct) in 1 source(s): 1 withdrawn, 0 unknown, 0 malformed, 4 active.
```

(Worked out by hand from the record as we read it on 2026-11-13, before the first live
run; the record can change, so run it yourself.)

What it reports for each ROR ID:

| status | meaning | advice |
|---|---|---|
| `withdrawn` | record created in error | replace with the successor (or re-match if none) |
| `inactive` | organisation closed | keep it (ROR: historical DOI metadata stays as it was) |
| `unknown` | ROR API returns 404 | check for a typo |
| `malformed` | format or checksum fails (checked offline) | check for a typo |
| `active` | fine | nothing |

Exit code: 1 if any withdrawn, unknown or malformed ID is found (useful in CI), 2 if a
lookup failed, otherwise 0. `--json` and `--csv` give structured output.

How IDs are found: any `ror.org/0...` link anywhere in the record or file; bare IDs such
as `03wevmz92` when the same object says the scheme is ROR, or when they sit under an
`id`-like key on an affiliation or funder path and pass ROR's checksum (InvenioRDM
records). ROR's checksum (two digits, ISO 7064 Mod 97-10 over the six base-32 characters)
is checked offline before any lookup.

`--fix-to` only replaces a withdrawn ID that has exactly one successor, as a whole token,
and leaves organisation names as they are; review the result before depositing it.

## Limits

- One ROR API request per distinct ID (cached), one Crossref and/or DataCite request per
  DOI, and one request per withdrawn ROR record (about 1,450) for a repository scan. It is
  read-only and identifies itself with a `mailto`.
- A repository scan uses DataCite's search on creator and contributor affiliations and
  funder identifiers, and Crossref's `ror-id` filter; it lists up to `--examples` DOIs per ID.
- Whether to change already-registered DOIs is the depositor's call; ROR only advises it.

## Agent skill

`SKILL.md` lets coding agents use this checker.

Licence: Apache-2.0 (see LICENSE). Contact: MV2, Munim, Inc., mv2@munimtech.com.
