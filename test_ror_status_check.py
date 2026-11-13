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
UTA = {"id": "https://ror.org/00hj54h04", "status": "active",
       "names": [{"value": "The University of Texas at Austin", "types": ["ror_display"]}]}
UTA_MATCH = {"number_of_results": 2, "items": [
    {"substring": "The University of Texas at Austin", "score": 1.0,
     "matching_type": "SINGLE SEARCH", "chosen": True, "organization": UTA},
    {"substring": "The University of Texas at Austin", "score": 0.91,
     "matching_type": "SINGLE SEARCH", "chosen": False,
     "organization": {"id": "https://ror.org/019kgqr73", "status": "active",
                      "names": [{"value": "The University of Texas at Arlington",
                                 "types": ["ror_display"]}]}}]}
NO_MATCH = {"number_of_results": 1, "items": [
    {"substring": "Eodyn", "score": 0.5, "matching_type": "FUZZY", "chosen": False,
     "organization": BROAD}]}

DOI = "10.5281/zenodo.24183284"
DATACITE_REC = {"data": {"id": DOI, "attributes": {"creators": [
    {"name": "Ge, Tian", "affiliation": [
        {"name": "Broad Institute", "affiliationIdentifier": "https://ror.org/05a0ya142",
         "affiliationIdentifierScheme": "ROR"},
        {"name": "Harvard Medical School",
         "affiliationIdentifier": "https://ror.org/03wevmz92",
         "affiliationIdentifierScheme": "ROR"}]}]}}}
EDMO_DOI = "10.5281/zenodo.999001"
EDMO_REC = {"data": {"id": EDMO_DOI, "attributes": {"creators": [
    {"name": "Ge, Tian", "affiliation": [
        {"name": "Broad Institute", "affiliationIdentifier": "https://ror.org/05a0ya142",
         "affiliationIdentifierScheme": "ROR"},
        {"name": "Harvard Medical School",
         "affiliationIdentifier": "https://ror.org/03wevmz92",
         "affiliationIdentifierScheme": "ROR"}]},
    {"name": "Ni, Yang", "affiliation": [
        {"name": "The University of Texas at Austin",
         "affiliationIdentifier": "edmo:4475",
         "affiliationIdentifierScheme": "OTHER"}]}]}}}
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

# 0.2.1 fixtures, shaped like ROR API v2 and Zenodo answers read on 2026-11-13.
NAT = {"id": "https://ror.org/04h6dxr28", "status": "active",
       "names": [{"value": "Native American Technologies (United States)",
                  "types": ["ror_display", "label"]}],
       "locations": [{"geonames_details": {"country_code": "US"}}]}
BSE = {"id": "https://ror.org/02k09n368", "status": "active",
       "names": [{"value": "Barcelona School of Economics", "types": ["ror_display"]}],
       "locations": [{"geonames_details": {"country_code": "ES"}}]}
BARCA_NAME = "Barcelona Tech. Laboratory of Maritime Engineering"
BARCA_MATCH = {"items": [{"chosen": True, "score": 1.0, "organization": NAT},
                         {"chosen": False, "score": 0.88, "organization": BSE}]}
FUGRO = {"id": "https://ror.org/00p77cm62", "status": "active",
         "names": [{"value": "Fugro (United Kingdom)", "types": ["ror_display", "label"]},
                   {"value": "Fugro GeoConsulting", "types": ["alias"]}],
         "locations": [{"geonames_details": {"country_code": "GB", "name": "Wallingford"}}]}
FUGRO_MATCH = {"items": [{"chosen": True, "score": 1.0, "organization": FUGRO}]}


def nrc(rid, cc):
    return {"id": "https://ror.org/" + rid, "status": "active",
            "names": [{"value": "National Research Council",
                       "types": ["ror_display", "label"]}],
            "locations": [{"geonames_details": {"country_code": cc}}]}


