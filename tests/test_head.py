from __future__ import annotations
from pathlib import Path
import json
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys_path_appended = None

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_spine import Head, build_spine, expand_search, write_spine  # noqa: E402


def test_head_json_is_valid():
    data = json.loads((ROOT / "head.json").read_text(encoding="utf-8"))
    Head(data).validate()  # must not raise


def test_schema_version_pinned():
    data = json.loads((ROOT / "head.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"


def test_expand_search_fills_query():
    t = "https://github.com/search?q={q}"
    assert expand_search(t, "memetics") == \
        "https://github.com/search?q=memetics"
    assert expand_search("https://example.com/plain", "x") == \
        "https://example.com/plain"


def test_build_spine_seeds_connections(tmp_path):
    src = tmp_path / "head.json"
    src.write_text((ROOT / "head.json").read_text(encoding="utf-8"),
                   encoding="utf-8")
    out = write_spine(src)
    data = json.loads(out.read_text(encoding="utf-8"))
    # 4 resolutions x 1 corpus node = 4 seeded connections
    assert len(data["spine"]["connections"]) == 4
    # every connection references a declared resolution
    res_names = {r["name"] for r in data["spine"]["resolutions"]}
    assert all(c["resolution"] in res_names
               for c in data["spine"]["connections"])
    # last_built stamped
    assert data["last_built"]


def test_validation_rejects_bad_grain(tmp_path):
    data = json.loads((ROOT / "head.json").read_text(encoding="utf-8"))
    data["spine"]["resolutions"][0]["grain"] = "bogus"
    with pytest.raises(Exception):
        Head(data).validate()
