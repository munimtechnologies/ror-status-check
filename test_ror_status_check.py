# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. Made with AI agents working in MV2's name.
"""Offline tests for ror_status_check (no network: HTTP is faked)."""
import csv
import io
import json
import os
import tempfile
import unittest

import ror_status_check as rsc

HMS = {"id": "https://ror.org/03wevmz92", "status": "withdrawn",
       "names": [{"value": "HMS", "types": ["acronym"], "lang": None},
                 {"value": "Harvard Medical School", "types": ["ror_display", "label"],
                  "lang": "en"}],
       "relationships": [
           {"label": "Boston IVF", "type": "related", "id": "https://ror.org/05xckek43"},
           {"label": "Harvard University", "type": "successor",
            "id": "https://ror.org/03vek6s52"}]}
HARVARD = {"id": "https://ror.org/03vek6s52", "status": "active",
           "names": [{"value": "Harvard University", "types": ["ror_display"]}],
           "relationships": []}
BROAD = {"id": "https://ror.org/05a0ya142", "status": "active",
         "names": [{"value": "Broad Institute", "types": ["ror_display"]}]}
PLOS = {"id": "https://ror.org/03bdvdc06", "status": "withdrawn",
        "names": [{"value": "Public Library of Science", "types": ["ror_display"]}],
        "relationships": [{"type": "successor", "id": "https://ror.org/008zgvp64",
                           "label": "Public Library of Science"}]}

DOI = "10.5281/zenodo.24183284"
DATACITE_REC = {"data": {"id": DOI, "attributes": {"creators": [
    {"name": "Ge, Tian", "affiliation": [
        {"name": "Broad Institute", "affiliationIdentifier": "https://ror.org/05a0ya142",
         "affiliationIdentifierScheme": "ROR"},
        {"name": "Harvard Medical School",
         "affiliationIdentifier": "https://ror.org/03wevmz92",
         "affiliationIdentifierScheme": "ROR"}]}]}}}
CROSSREF_REC = {"DOI": "10.53354/x", "author": [
    {"given": "Calum", "family": "MacRae", "affiliation": [
        {"id": [{"id": "https://ror.org/03wevmz92", "id-type": "ROR",
                 "asserted-by": "publisher"}],
         "name": "Harvard Medical School"}]}]}
INVENIO_REC = {"metadata": {
    "creators": [{"person_or_org": {"name": "Ge, Tian", "identifiers": [
        {"scheme": "orcid", "identifier": "0000-0003-4785-4444"}]},
        "affiliations": [{"id": "03wevmz92", "name": "Harvard Medical School"},
                         {"id": "edmo:3800", "name": "Harvard University"}]}],
    "funding": [{"funder": {"id": "021nxhr62", "name": "National Science Foundation"},
                 "award": {"id": "012345678"}}],
    "identifiers": [{"scheme": "ror", "identifier": "03wevmz93"}]}}


def fake_get(table):
    """table: list of (url prefix or predicate, response or exception)."""
    calls = []

    def get(url):
        calls.append(url)
        for key, resp in table:
            if (key(url) if callable(key) else url.startswith(key)):
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return None
    get.calls = calls
    return get


class TestIds(unittest.TestCase):
    def test_checksum(self):
        for good in ("03wevmz92", "03vek6s52", "05a0ya142", "021nxhr62",
                     "0abcdef23", "03WEVMZ92"):
            self.assertTrue(rsc.checksum_ok(good), good)
        for bad in ("03wevmz93", "03wivmz92", "3wevmz92", "", "0abcd", None):
            self.assertFalse(rsc.checksum_ok(bad), bad)

    def test_normalize(self):
        self.assertEqual(rsc.normalize_id("https://ror.org/03WEVMZ92"), "03wevmz92")
        self.assertEqual(rsc.normalize_id("03vek6s52"), "03vek6s52")
        self.assertEqual(rsc.normalize_id("Harvard"), "")
        self.assertEqual(rsc.normalize_id(None), "")