NRC_MATCH = {"items": [{"chosen": False, "score": 1.0, "organization": nrc("03bjn0010", "LK")},
                       {"chosen": False, "score": 1.0, "organization": nrc("035rrps97", "RO")},
                       {"chosen": False, "score": 1.0, "organization": nrc("04zaypm56", "IT")}]}


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


class TestExtractEdmo(unittest.TestCase):
    def test_datacite_edmo(self):
        hits = rsc.extract_edmo_json(EDMO_REC["data"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["edmo_id"], "edmo:4475")
        self.assertEqual(hits[0]["path"],
                         "attributes.creators[1].affiliation[0].affiliationIdentifier")
        self.assertEqual(hits[0]["name_in_record"], "The University of Texas at Austin")

    def test_invenio_edmo(self):
        hits = rsc.extract_edmo_json(INVENIO_REC)
        self.assertEqual([(h["edmo_id"], h["path"], h["name_in_record"]) for h in hits],
                         [("edmo:3800", "metadata.creators[0].affiliations[1].id",
                           "Harvard University")])

    def test_no_name_from_parent(self):
        hits = rsc.extract_edmo_json({"name": "Ge, Tian", "affiliation": ["edmo:3800"]})
        self.assertEqual([(h["edmo_id"], h["name_in_record"]) for h in hits],
                         [("edmo:3800", "")])

    def test_text_forms(self):
        text = ("see EDMO:0544 and https://edmo.seadatanet.org/report/3800\n"
                "xedmo:1 notedmo:2 scheme EDMO edmo:12345678\n")
        hits = rsc.extract_edmo_any(text)
        self.assertEqual([h["edmo_id"] for h in hits], ["edmo:544", "edmo:3800"])
        self.assertEqual([h["path"] for h in hits], ["line 1", "line 1"])

    def test_ror_extraction_unchanged(self):
        self.assertEqual(rsc.extract_any("edmo:3800\n"), [])


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

    def test_advise_edmo(self):
        p, a = rsc.advise_edmo({"match": {"id": "00hj54h04",
                                          "name": "The University of Texas at Austin"}})
        self.assertTrue(p)
        self.assertIn("https://ror.org/00hj54h04 (The University of Texas at Austin)", a)
        self.assertFalse(rsc.advise_edmo({"match": None})[0])
        self.assertIn("no organisation name", rsc.advise_edmo({"match": None,
                                                              "no_name": True})[1])
        self.assertIn("failed: x", rsc.advise_edmo({"match": None, "error": "x"})[1])

    def test_fix_text_whole_tokens(self):
        self.assertEqual(
            rsc.fix_text("x03wevmz92 03wevmz92 03WEVMZ92a", {"03wevmz92": "03vek6s52"}),
            ("x03wevmz92 03vek6s52 03WEVMZ92a", 1))


class TestMatch(unittest.TestCase):
    def test_match_chosen_and_cached(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", UTA_MATCH)])
        c = rsc.Checker(get=get, pause=0)
        m = c.match_ror("The University of Texas at Austin")
        self.assertEqual(m["match"], {"id": "00hj54h04",
                                      "name": "The University of Texas at Austin"})
        c.match_ror("the university of texas at austin")
        self.assertEqual(len(get.calls), 1)
        self.assertIn("affiliation=The+University+of+Texas+at+Austin", get.calls[0])

    def test_match_none_and_no_name(self):
        c = rsc.Checker(get=fake_get([(rsc.ROR_API + "?affiliation=", NO_MATCH)]),
                        pause=0)
        self.assertIsNone(c.match_ror("Eodyn")["match"])
        self.assertTrue(c.match_ror("  ")["no_name"])

    def test_match_ignores_inactive(self):
        gone = dict(UTA, status="withdrawn")
        resp = {"items": [{"chosen": True, "organization": gone}]}
        c = rsc.Checker(get=fake_get([(rsc.ROR_API + "?affiliation=", resp)]), pause=0)
        self.assertIsNone(c.match_ror("The University of Texas at Austin")["match"])


class TestEdmoChecks(unittest.TestCase):
    """0.2.1: a suggested ROR record must share the name and the country."""

    def test_name_ok(self):
        ok = rsc.name_ok
        self.assertTrue(ok("Fugro Geoconsulting Inc", ["Fugro (United Kingdom)"]))
        self.assertFalse(ok(BARCA_NAME, ["Native American Technologies (United States)"]))
        self.assertTrue(ok("MIT, Massachussets Institute of Technology, Boston",
                           ["Massachusetts Institute of Technology"]))
        self.assertTrue(ok("University of Glasgow School of Life Sciences",
                           ["University of Glasgow"]))
        self.assertFalse(ok("University of Bergen", ["University of Bremen"]))
        self.assertTrue(ok("Universite de Bretagne Occidentale",
                           ["Université de Bretagne Occidentale"]))
        self.assertTrue(ok("MIT", ["Massachusetts Institute of Technology"], ["MIT"]))
        self.assertFalse(ok("MIT Boston", ["Massachusetts Institute of Technology"],
                            ["MIT"]))
        self.assertFalse(ok("", ["Harvard University"]))
        self.assertFalse(ok("Harvard University", []))

    def test_ror_names_and_countries(self):
        self.assertEqual(rsc.ror_names(FUGRO),
                         (["Fugro (United Kingdom)", "Fugro GeoConsulting"], []))
        self.assertEqual(rsc.ror_names(HMS), (["Harvard Medical School"], ["HMS"]))
        self.assertEqual(rsc.ror_countries(FUGRO), {"GB"})
        self.assertEqual(rsc.ror_countries({"country": {"country_code": "us"}}), {"US"})
        self.assertEqual(rsc.ror_countries(UTA), set())

    def test_chosen_rejected_by_name(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", BARCA_MATCH),
                        (rsc.ZENODO_AFF + "edmo:340", {"id": "edmo:340", "country": "ES"})])
        m = rsc.Checker(get=get, pause=0).match_ror(BARCA_NAME, "edmo:340")
        self.assertIsNone(m["match"])
        self.assertEqual((m["candidate"]["id"], m["reason"]), ("04h6dxr28", "name"))
        p, a = rsc.advise_edmo(m)
        self.assertFalse(p)
        self.assertIn("shares too few words", a)

    def test_chosen_rejected_by_country_and_cached(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", FUGRO_MATCH),
                        (rsc.ZENODO_AFF + "edmo:3399", {"id": "edmo:3399", "country": "US"})])
        c = rsc.Checker(get=get, pause=0)
        m = c.match_ror("Fugro Geoconsulting Inc", "edmo:3399")
        self.assertIsNone(m["match"])
        self.assertEqual((m["candidate"]["id"], m["reason"], m["edmo_country"],
                          m["ror_countries"]), ("00p77cm62", "country", "US", ["GB"]))
        p, a = rsc.advise_edmo(m)
        self.assertFalse(p)
        self.assertIn("(Fugro (United Kingdom), GB)", a)
        self.assertIn("this EDMO entry is in US", a)
        c.match_ror("Fugro Geoconsulting Inc", "edmo:3399")
        self.assertEqual(len(get.calls), 2)
        self.assertEqual(get.calls[1], rsc.ZENODO_AFF + "edmo:3399")

    def test_chosen_same_country_kept(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", FUGRO_MATCH),
                        (rsc.ZENODO_AFF + "edmo:77", {"country": "gb"})])
        m = rsc.Checker(get=get, pause=0).match_ror("Fugro Geoconsulting Inc", "edmo:77")
        self.assertEqual((m["match"]["id"], m["basis"]), ("00p77cm62", "chosen"))

    def test_same_country_fallback(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", NRC_MATCH),
                        (rsc.ZENODO_AFF + "edmo:1367", {"country": "IT"})])
        m = rsc.Checker(get=get, pause=0).match_ror("National Research Council",
                                                     "edmo:1367")
        self.assertEqual(m["match"], {"id": "04zaypm56", "name": "National Research Council"})
        self.assertEqual((m["basis"], m["country"]), ("name+country", "IT"))
        p, a = rsc.advise_edmo(m)
        self.assertTrue(p)
        self.assertIn("same country (IT): https://ror.org/04zaypm56", a)

    def test_fallback_needs_country_and_uniqueness(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", NRC_MATCH)])
        m = rsc.Checker(get=get, pause=0).match_ror("National Research Council",
                                                     "edmo:1367")
        self.assertEqual(m, {"match": None})
        two = {"items": NRC_MATCH["items"] + [
            {"chosen": False, "score": 1.0, "organization": nrc("01aaaaa00", "IT")}]}
        get = fake_get([(rsc.ROR_API + "?affiliation=", two),
                        (rsc.ZENODO_AFF + "edmo:1367", {"country": "IT"})])
        m = rsc.Checker(get=get, pause=0).match_ror("National Research Council",
                                                     "edmo:1367")
        self.assertIsNone(m["match"])

    def test_no_vocab_no_country_call(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", NRC_MATCH)])
        c = rsc.Checker(get=get, pause=0, edmo_vocab="")
        self.assertIsNone(c.match_ror("National Research Council", "edmo:1367")["match"])
        self.assertFalse(any("zenodo" in u for u in get.calls))

    def test_country_lookup_error_is_ignored(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", FUGRO_MATCH),
                        (rsc.ZENODO_AFF, RuntimeError("down"))])
        m = rsc.Checker(get=get, pause=0).match_ror("Fugro Geoconsulting Inc", "edmo:3399")
        self.assertEqual(m["basis"], "chosen")

    def file_run(self, rec, table, extra=()):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rec.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(rec, f)
            out = io.StringIO()
            code = rsc.main([p, "--pause", "0"] + list(extra), get=fake_get(table),
                            out=out)
        return code, out.getvalue()

    def test_main_rejected_candidate_csv(self):
        rec = {"affiliations": [{"id": "edmo:340", "name": BARCA_NAME}]}
        table = [(rsc.ROR_API + "?affiliation=", BARCA_MATCH),
                 (rsc.ZENODO_AFF + "edmo:340", {"country": "ES"})]
        code, s = self.file_run(rec, table, ["--csv"])
        self.assertEqual(code, 0)
        rows = list(csv.DictReader(io.StringIO(s)))
        self.assertEqual((rows[0]["edmo_id"], rows[0]["ror_match"],
                          rows[0]["ror_candidate"], rows[0]["problem"]),
                         ("edmo:340", "", "04h6dxr28", "False"))
        code, s = self.file_run(rec, table)
        self.assertIn("Also 1 EDMO ID mention(s), 0 with a ROR match, "
                      "1 with a rejected ROR candidate.", s)

    def test_main_same_country_match(self):
        rec = {"affiliations": [{"id": "edmo:1367", "name": "National Research Council"}]}
        table = [(rsc.ROR_API + "?affiliation=", NRC_MATCH),
                 (rsc.ZENODO_AFF + "edmo:1367", {"country": "IT"})]
        code, s = self.file_run(rec, table, ["--csv"])
        self.assertEqual(code, 1)
        rows = list(csv.DictReader(io.StringIO(s)))
        self.assertEqual((rows[0]["ror_match"], rows[0]["match_basis"]),
                         ("04zaypm56", "name+country"))


class TestMain(unittest.TestCase):
    def table(self):
        return [(rsc.DATACITE + "/" + DOI, DATACITE_REC),
                (rsc.DATACITE + "/" + EDMO_DOI, EDMO_REC),
                (rsc.CROSSREF + "/10.53354/x", {"message": CROSSREF_REC}),
                (rsc.ROR_API + "/03wevmz92", HMS),
                (rsc.ROR_API + "/03vek6s52", HARVARD),
                (rsc.ROR_API + "/05a0ya142", BROAD),
                (rsc.ROR_API + "?affiliation=", UTA_MATCH)]

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
        self.assertNotIn("EDMO", s)

    def test_doi_with_edmo(self):
        get = fake_get(self.table())
        out = io.StringIO()
        code = rsc.main(["--pause", "0", EDMO_DOI], get=get, out=out)
        s = out.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("edmo:4475 \"The University of Texas at Austin\"  EDMO", s)
        self.assertIn("https://ror.org/00hj54h04 (The University of Texas at Austin)", s)
        self.assertIn("Checked 2 ROR ID mentions (2 distinct) in 1 source(s): "
                      "1 withdrawn, 0 unknown, 0 malformed, 1 active. "
                      "Also 1 EDMO ID mention(s), 1 with a ROR match.", s)
        self.assertEqual(sum(u.startswith(rsc.ROR_API + "?affiliation=")
                             for u in get.calls), 1)

    def test_no_edmo_flag(self):
        get = fake_get(self.table())
        out = io.StringIO()
        rsc.main(["--pause", "0", "--no-edmo", EDMO_DOI], get=get, out=out)
        self.assertNotIn("EDMO", out.getvalue())
        self.assertFalse(any(u.startswith(rsc.ROR_API + "?affiliation=")
                             for u in get.calls))

    def test_edmo_csv_columns(self):
        out = io.StringIO()
        rsc.main(["--pause", "0", "--csv", EDMO_DOI], get=fake_get(self.table()), out=out)
        rows = list(csv.DictReader(io.StringIO(out.getvalue())))
        e = [r for r in rows if r["status"] == "edmo"]
        self.assertEqual(len(e), 1)
        self.assertEqual((e[0]["edmo_id"], e[0]["ror_match"], e[0]["problem"]),
                         ("edmo:4475", "00hj54h04", "True"))

    def test_edmo_without_match_exit_0(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", NO_MATCH)])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rec.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"affiliations": [{"id": "edmo:6246", "name": "Eodyn"}]}, f)
            out = io.StringIO()
            code = rsc.main([p, "--pause", "0"], get=get, out=out)
        self.assertEqual(code, 0)
        self.assertIn("no confident match", out.getvalue())
        self.assertIn("Also 1 EDMO ID mention(s), 0 with a ROR match.", out.getvalue())

    def test_edmo_match_error_exit_2(self):
        get = fake_get([(rsc.ROR_API + "?affiliation=", RuntimeError("boom"))])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rec.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"affiliations": [{"id": "edmo:3800",
                                             "name": "Harvard University"}]}, f)
            out = io.StringIO()
            code = rsc.main([p, "--pause", "0"], get=get, out=out)
        self.assertEqual(code, 2)
        self.assertIn("ROR name match failed: boom", out.getvalue())

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
        return [(lambda u: u.startswith(rsc.DATACITE + "?") and "edmo" in u,
                 {"meta": {"total": 80195}, "data": []}),
                (rsc.ROR_API + "?filter=status:withdrawn&page=1",
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

    def test_edmo_count(self):
        get = fake_get(self.table())
        n = rsc.edmo_count(rsc.Checker(get=get, pause=0), "cern.zenodo")
        self.assertEqual(n, 80195)
        self.assertIn("client-id=cern.zenodo", get.calls[0])
        self.assertIn("edmo%2A", get.calls[0])

    def test_main_scan_text_with_edmo_line(self):
        out = io.StringIO()
        code = rsc.main(["--datacite-client", "cern.zenodo", "--pause", "0"],
                        get=fake_get(self.table()), out=out)
        s = out.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("1 withdrawn ROR IDs in use, on 1065 ID-DOI pairs.", s)
        self.assertIn("80195 DOIs in datacite:cern.zenodo carry an EDMO affiliation ID", s)

    def test_withdrawn_list(self):
        out = io.StringIO()
        code = rsc.main(["--withdrawn-list", "--pause", "0"],
                        get=fake_get(self.table()), out=out)
        self.assertEqual(code, 0)
        self.assertIn("03wevmz92,Harvard Medical School,03vek6s52 Harvard University",
                      out.getvalue())


if __name__ == "__main__":
    unittest.main()
