# ror-status-check

Find **withdrawn**, unknown or malformed [ROR](https://ror.org) organisation IDs, and
**EDMO IDs used where the organisation has a ROR record**, in DOI metadata, metadata
files, or a whole DataCite repository or Crossref member, and get the ROR ID that should
replace each one.

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

**EDMO twins (new in 0.2.0).** Zenodo also loads EDMO, the European Directory of Marine
Organisations, into its affiliation picker, and lists EDMO copies of universities such as
Harvard (edmo:3800), Caltech (edmo:3797) and MIT (edmo:3804) right under their ROR
records. **80,195** Zenodo DOIs carry an `edmo:` affiliation ID (scheme `OTHER` in
DataCite); in 2026 a search by ROR ID misses 45% of the Zenodo DOIs that identify Harvard
University by ID and 50% of Caltech's. Details, numbers and how to check them:
[FINDINGS-EDMO-1.md](FINDINGS-EDMO-1.md).

**Checked EDMO suggestions (new in 0.2.1).** ROR's affiliation matcher goes by name alone.
In a 10-entry pilot it chose a US company for "Barcelona Tech. Laboratory of Maritime
Engineering" and a UK company for a US Fugro office, and for Italy's "National Research
Council" (CNR, edmo:1367) it chose nothing, because several countries have a council of
that name. 0.2.1 checks names and countries before suggesting anything:
[FINDINGS-EDMO-2.md](FINDINGS-EDMO-2.md). A pre-registered census of all 5,258 EDMO
entries in Zenodo's vocabulary is in [PREREG-EDMO-1.md](PREREG-EDMO-1.md) (`edmo_census.py`;
results pending).