class TestExtract(unittest.TestCase):
    def test_datacite(self):
        hits = rsc.extract_json(DATACITE_REC["data"])
        self.assertEqual([h["ror_id"] for h in hits], ["05a0ya142", "03wevmz92"])
        self.assertEqual(hits[1]["path"],
                         "attributes.creators[0].affiliation[1].affiliationIdentifier")
        self.assertEqual(hits[1]["name_in_record"], "Harvard Medical School")

    def test_crossref(self):
        hits = rsc.extract_json(CROSSREF_REC)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["path"], "author[0].affiliation[0].id[0].id")
        self.assertEqual(hits[0]["name_in_record"], "Harvard Medical School")

    def test_invenio_bare_ids(self):
        hits = rsc.extract_json(INVENIO_REC)
        self.assertEqual([h["ror_id"] for h in hits],
                         ["03wevmz92", "021nxhr62", "03wevmz93"])
        self.assertEqual(hits[0]["path"], "metadata.creators[0].affiliations[0].id")
        self.assertEqual(hits[1]["name_in_record"], "National Science Foundation")
        self.assertEqual(hits[2]["path"], "metadata.identifiers[0].identifier")

    def test_text(self):
        text = ("see https://ror.org/03wevmz92 and\n"
                "ROR.org/03VEK6S52; ror.org/about https://ror.org/0abcd\n")
        hits = rsc.extract_any(text)
        self.assertEqual([h["ror_id"] for h in hits], ["03wevmz92", "03vek6s52", "0abcd"])
        self.assertEqual([h["path"] for h in hits], ["line 1", "line 2", "line 2"])

    def test_json_lines(self):
        text = (json.dumps({"affiliation": [{"name": "HMS",
                "affiliationIdentifier": "https://ror.org/03wevmz92"}]}) + "\n\n" +
                json.dumps({"x": "https://ror.org/03vek6s52"}) + "\n")
        hits = rsc.extract_any(text)
        self.assertEqual([h["ror_id"] for h in hits], ["03wevmz92", "03vek6s52"])
        self.assertEqual(hits[0]["path"], "line 1.affiliation[0].affiliationIdentifier")
        self.assertEqual(hits[1]["path"], "line 3.x")

    def test_top_level_string(self):
        hits = rsc.extract_json("https://ror.org/03wevmz92")
        self.assertEqual([h["ror_id"] for h in hits], ["03wevmz92"])


class TestAdvice(unittest.TestCase):
    def test_parse_ror(self):
        self.assertEqual(rsc.parse_ror(HMS), {
            "status": "withdrawn", "ror_name": "Harvard Medical School",
            "successors": [{"id": "03vek6s52", "name": "Harvard University"}]})

    def test_advise(self):
        self.assertEqual(rsc.advise({"status": "active"}), (False, "ok"))
        p, a = rsc.advise(rsc.parse_ror(HMS))
        self.assertTrue(p)
        self.assertIn("replace with https://ror.org/03vek6s52 (Harvard University)", a)
        p, a = rsc.advise({"status": "withdrawn", "successors": []})
        self.assertTrue(p)
        self.assertIn("no successor", a)
        self.assertFalse(rsc.advise({"status": "inactive", "successors": []})[0])
        self.assertTrue(rsc.advise({"status": "unknown"})[0])
        self.assertTrue(rsc.advise({"status": "malformed"})[0])
        self.assertFalse(rsc.advise({"status": "error", "error": "x"})[0])

    def test_fix_text_whole_tokens(self):
        self.assertEqual(
            rsc.fix_text("x03wevmz92 03wevmz92 03WEVMZ92a", {"03wevmz92": "03vek6s52"}),
            ("x03wevmz92 03vek6s52 03WEVMZ92a", 1))


