# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. Made with AI agents working in MV2's name.
"""Offline tests for edmo_census (no network: HTTP is faked)."""
import json
import os
import tempfile
import unittest
import urllib.parse

import edmo_census as ec
import ror_status_check as rsc


def org(rid, name, cc):
    return {"id": "https://ror.org/" + rid, "status": "active",
            "names": [{"value": name, "types": ["ror_display", "label"]}],
            "locations": [{"geonames_details": {"country_code": cc}}]}


HARV_MATCH = {"items": [{"chosen": True, "score": 1.0,
                         "organization": org("03vek6s52", "Harvard University", "US")}]}
NRC_MATCH = {"items": [
    {"chosen": False, "score": 1.0,
     "organization": org("03bjn0010", "National Research Council", "LK")},
    {"chosen": False, "score": 1.0,
     "organization": org("04zaypm56", "National Research Council", "IT")}]}
BARCA = "Barcelona Tech. Laboratory of Maritime Engineering"
BARCA_MATCH = {"items": [{"chosen": True, "score": 1.0, "organization": org(
    "04h6dxr28", "Native American Technologies (United States)", "US")}]}
NO_MATCH = {"items": [{"chosen": False, "score": 0.5, "organization": {
    "id": "https://ror.org/05a0ya142", "status": "active",
    "names": [{"value": "Broad Institute", "types": ["ror_display"]}]}}]}

HITS = [{"id": "edmo:3800", "name": "Harvard University", "country": "us"},
        {"id": "edmo:1367", "name": "National Research Council", "acronym": "CNR",
         "country": "IT"},
        {"id": "EDMO:340", "name": BARCA, "country": "ES"},
        {"id": "edmo:6246", "name": "Eodyn", "country": "FR"}]
COUNTS = {'"edmo:3800"': (640, 568), '"edmo:1367"': (288, 135), '"edmo:340"': (5, 5),
          '"edmo:6246"': (0, 0)}


def fake_get(vocab_pages):
    calls = []

    def get(url):
        calls.append(url)
        if url.startswith("https://zenodo.org/api/affiliations?"):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            return vocab_pages.get(int(q["page"][0]))
        if url.startswith(rsc.DATACITE + "?"):
            s = urllib.parse.unquote_plus(url)
            for key, (n_all, n_wo) in COUNTS.items():
                if key in s:
                    return {"meta": {"total": n_wo if "AND NOT" in s else n_all}}
            return {"meta": {"total": 0}}
        if url.startswith(rsc.ROR_API + "?affiliation="):
            for word, resp in (("Harvard", HARV_MATCH), ("National", NRC_MATCH),
                               ("Barcelona", BARCA_MATCH), ("Eodyn", NO_MATCH)):
                if "affiliation=" + word in url:
                    return resp
        return None
    get.calls = calls
    return get


ONE_PAGE = {1: {"hits": {"total": 4, "hits": HITS}}}


class TestVocab(unittest.TestCase):
    def test_url(self):
        self.assertEqual(ec.vocab_url(rsc.ZENODO_AFF, 3, 100),
                         "https://zenodo.org/api/affiliations?q=identifiers.scheme:edmo"
                         "&size=100&page=3&sort=name")

    def test_pages_dedup_and_normalise(self):
        pages = {1: {"hits": {"total": 3, "hits": HITS[:2]}},
                 2: {"hits": {"total": 3, "hits": [HITS[0], HITS[2]]}},
                 3: {"hits": {"total": 3, "hits": [HITS[3]]}}}
        get = fake_get(pages)
        out = ec.fetch_vocab(rsc.Checker(get=get, pause=0), size=2)
        self.assertEqual([e["edmo_id"] for e in out], ["edmo:3800", "edmo:1367", "edmo:340"])
        self.assertEqual(out[0]["country"], "US")
        self.assertEqual(out[1]["acronym"], "CNR")
        self.assertEqual(len(get.calls), 2)

    def test_limit(self):
        out = ec.fetch_vocab(rsc.Checker(get=fake_get(ONE_PAGE), pause=0), limit=2)
        self.assertEqual(len(out), 2)


class TestCensus(unittest.TestCase):
    def run_census(self):
        get = fake_get(ONE_PAGE)
        c = rsc.Checker(get=get, pause=0)
        rows = ec.census(c, ec.fetch_vocab(c))
        return rows, get

    def test_rows(self):
        rows, get = self.run_census()
        got = [(r["edmo_id"], r["status"], r["ror_id"], r["candidate"], r["dois"],
                r["dois_without_ror"]) for r in rows]
        self.assertEqual(got, [
            ("edmo:3800", "chosen", "03vek6s52", "", 640, 568),
            ("edmo:1367", "name+country", "04zaypm56", "", 288, 135),
            ("edmo:340", "rejected-name", "", "04h6dxr28", 5, ""),
            ("edmo:6246", "none", "", "", 0, "")])
        self.assertFalse(any(u.startswith(rsc.ZENODO_AFF) for u in get.calls))

    def test_summary(self):
        rows, _ = self.run_census()
        s = ec.summarize(rows)
        self.assertEqual(s["entries"], 4)
        self.assertEqual(s["by_status"], {"chosen": 1, "name+country": 1, "none": 1,
                                          "rejected-name": 1})
        self.assertEqual((s["matched"], s["matched_share"]), (2, 0.5))
        self.assertEqual((s["rejected"], s["rejected_share"]), (1, 0.25))
        self.assertEqual((s["edmo_id_doi_pairs"], s["pairs_on_matched"],
                          s["pairs_on_matched_share"]), (933, 928, 0.9946))
        self.assertEqual((s["pairs_on_matched_without_ror"],
                          s["pairs_on_matched_without_ror_share"]), (703, 0.7575))
        self.assertEqual(s["entries_with_dois"], 3)
        self.assertTrue(s["known_cases"]["edmo:3800"]["ok"])
        self.assertTrue(s["known_cases"]["edmo:1367"]["ok"])
        self.assertEqual(s["top_matched"][0]["edmo_id"], "edmo:3800")

    def test_hand_sample_deterministic(self):
        rows, _ = self.run_census()
        a = [r["edmo_id"] for r in ec.hand_sample(rows)]
        b = [r["edmo_id"] for r in ec.hand_sample(rows)]
        self.assertEqual(a, b)
        self.assertEqual(sorted(a), ["edmo:1367", "edmo:340", "edmo:3800"])

    def test_classify(self):
        self.assertEqual(ec.classify({"match": None, "error": "x"}), "error")
        self.assertEqual(ec.classify({"match": None, "no_name": True}), "no-name")
        self.assertEqual(ec.classify({"match": {"id": "x"}}), "chosen")


class TestMain(unittest.TestCase):
    def test_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            code = ec.main(["--out-dir", d, "--pause", "0"], get=fake_get(ONE_PAGE))
            self.assertEqual(code, 0)
            for f in ("vocab.jsonl", "census.csv", "summary.json", "hand_sample.csv"):
                self.assertTrue(os.path.exists(os.path.join(d, f)), f)
            with open(os.path.join(d, "summary.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["entries"], 4)
            with open(os.path.join(d, "census.csv"), encoding="utf-8") as f:
                self.assertEqual(len(f.read().strip().splitlines()), 5)


if __name__ == "__main__":
    unittest.main()
