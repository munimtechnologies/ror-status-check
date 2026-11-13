#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. Made with AI agents working in the name of MV2,
# Munim, Inc. (mv2@munimtech.com).
"""ror_status_check: find withdrawn, unknown or malformed ROR IDs in metadata.

ROR (the Research Organization Registry) marks a record "withdrawn" when it
"was created in error, such as a duplicate record or a record that is not in
scope for the registry", and usually points to the right record with a
"successor" relationship. Repository and publisher systems that load the full
ROR dump keep offering withdrawn records in their affiliation pickers, so new
DOIs keep getting them (Harvard Medical School, https://ror.org/03wevmz92, is
on more than 1,200 DataCite DOIs).

This script checks:
  * DOIs (Crossref or DataCite metadata, fetched live),
  * local files (JSON such as InvenioRDM/Zenodo records, DataCite or Crossref
    JSON, JSON lines; any other text such as XML or CSV is scanned for
    ror.org/... links),
  * a whole DataCite repository (--datacite-client) or Crossref member
    (--crossref-member), one query per withdrawn ROR record.

For every ROR ID found it reports the ROR status and what to do: withdrawn ->
replace with the successor; inactive -> keep (ROR advises keeping historical
IDs in DOI metadata); unknown (404) or malformed (bad checksum) -> fix the
typo. Exit code 1 if any withdrawn, unknown or malformed ID is found, 2 if a
lookup failed, else 0.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.1.0"
MAILTO = "mv2@munimtech.com"
UA = "ror-status-check/%s (MV2, Munim, Inc.; mailto:%s)" % (VERSION, MAILTO)
ROR_API = "https://api.ror.org/v2/organizations"
CROSSREF = "https://api.crossref.org/works"
DATACITE = "https://api.datacite.org/dois"
CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"

URL_RE = re.compile(r"ror\.org/(0[0-9a-z]{4,12})(?![0-9a-z])", re.I)
BARE_RE = re.compile(r"^\s*0[0-9a-z]{6}[0-9]{2}\s*$", re.I)
WELL_FORMED_RE = re.compile(r"0[0-9a-hjkmnp-tv-z]{6}[0-9]{2}")
DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.I)
SCHEME_KEYS = ("scheme", "identifierscheme", "affiliationidentifierscheme",
               "nameidentifierscheme", "funderidentifiertype", "id-type")
ID_KEYS = ("id", "identifier", "affiliationidentifier", "funderidentifier",
           "nameidentifier", "value")
ORG_PATH_WORDS = ("affiliation", "funder", "organization", "organisation",
                  "institution")
NAME_KEYS = ("name", "funderName", "label")
PROBLEMS = ("withdrawn", "unknown", "malformed")
FIELDS = ["source", "path", "ror_id", "status", "name_in_record", "ror_name",
          "successors", "problem", "advice"]


# ------------------------------------------------------------------ ID rules

def checksum_ok(rid):
    """True if rid is a well-formed ROR ID whose two-digit checksum matches.

    A ROR ID is '0', six Crockford base32 characters and a checksum equal to
    98 - (n * 100 mod 97), where n is the base32 value (ISO 7064 Mod 97-10).
    """
    rid = (rid or "").strip().lower()
    if not WELL_FORMED_RE.fullmatch(rid):
        return False
    n = 0
    for ch in rid[1:7]:
        n = n * 32 + CROCKFORD.index(ch)
    return "%02d" % (98 - (n * 100) % 97) == rid[7:]


def normalize_id(x):
    """'https://ror.org/03WEVMZ92' or '03wevmz92' -> '03wevmz92'; else ''."""
    x = (x or "").strip()
    m = URL_RE.search(x)
    if m:
        return m.group(1).lower()
    return x.lower() if BARE_RE.match(x) else ""


# ---------------------------------------------------------------- extraction

def _hit(path, raw, rid, name):
    return {"path": path, "raw": raw, "ror_id": rid, "name_in_record": name or ""}


def _from_string(s, path, name, out):
    n = 0
    for m in URL_RE.finditer(s):
        out.append(_hit(path, m.group(0), m.group(1).lower(), name))
        n += 1
    return n


def _ctx_name(d, inherited):
    for k in NAME_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return inherited


def _scheme_is_ror(d):
    for k, v in d.items():
        if str(k).lower() in SCHEME_KEYS and isinstance(v, str) \
                and v.strip().lower() == "ror":
            return True
    return False


def extract_json(obj, path="", ctx="", out=None):
    """All ROR IDs in a parsed JSON value, with their path and nearest name.

    ror.org links are found anywhere. Bare IDs ('03wevmz92') count when the
    same object says the scheme is ROR, or when they sit under an id-like key
    on an affiliation/funder path and pass the checksum (InvenioRDM style).
    """
    if out is None:
        out = []
    if isinstance(obj, str):
        _from_string(obj, path or "value", ctx, out)
    elif isinstance(obj, dict):
        name = _ctx_name(obj, ctx)
        ror_scheme = _scheme_is_ror(obj)
        org_path = any(w in path.lower() for w in ORG_PATH_WORDS)
        for k, v in obj.items():
            p = "%s.%s" % (path, k) if path else str(k)
            if isinstance(v, str):
                found = _from_string(v, p, name, out)
                if not found and BARE_RE.match(v) and str(k).lower() in ID_KEYS:
                    rid = v.strip().lower()
                    if ror_scheme or (org_path and checksum_ok(rid)):
                        out.append(_hit(p, v.strip(), rid, name))
            else:
                extract_json(v, p, name, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = "%s[%d]" % (path, i)
            if isinstance(v, str):
                _from_string(v, p, ctx, out)
            else:
                extract_json(v, p, ctx, out)
    return out


def extract_text(text):
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        _from_string(line, "line %d" % ln, "", out)
    return out


def extract_any(text):
    """JSON document, JSON lines, or plain text (XML, CSV, ...)."""
    try:
        return extract_json(json.loads(text))
    except ValueError:
        pass
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines:
        out = []
        try:
            for i, ln in enumerate(text.splitlines(), 1):
                if ln.strip():
                    extract_json(json.loads(ln), "line %d" % i, "", out)
            return out
        except ValueError:
            pass
    return extract_text(text)


# ------------------------------------------------------------------- lookups

def parse_ror(item):
    names = item.get("names") or []
    disp = ""
    for n in names:
        if "ror_display" in (n.get("types") or []):
            disp = n.get("value") or ""
            break
    if not disp and names:
        disp = names[0].get("value") or ""
    if not disp:
        disp = item.get("name") or ""          # ROR API v1 shape
    succ = []
    for r in item.get("relationships") or []:
        if (r.get("type") or "").lower() == "successor":
            sid = normalize_id(r.get("id"))
            if sid:
                succ.append({"id": sid, "name": r.get("label") or ""})
    return {"status": (item.get("status") or "").lower(), "ror_name": disp,
            "successors": succ}


def advise(info):
    """(is_problem, advice) for a lookup result."""
    s = info.get("status")
    succ = info.get("successors") or []
    names = ", ".join("https://ror.org/%s (%s)" % (x["id"], x["name"]) for x in succ)
    if s == "active":
        return False, "ok"
    if s == "inactive":
        return False, ("inactive (the organisation closed); ROR advises keeping the "
                       "historical ID in DOI metadata" +
                       ("; successor " + names if succ else ""))
    if s == "withdrawn":
        if len(succ) == 1:
            return True, "withdrawn (record created in error); replace with " + names
        if succ:
            return True, "withdrawn (record created in error); replace with one of " + names
        return True, ("withdrawn (record created in error) and no successor; "
                      "match the affiliation again")
    if s == "unknown":
        return True, "no such ROR record (HTTP 404); check for a typo"
    if s == "malformed":
        return True, "not a valid ROR ID (format or checksum fails); check for a typo"
    return False, "lookup failed: " + str(info.get("error") or s)


def http_get(url, tries=5):
    last = None
    for k in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = "HTTP %d" % e.code
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(60, 3 * 2 ** k))
                continue
            raise RuntimeError(last)
        except (OSError, ValueError) as e:
            last = repr(e)
            time.sleep(min(60, 3 * 2 ** k))
    raise RuntimeError("giving up on %s: %s" % (url, last))


class Checker:
    def __init__(self, get=None, pause=0.1):
        self.get = get or http_get
        self.pause = pause
        self.cache = {}

    def fetch(self, url):
        if self.pause:
            time.sleep(self.pause)
        return self.get(url)

    def lookup(self, rid):
        if rid in self.cache:
            return self.cache[rid]
        if not checksum_ok(rid):
            info = {"status": "malformed", "ror_name": "", "successors": []}
        else:
            try:
                d = self.fetch(ROR_API + "/" + rid)
                if d is None:
                    info = {"status": "unknown", "ror_name": "", "successors": []}
                else:
                    info = parse_ror(d)
            except Exception as e:  # reported per ID, exit code 2
                info = {"status": "error", "ror_name": "", "successors": [],
                        "error": str(e)[:200]}
        self.cache[rid] = info
        return info

    def fetch_doi(self, doi):
        q = urllib.parse.quote(doi, safe="/")
        d = self.fetch("%s/%s?mailto=%s" % (CROSSREF, q, MAILTO))
        if d and isinstance(d.get("message"), dict):
            return "crossref", d["message"]
        d = self.fetch("%s/%s?affiliation=true&publisher=true" % (DATACITE, q))
        if d and isinstance(d.get("data"), dict):
            return "datacite", d["data"]
        return None, None

    def check_hits(self, source, hits):
        rows = []
        for h in hits:
            info = self.lookup(h["ror_id"])
            problem, adv = advise(info)
            rows.append({"source": source, "path": h["path"], "ror_id": h["ror_id"],
                         "raw": h["raw"], "status": info["status"],
                         "name_in_record": h["name_in_record"],
                         "ror_name": info.get("ror_name", ""),
                         "successors": info.get("successors") or [],
                         "problem": problem, "advice": adv})
        return rows

    def list_withdrawn(self):
        items, page = [], 1
        while True:
            d = self.fetch("%s?filter=status:withdrawn&page=%d" % (ROR_API, page))
            batch = (d or {}).get("items") or []
            total = (d or {}).get("number_of_results", 0)
            for it in batch:
                info = parse_ror(it)
                info["id"] = normalize_id(it.get("id"))
                items.append(info)
            if not batch or len(items) >= total:
                break
            page += 1
        return items


def datacite_query(rid):
    u = "https://ror.org/" + rid
    fields = ("creators.affiliation.affiliationIdentifier",
              "contributors.affiliation.affiliationIdentifier",
              "fundingReferences.funderIdentifier")
    return " OR ".join('%s:"%s"' % (f, u) for f in fields)


def scan_repository(checker, client=None, member=None, examples=3, limit=0,
                    progress=None):
    """Withdrawn ROR IDs used in one DataCite client and/or Crossref member."""
    wl = checker.list_withdrawn()
    if limit:
        wl = wl[:limit]
    rows = []
    for i, w in enumerate(wl, 1):
        rid = w["id"]
        targets = []
        if client:
            p = urllib.parse.urlencode({"query": datacite_query(rid), "client-id": client,
                                        "page[size]": examples}, safe=":,")
            d = checker.fetch(DATACITE + "?" + p) or {}
            n = int((d.get("meta") or {}).get("total") or 0)
            ex = [x.get("id") for x in d.get("data") or [] if x.get("id")]
            targets.append(("datacite:" + client, n, ex))
        if member:
            p = urllib.parse.urlencode({"filter": "ror-id:%s,member:%s" % (rid, member),
                                        "rows": examples, "select": "DOI",
                                        "mailto": MAILTO}, safe=":,")
            d = checker.fetch(CROSSREF + "?" + p) or {}
            msg = d.get("message") or {}
            n = int(msg.get("total-results") or 0)
            ex = [x.get("DOI") for x in msg.get("items") or [] if x.get("DOI")]
            targets.append(("crossref:member " + str(member), n, ex))
        for src, n, ex in targets:
            if n:
                _, adv = advise({"status": "withdrawn", "successors": w["successors"]})
                rows.append({"source": src, "ror_id": rid, "ror_name": w["ror_name"],
                             "dois": n, "examples": ex, "successors": w["successors"],
                             "advice": adv})
        if progress and i % 100 == 0:
            progress("%d of %d withdrawn IDs checked, %d in use" % (i, len(wl), len(rows)))
    rows.sort(key=lambda r: -r["dois"])
    return rows


# ----------------------------------------------------------------------- fix

def fix_text(text, replacements):
    """Replace each old ROR ID (as a whole token) with its new ID."""
    n = 0
    for old, new in sorted(replacements.items()):
        pat = re.compile(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % re.escape(old), re.I)
        text, k = pat.subn(new, text)
        n += k
    return text, n


def replacements_from(rows):
    """Withdrawn IDs with exactly one successor -> that successor."""
    out = {}
    for r in rows:
        if r["status"] == "withdrawn" and len(r["successors"]) == 1:
            out[r["ror_id"]] = r["successors"][0]["id"]
    return out


# -------------------------------------------------------------------- output

def _succ_str(succ):
    return ";".join("%s %s" % (s["id"], s["name"]) for s in succ)


def summary_line(rows, n_sources):
    c = {}
    for r in rows:
        c[r["status"]] = c.get(r["status"], 0) + 1
    order = ["withdrawn", "unknown", "malformed", "inactive", "active", "error"]
    parts = ["%d %s" % (c.get(k, 0), k) for k in order if c.get(k) or k in PROBLEMS]
    return "Checked %d ROR ID mentions (%d distinct) in %d source(s): %s." % (
        len(rows), len({r["ror_id"] for r in rows}), n_sources, ", ".join(parts))


def render_text(rows, n_sources, show_all=False, notes=()):
    buf = io.StringIO()
    last = None
    for r in rows:
        if not show_all and r["status"] == "active":
            continue
        if r["source"] != last:
            buf.write("%s\n" % r["source"])
            last = r["source"]
        nm = (' "%s"' % r["name_in_record"]) if r["name_in_record"] else ""
        rid = ("https://ror.org/" + r["ror_id"]) if r["ror_id"] else "(no ID)"
        buf.write("  %s\n    %s%s  %s\n    -> %s\n" % (
            r["path"], rid, nm, r["status"].upper(), r["advice"]))
    for n in notes:
        buf.write("%s\n" % n)
    buf.write(summary_line(rows, n_sources) + "\n")
    return buf.getvalue()


def render_csv(rows, fields):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        r2 = dict(r)
        if "successors" in r2:
            r2["successors"] = _succ_str(r2["successors"])
        if "examples" in r2:
            r2["examples"] = " ".join(r2["examples"])
        w.writerow(r2)
    return buf.getvalue()


def exit_code(rows):
    if any(r.get("problem") for r in rows):
        return 1
    if any(r.get("status") == "error" for r in rows):
        return 2
    return 0


# ---------------------------------------------------------------------- main

def load_inputs(args, doi_file):
    items = list(args)
    if doi_file:
        with open(doi_file, encoding="utf-8") as f:
            items += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return items


def check_inputs(checker, items, read_stdin=None):
    rows, notes, n_sources = [], [], 0
    for arg in items:
        m = DOI_RE.match(arg)
        if m and not os.path.exists(arg):
            doi = m.group(1)
            try:
                agency, rec = checker.fetch_doi(doi)
            except Exception as e:
                notes.append("doi:%s: lookup failed: %s" % (doi, str(e)[:200]))
                rows.append({"source": "doi:" + doi, "path": "", "ror_id": "",
                             "status": "error", "problem": False,
                             "advice": "DOI lookup failed", "successors": [],
                             "name_in_record": "", "ror_name": "", "raw": ""})
                continue
            n_sources += 1
            if rec is None:
                notes.append("doi:%s: not found in Crossref or DataCite" % doi)
                continue
            rows += checker.check_hits("doi:%s (%s)" % (doi, agency), extract_json(rec))
            continue
        if arg == "-":
            text = (read_stdin or sys.stdin.read)()
        else:
            with open(arg, encoding="utf-8", errors="replace") as f:
                text = f.read()
        n_sources += 1
        rows += checker.check_hits(arg, extract_any(text))
    return rows, notes, n_sources


def main(argv=None, get=None, out=None):
    out = out or sys.stdout
    ap = argparse.ArgumentParser(
        prog="ror_status_check",
        description="Find withdrawn, unknown or malformed ROR IDs in DOIs, "
                    "metadata files or whole repositories.")
    ap.add_argument("inputs", nargs="*",
                    help="DOIs (10.x/..., doi:..., https://doi.org/...), files, or - for stdin")
    ap.add_argument("--doi-file", help="file with one DOI or path per line")
    ap.add_argument("--datacite-client", help="DataCite client ID to scan, e.g. cern.zenodo")
    ap.add_argument("--crossref-member", help="Crossref member ID to scan, e.g. 4374")
    ap.add_argument("--withdrawn-list", action="store_true",
                    help="print every withdrawn ROR record with its successors")
    ap.add_argument("--examples", type=int, default=3,
                    help="example DOIs per withdrawn ID in a repository scan")
    ap.add_argument("--limit", type=int, default=0,
                    help="scan only the first N withdrawn IDs (testing)")
    ap.add_argument("--fix-to", help="with one local file: write a copy with each "
                    "withdrawn ID that has exactly one successor replaced by it")
    ap.add_argument("--all", action="store_true", help="also list active IDs")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--pause", type=float, default=0.1, help="seconds between requests")
    ap.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    a = ap.parse_args(argv)
    checker = Checker(get=get, pause=a.pause)

    if a.withdrawn_list:
        wl = checker.list_withdrawn()
        rows = [{"ror_id": w["id"], "ror_name": w["ror_name"],
                 "successors": w["successors"]} for w in wl]
        if a.json:
            out.write(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
        else:
            out.write(render_csv(rows, ["ror_id", "ror_name", "successors"]))
        return 0

    if a.datacite_client or a.crossref_member:
        rows = scan_repository(checker, a.datacite_client, a.crossref_member,
                               a.examples, a.limit,
                               progress=lambda s: print(s, file=sys.stderr, flush=True))
        if a.json:
            out.write(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
        elif a.csv:
            out.write(render_csv(rows, ["source", "ror_id", "ror_name", "dois",
                                        "successors", "examples", "advice"]))
        else:
            for r in rows:
                out.write("%s  https://ror.org/%s  %s: %d DOIs (e.g. %s)\n    -> %s\n" % (
                    r["source"], r["ror_id"], r["ror_name"], r["dois"],
                    ", ".join(r["examples"]), r["advice"]))
            out.write("%d withdrawn ROR IDs in use, on %d ID-DOI pairs.\n" % (
                len(rows), sum(r["dois"] for r in rows)))
        return 1 if rows else 0

    items = load_inputs(a.inputs, a.doi_file)
    if not items:
        ap.error("give DOIs, files, --doi-file, --datacite-client, "
                 "--crossref-member or --withdrawn-list")
    rows, notes, n_sources = check_inputs(checker, items)

    if a.fix_to:
        local = [x for x in items if os.path.exists(x)]
        if len(items) != 1 or len(local) != 1:
            ap.error("--fix-to needs exactly one local file")
        with open(local[0], encoding="utf-8", errors="replace") as f:
            text = f.read()
        fixed, n = fix_text(text, replacements_from(rows))
        with open(a.fix_to, "w", encoding="utf-8", newline="") as f:
            f.write(fixed)
        notes.append("wrote %s with %d replacement(s); names next to the IDs were not "
                     "changed, so check them" % (a.fix_to, n))

    if a.json:
        out.write(json.dumps({"version": VERSION, "results": rows, "notes": notes},
                             indent=1, ensure_ascii=False) + "\n")
    elif a.csv:
        out.write(render_csv(rows, FIELDS))
    else:
        out.write(render_text(rows, n_sources, a.all, notes))
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main())