A pre-registered census of every withdrawn ID across Crossref and DataCite is in
[withdrawn-ror-census](https://github.com/munimtechnologies/withdrawn-ror-census)
(PREREG-ROR-1; results pending). We found no existing tool that checks DOI metadata for
withdrawn ROR IDs or EDMO twins and names the ROR ID to use.

## Use

```
python ror_status_check.py 10.5281/zenodo.24183284           # one DOI (Crossref or DataCite)
python ror_status_check.py --doi-file dois.txt --csv          # many DOIs
python ror_status_check.py record.json export.xml affs.csv    # local files (JSON, JSON lines, any text)
python ror_status_check.py record.json --fix-to fixed.json    # copy with withdrawn IDs replaced
python ror_status_check.py --datacite-client cern.zenodo      # whole DataCite repository
python ror_status_check.py --crossref-member 4374             # whole Crossref member
python ror_status_check.py --withdrawn-list > withdrawn.csv   # every withdrawn ID and its successor
python ror_status_check.py --no-edmo record.json              # ROR checks only
python ror_status_check.py --edmo-vocab "" record.json        # EDMO checks without the country lookup
```

Example (DOI with one withdrawn ROR affiliation and one EDMO twin; active IDs are hidden
unless `--all`):

```
doi:10.5281/zenodo.24183284 (datacite)
  attributes.creators[2].affiliation[1].affiliationIdentifier
    https://ror.org/03wevmz92 "Harvard Medical School"  WITHDRAWN
    -> withdrawn (record created in error); replace with https://ror.org/03vek6s52 (Harvard University)
  attributes.creators[3].affiliation[0].affiliationIdentifier
    edmo:4475 "The University of Texas at Austin"  EDMO
    -> EDMO ID, not ROR; ROR's affiliation matcher picks https://ror.org/00hj54h04 (The University of Texas at Austin) for this name. If it is the same organisation, use the ROR ID so ROR-based searches and counts find this record
Checked 5 ROR ID mentions (4 distinct) in 1 source(s): 1 withdrawn, 0 unknown, 0 malformed, 4 active. Also 1 EDMO ID mention(s), 1 with a ROR match.
```

(Worked out by hand from the record and ROR's matcher as we read them on 2026-11-13,
before a live run; records change, so run it yourself.)

What it reports for each ID:

| status | meaning | advice |
|---|---|---|
| `withdrawn` | ROR record created in error | replace with the successor (or re-match if none) |
| `inactive` | organisation closed | keep it (ROR: historical DOI metadata stays as it was) |
| `unknown` | ROR API returns 404 | check for a typo |
| `malformed` | format or checksum fails (checked offline) | check for a typo |
| `active` | fine | nothing |
| `edmo` | EDMO ID (`edmo:N` or an `edmo.seadatanet.org/report/N` link) | if a checked ROR record exists (`ror_match`), consider the ROR ID |

How an EDMO ID gets a `ror_match` (0.2.1):

1. ROR's matcher (`?affiliation=` with the name stored next to the EDMO ID) `chosen`, active
   record, if it passes the **name check** (at least 60% of the words of one of its names,
   ignoring "of", "the", "de" and the like, accents and parenthesised text such as
   "(United Kingdom)", appear in the stored name) and the **country check** (same country
   as the EDMO entry in Zenodo's vocabulary, `zenodo.org/api/affiliations/edmo:N`, when
   both are known). `match_basis` = `chosen`.
2. Otherwise the only active record that scored at least 0.9, passes the name check and is
   in the EDMO entry's country. `match_basis` = `name+country`.
3. Otherwise no match. A `chosen` record that failed a check is shown as `ror_candidate`,
   with the reason, and is not counted as a problem.

Exit code: 1 if any withdrawn, unknown or malformed ROR ID, or any EDMO ID with a ROR
match, is found (useful in CI); 2 if a lookup failed; otherwise 0. `--json` and `--csv`
give structured output (CSV columns `edmo_id` and `ror_match` were added in 0.2.0,
`match_basis` and `ror_candidate` in 0.2.1).

How IDs are found: any `ror.org/0...` link anywhere in the record or file; bare IDs such
as `03wevmz92` when the same object says the scheme is ROR, or when they sit under an
`id`-like key on an affiliation or funder path and pass ROR's checksum (InvenioRDM
records). ROR's checksum (two digits, ISO 7064 Mod 97-10 over the six base-32 characters)
is checked offline before any lookup. EDMO IDs are matched using the name stored in the
same object (never a person's name).

`--fix-to` only replaces a withdrawn ID that has exactly one successor, as a whole token,
and leaves organisation names as they are; review the result before depositing it. It
never changes EDMO IDs (that needs a scheme change and a human check).

## EDMO census

`edmo_census.py` (pre-registered in [PREREG-EDMO-1.md](PREREG-EDMO-1.md)) lists every
EDMO entry in an InvenioRDM vocabulary (Zenodo's by default), runs the 0.2.1 matching on
each, and counts the DataCite DOIs that carry each EDMO ID (and, for matched entries, those
without the matched ROR ID):

```
python edmo_census.py --out-dir out/      # vocab.jsonl, census.csv, summary.json, hand_sample.csv
```

## Limits

- One ROR API request per distinct ID or EDMO name, and one Zenodo vocabulary request per
  distinct EDMO ID (both cached), one Crossref and/or DataCite request per DOI, and one
  request per withdrawn ROR record (about 1,450) for a repository scan, plus one for the
  EDMO count. It is read-only and identifies itself with a `mailto`.
- A repository scan uses DataCite's search on creator and contributor affiliations and
  funder identifiers, and Crossref's `ror-id` filter; it lists up to `--examples` DOIs per ID.
- The name and country checks are simple rules, tested on a handful of real cases
  (FINDINGS-EDMO-2). A suggested `ror_match` can still be wrong, for example a parent
  university for a department, or a namesake in the same country. Check it.
- Whether to change already-registered DOIs is the depositor's call; ROR only advises it.

## Agent skill

`SKILL.md` lets coding agents use this checker.

Licence: Apache-2.0 (see LICENSE). Contact: MV2, Munim, Inc., mv2@munimtech.com.