class TestMain(unittest.TestCase):
    def table(self):
        return [(rsc.DATACITE + "/" + DOI, DATACITE_REC),
                (rsc.CROSSREF + "/10.53354/x", {"message": CROSSREF_REC}),
                (rsc.ROR_API + "/03wevmz92", HMS),
                (rsc.ROR_API + "/03vek6s52", HARVARD),
                (rsc.ROR_API + "/05a0ya142", BROAD)]

    def test_doi_datacite_text(self):
        out = io.StringIO()
        code = rsc.main(["--pause", "0", DOI], get=fake_get(self.table()), out=out)
        s = out.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("doi:%s (datacite)" % DOI, s)
        self.assertIn("WITHDRAWN", s)
        self.assertIn("03vek6s52 (Harvard University)", s)
        self.assertIn("1 withdrawn, 0 unknown, 0 malformed, 1 active", s)
        self.assertNotIn("05a0ya142", s)

    def test_doi_crossref_json(self):
        out = io.StringIO()
        code = rsc.main(["--pause", "0", "--json", "doi:10.53354/x"],
                        get=fake_get(self.table()), out=out)
        d = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(len(d["results"]), 1)
        r = d["results"][0]
        self.assertEqual(r["source"], "doi:10.53354/x (crossref)")
        self.assertEqual(r["path"], "author[0].affiliation[0].id[0].id")
        self.assertEqual(r["status"], "withdrawn")
        self.assertEqual(r["successors"][0]["id"], "03vek6s52")

    def test_doi_not_found(self):
        out = io.StringIO()
        code = rsc.main(["--pause", "0", "10.1234/nope"], get=fake_get([]), out=out)
        self.assertEqual(code, 0)
        self.assertIn("not found in Crossref or DataCite", out.getvalue())

    def test_file_unknown_malformed_csv(self):
        get = fake_get(self.table())
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "affs.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("https://ror.org/03vek6s52\nhttps://ror.org/0abcdef23\n"
                        "https://ror.org/03wevmz93\n")
            out = io.StringIO()
            code = rsc.main([p, "--pause", "0", "--csv"], get=get, out=out)
        rows = list(csv.DictReader(io.StringIO(out.getvalue())))
        self.assertEqual(code, 1)
        self.assertEqual([r["status"] for r in rows], ["active", "unknown", "malformed"])
        self.assertFalse(any("03wevmz93" in u for u in get.calls))

    def test_fix_to(self):
        get = fake_get(self.table())
        rec = {"metadata": {"creators": [{"affiliations": [
            {"id": "03wevmz92", "name": "Harvard Medical School"}]}]},
            "note": "see https://ror.org/03wevmz92"}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "record.json")
            q = os.path.join(d, "fixed.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(rec, f)
            out = io.StringIO()
            code = rsc.main([p, "--fix-to", q, "--pause", "0"], get=get, out=out)
            with open(q, encoding="utf-8") as f:
                fixed = f.read()
        self.assertEqual(code, 1)
        self.assertEqual(fixed.count("03vek6s52"), 2)
        self.assertNotIn("03wevmz92", fixed)
        self.assertIn("with 2 replacement(s)", out.getvalue())
        self.assertEqual(sum("03wevmz92" in u for u in get.calls), 1)

    def test_lookup_error_exit_2(self):
        get = fake_get([(rsc.ROR_API, RuntimeError("boom"))])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("https://ror.org/03vek6s52\n")
            out = io.StringIO()
            code = rsc.main([p, "--pause", "0"], get=get, out=out)
        self.assertEqual(code, 2)
        self.assertIn("lookup failed: boom", out.getvalue())


class TestRepository(unittest.TestCase):
    def table(self):
        return [(rsc.ROR_API + "?filter=status:withdrawn&page=1",
                 {"number_of_results": 2, "items": [HMS, PLOS]}),
                (lambda u: u.startswith(rsc.DATACITE + "?") and "03wevmz92" in u,
                 {"meta": {"total": 1065},
                  "data": [{"id": DOI}, {"id": "10.5281/zenodo.1"}]})]

    def test_scan_datacite_client(self):
        get = fake_get(self.table())
        rows = rsc.scan_repository(rsc.Checker(get=get, pause=0),
                                   client="cern.zenodo", examples=2)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["source"], r["ror_id"], r["dois"]),
                         ("datacite:cern.zenodo", "03wevmz92", 1065))
        self.assertEqual(r["examples"], [DOI, "10.5281/zenodo.1"])
        self.assertIn("replace with https://ror.org/03vek6s52 (Harvard University)",
                      r["advice"])
        self.assertTrue(any("client-id=cern.zenodo" in u for u in get.calls))

    def test_withdrawn_list(self):
        out = io.StringIO()
        code = rsc.main(["--withdrawn-list", "--pause", "0"],
                        get=fake_get(self.table()), out=out)
        self.assertEqual(code, 0)
        self.assertIn("03wevmz92,Harvard Medical School,03vek6s52 Harvard University",
                      out.getvalue())


if __name__ == "__main__":
    unittest.main()
