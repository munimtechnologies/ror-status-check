#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. Made with AI agents working in the name of MV2,
# Munim, Inc. (mv2@munimtech.com).
"""edmo_census: which EDMO entries in an InvenioRDM affiliation vocabulary
(Zenodo's by default) have a ROR twin, and how many DataCite DOIs use them.

Pre-registered in PREREG-EDMO-1.md. Three phases, all read-only public APIs:

  A. vocabulary: every entry with identifiers.scheme:edmo, paged by name;
  B. matching:   ror_status_check.Checker.match_ror (0.2.1 rules: ROR's chosen
                 record if it passes the name and country checks, else a single
                 same-name record in the entry's country);
  C. usage:      for every entry, the number of DataCite DOIs whose creator
                 affiliations carry the EDMO ID; for matched entries also the
                 number of those without the matched ROR ID.

Writes vocab.jsonl, census.csv, summary.json and hand_sample.csv to --out-dir.
"""
import argparse
import csv
import json
import os
import random
import sys
import urllib.parse

import ror_status_check as rsc

VERSION = "0.1.0"
AFF_FIELD = "creators.affiliation.affiliationIdentifier"
KNOWN = {"edmo:3800": "03vek6s52", "edmo:3797": "05dxps055", "edmo:3804": "042nb2s44",
         "edmo:4475": "00hj54h04", "edmo:544": "03zga2b32", "edmo:1367": "04zaypm56"}
CSV_FIELDS = ["edmo_id", "name", "acronym", "country", "status", "ror_id", "ror_name",
              "candidate", "dois", "dois_without_ror"]


def vocab_url(base, page, size):
    q = urllib.parse.urlencode({"q": "identifiers.scheme:edmo", "size": size,
                                "page": page, "sort": "name"}, safe=":")
    return "%s?%s" % (base.rstrip("/"), q)


def fetch_vocab(checker, base=rsc.ZENODO_AFF, size=100, limit=0):
    """All EDMO entries: list of {edmo_id, name, acronym, country}."""
    out, seen, page = [], set(), 1
    while True:
        d = checker.fetch(vocab_url(base, page, size)) or {}
        hits = (d.get("hits") or {}).get("hits") or []
        total = int((d.get("hits") or {}).get("total") or 0)
        for h in hits:
            eid = str(h.get("id") or "").strip().lower()
            if not eid.startswith("edmo:") or eid in seen:
                continue
            seen.add(eid)
            out.append({"edmo_id": eid, "name": (h.get("name") or "").strip(),
                        "acronym": (h.get("acronym") or "").strip(),
                        "country": str(h.get("country") or "").strip().upper()})
        if not hits or len(out) >= total or (limit and len(out) >= limit):
            break
        page += 1
    return out[:limit] if limit else out


def classify(m):
    if m.get("error"):
        return "error"
    if m.get("match"):
        return m.get("basis") or "chosen"
    if m.get("candidate"):
        return "rejected-" + (m.get("reason") or "?")
    if m.get("no_name"):
        return "no-name"
    return "none"


def datacite_total(checker, query):
    p = urllib.parse.urlencode({"query": query, "page[size]": 0}, safe=":,")
    d = checker.fetch(rsc.DATACITE + "?" + p) or {}
    return int((d.get("meta") or {}).get("total") or 0)


def census(checker, entries, usage=True, progress=None):
    rows = []
    for i, e in enumerate(entries, 1):
        if e["country"]:
            checker.cache["edmo-country:" + e["edmo_id"]] = e["country"]
        m = checker.match_ror(e["name"], e["edmo_id"])
        st = classify(m)
        twin = m.get("match") or {}
        cand = m.get("candidate") or {}
        r = dict(e, status=st, ror_id=twin.get("id", ""), ror_name=twin.get("name", ""),
                 candidate=cand.get("id", ""), dois="", dois_without_ror="")
        if usage:
            q = '%s:"%s"' % (AFF_FIELD, e["edmo_id"])
            r["dois"] = datacite_total(checker, q)
            if r["ror_id"] and r["dois"]:
                r["dois_without_ror"] = datacite_total(
                    checker, '%s AND NOT %s:"https://ror.org/%s"' % (q, AFF_FIELD,
                                                                   r["ror_id"]))
            elif r["ror_id"]:
                r["dois_without_ror"] = 0
        rows.append(r)
        if progress and i % 250 == 0:
            progress("%d of %d entries" % (i, len(entries)))
    return rows


