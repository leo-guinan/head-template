from __future__ import annotations
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import new_head  # noqa: E402


def _make_local_image(path: Path) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


def test_new_head_local_source(tmp_path, monkeypatch):
    # avoid any real git clone / gh by monkeypatching the network bits
    monkeypatch.setattr(new_head, "clone_template",
                        lambda dest: (dest.mkdir(parents=True, exist_ok=True),
                                      (dest / "head.json").write_text("{}"),
                                      (dest / "assets").mkdir(parents=True, exist_ok=True)))
    monkeypatch.setattr(new_head, "create_repo", lambda *a, **k: None)

    img = tmp_path / "src.png"
    _make_local_image(img)
    out = tmp_path / "out"

    # run the pipeline logic directly (no-push path, no git)
    head_dir = out / "testperson-head"
    body_dir = out / "testperson-body"
    staging = out / ".testperson-headshot-staging"
    staging.mkdir(parents=True, exist_ok=True)
    headshot = new_head.fetch_local(str(img), staging)
    head_dir.mkdir(parents=True, exist_ok=True)
    head_dir.joinpath("assets").mkdir(parents=True, exist_ok=True)
    shutil.move(str(staging / headshot), str(head_dir / "assets" / headshot))
    body_url = "https://github.com/leo-guinan/testperson-body"
    new_head.write_head(head_dir, id_="testperson", name="Test Person",
                        aliases=["tp"], bio="x", headshot=headshot,
                        source_kind="local", source_ref=str(img), body_url=body_url)
    new_head.write_body(body_dir, id_="testperson", name="Test Person",
                        source_kind="local", source_ref=str(img))
    new_head.build_spine(head_dir)

    head = json.loads((head_dir / "head.json").read_text())
    body = json.loads((body_dir / "head.json").read_text())
    # headshot landed in the right place
    assert (head_dir / "assets" / headshot).exists()
    # head corpus connects to body repo + the source
    kinds = {c["type"] for c in head["corpus"]}
    assert "github" in kinds  # body repo
    assert any(c["url"] == str(img) for c in head["corpus"])
    # body corpus points at the source
    assert any(c["url"] == str(img) for c in body["corpus"])
    # spine seeded
    assert len(head["spine"]["connections"]) == len(head["spine"]["resolutions"]) * len(head["corpus"])
