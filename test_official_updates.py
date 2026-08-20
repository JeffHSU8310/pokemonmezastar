"""Append-only official updater tests; never writes the production Pokédex."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scraper import append_only_merge, fetch_and_sync_official_new_cards, parse_international_cards, parse_taiwan_cards


TAIWAN_HTML = """
<html><body><h2>銀河第３彈</h2><div class="cassette-card">
<img src="/uploads/images/new.png"><p>3-1-001<br>測試寶可夢</p></div></body></html>
"""
INTERNATIONAL_INDEX = '<html><body><a href="./999/">Galaxy Version 3</a></body></html>'
INTERNATIONAL_PAGE = """
<html><body><li class="tag-all_list_child"><figure><img src="/assets/new.png"><figcaption>
<p class="tag-no">3-1-001</p><p class="tag-name">Testmon</p>
</figcaption></figure></li></body></html>
"""


class FakeResponse:
    def __init__(self, text, url):
        self.text, self.url, self.apparent_encoding = text, url, "utf-8"

    def raise_for_status(self):
        return None


class FakeSession:
    def get(self, url, **_kwargs):
        if "pokemonmezastar.com.tw" in url:
            return FakeResponse(TAIWAN_HTML, "https://www.pokemonmezastar.com.tw/cassette/21")
        if url.endswith("/999/"):
            return FakeResponse(INTERNATIONAL_PAGE, url)
        return FakeResponse(INTERNATIONAL_INDEX, "https://world.pokemonmezastar.com/sg/tag/")


class OfficialUpdaterTests(unittest.TestCase):
    def test_parsers_extract_official_ids_names_and_images(self):
        series, taiwan = parse_taiwan_cards(TAIWAN_HTML, "https://www.pokemonmezastar.com.tw/cassette/21")
        international = parse_international_cards(INTERNATIONAL_PAGE, "https://world.pokemonmezastar.com/sg/tag/999/")
        self.assertEqual(series, "銀河第3彈")
        self.assertEqual(taiwan[0]["id"], "3-1-001")
        self.assertEqual(international["3-1-001"]["name_en"], "Testmon")

    def test_append_only_merge_never_replaces_existing_card(self):
        original = [{"id": "A", "name": "原始", "nested": {"value": 1}}]
        merged, additions, protected = append_only_merge(
            original, [{"id": "A", "name": "竄改"}, {"id": "B", "name": "新增"}]
        )
        self.assertEqual(merged[0], original[0])
        self.assertEqual(additions, [{"id": "B", "name": "新增"}])
        self.assertEqual(protected, ["A"])

    @patch("scraper.fetch_online_pokemon_metadata", return_value={
        "types": ["一般"], "hp": 80, "attack": 90, "defense": 70,
        "sp_attack": 60, "sp_defense": 70, "speed": 100,
    })
    def test_dual_source_update_only_appends_new_card(self, _metadata):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.json"
            original = [{"id": "OLD", "name": "不可修改", "value": 7}]
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            result = fetch_and_sync_official_new_cards(
                auto_push=False, session=FakeSession(), cards_path=path
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(result["success"])
            self.assertEqual(result["new_count"], 1)
            self.assertEqual(saved[0], original[0])
            self.assertEqual(saved[1]["id"], "3-1-001")
            self.assertEqual(saved[1]["name_en"], "Testmon")


if __name__ == "__main__":
    unittest.main()