def summarize(rows, top=40):
    n = len(rows)
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    matched = [r for r in rows if r["ror_id"]]
    rejected = [r for r in rows if r["status"].startswith("rejected-")]
    pairs_all = sum(int(r["dois"] or 0) for r in rows)
    pairs_m = sum(int(r["dois"] or 0) for r in matched)
    pairs_m_wo = sum(int(r["dois_without_ror"] or 0) for r in matched)
    known = {}
    for r in rows:
        if r["edmo_id"] in KNOWN:
            known[r["edmo_id"]] = {"expected": KNOWN[r["edmo_id"]], "got": r["ror_id"],
                                   "status": r["status"],
                                   "ok": r["ror_id"] == KNOWN[r["edmo_id"]]}

    def share(a, b):
        return round(a / b, 4) if b else None

    return {
        "version": VERSION, "tool": "ror_status_check " + rsc.VERSION,
        "entries": n, "by_status": dict(sorted(by.items())),
        "matched": len(matched), "matched_share": share(len(matched), n),
        "rejected": len(rejected), "rejected_share": share(len(rejected), n),
        "edmo_id_doi_pairs": pairs_all, "pairs_on_matched": pairs_m,
        "pairs_on_matched_share": share(pairs_m, pairs_all),
        "pairs_on_matched_without_ror": pairs_m_wo,
        "pairs_on_matched_without_ror_share": share(pairs_m_wo, pairs_m),
        "entries_with_dois": sum(1 for r in rows if int(r["dois"] or 0) > 0),
        "known_cases": known,
        "top_matched": [{k: r[k] for k in ("edmo_id", "name", "country", "ror_id",
                                           "ror_name", "status", "dois",
                                           "dois_without_ror")}
                        for r in sorted(matched, key=lambda r: -int(r["dois"] or 0))[:top]],
    }


def hand_sample(rows, seed=20261113, n_matched=30, n_rejected=20):
    rng = random.Random(seed)
    matched = sorted((r for r in rows if r["ror_id"]), key=lambda r: r["edmo_id"])
    rejected = sorted((r for r in rows if r["status"].startswith("rejected-")),
                      key=lambda r: r["edmo_id"])
    out = rng.sample(matched, min(n_matched, len(matched)))
    out += rng.sample(rejected, min(n_rejected, len(rejected)))
    return out


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None, get=None):
    ap = argparse.ArgumentParser(prog="edmo_census")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--vocab", default=rsc.ZENODO_AFF)
    ap.add_argument("--limit", type=int, default=0, help="first N entries only (testing)")
    ap.add_argument("--no-usage", action="store_true", help="skip DataCite counts")
    ap.add_argument("--pause", type=float, default=0.15)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    checker = rsc.Checker(get=get, pause=a.pause, edmo_vocab=a.vocab)
    log = lambda s: print(s, file=sys.stderr, flush=True)  # noqa: E731
    entries = fetch_vocab(checker, a.vocab, limit=a.limit)
    log("%d EDMO entries" % len(entries))
    with open(os.path.join(a.out_dir, "vocab.jsonl"), "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    rows = census(checker, entries, usage=not a.no_usage, progress=log)
    write_csv(os.path.join(a.out_dir, "census.csv"), rows, CSV_FIELDS)
    write_csv(os.path.join(a.out_dir, "hand_sample.csv"), hand_sample(rows), CSV_FIELDS)
    s = summarize(rows)
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: s[k] for k in ("entries", "by_status", "matched_share",
                                        "rejected_share", "pairs_on_matched_share",
                                        "pairs_on_matched_without_ror_share")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
