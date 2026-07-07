"""build_spine — assemble a head's connection manifest (the 'spine').

The spine is built from the *collective search space* of the corpus (the
'body' of work). For each resolution tier, we emit a set of search-backed
connection stubs pointing at the corpus, so the mind can be explored at
coarse (whole-of-corpus) down to atom (single claim) resolution.

This template version is corpus-agnostic: it validates head.json, expands
each corpus node's search template, and emits a spine skeleton with one
connection per (resolution x corpus-node) pair as a starting search. A
real deployment swaps `probe_corpus` for live search (GitHub code search,
a local index, an LLM over the export, etc.).
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEAD_FIELDS = {"schema_version", "id", "name", "aliases", "headshot",
               "bio", "corpus", "spine", "last_built"}
RES_GRAINS = {"coarse", "medium", "fine", "atom"}


@dataclass
class ValidationError(Exception):
    pass


@dataclass
class Head:
    data: dict[str, Any]

    def validate(self) -> None:
        for req in ("schema_version", "id", "name", "headshot", "corpus", "spine"):
            if req not in self.data:
                raise ValidationError(f"missing required field: {req}")
        if self.data["schema_version"] != "1.0":
            raise ValidationError("schema_version must be '1.0'")
        if not isinstance(self.data["corpus"], list) or not self.data["corpus"]:
            raise ValidationError("corpus must be a non-empty array")
        for c in self.data["corpus"]:
            for k in ("name", "url", "search"):
                if k not in c:
                    raise ValidationError(f"corpus entry missing '{k}': {c}")
        spine = self.data["spine"]
        if "resolutions" not in spine or "connections" not in spine:
            raise ValidationError("spine needs resolutions + connections")
        for r in spine["resolutions"]:
            if r.get("grain") not in RES_GRAINS:
                raise ValidationError(f"bad resolution grain: {r}")
        res_names = {r["name"] for r in spine["resolutions"]}
        for conn in spine["connections"]:
            if conn.get("resolution") not in res_names:
                raise ValidationError(
                    f"connection resolution '{conn.get('resolution')}' "
                    f"not declared in spine.resolutions")

    @property
    def id(self) -> str:
        return self.data["id"]


def expand_search(template: str, query: str) -> str:
    """Fill a corpus search template with a query string."""
    if "{q}" not in template:
        return template
    return template.replace("{q}", urllib.parse.quote_plus(query))


def probe_corpus(node: dict, query: str) -> dict:
    """Stub probe. Real impl searches the corpus node (live search/CLI/LLM).

    Returns a connection-style dict with evidence links so the spine is
    navigable even before live search is wired.
    """
    url = expand_search(node.get("search", node["url"]), query)
    return {
        "label": f"{query} @ {node['name']}",
        "resolution": query,  # replaced by caller per-resolution
        "target": node["url"],
        "evidence": [url],
    }


def build_spine(head_path: str | Path, seed_queries: list[str] | None = None
                ) -> dict:
    """Build / refresh the spine for a head. Returns updated head data."""
    head_path = Path(head_path)
    data = json.loads(head_path.read_text(encoding="utf-8"))
    head = Head(data)
    head.validate()

    seed_queries = seed_queries or [r["name"] for r in data["spine"]["resolutions"]]
    connections: list[dict] = list(data["spine"].get("connections", []))

    # Seed one evidence-backed connection per (resolution x corpus node).
    for res in data["spine"]["resolutions"]:
        for node in data["corpus"]:
            q = res["name"]
            probe = probe_corpus(node, q)
            probe["resolution"] = res["name"]
            probe["label"] = f"{res['name']}: {node['name']}"
            # Avoid duplicate (label, target) seeding.
            if not any(c.get("label") == probe["label"]
                       and c.get("target") == probe["target"]
                       for c in connections):
                connections.append(probe)

    data["spine"]["connections"] = connections
    data["last_built"] = datetime.now(timezone.utc).isoformat()
    return data


def write_spine(head_path: str | Path, seed_queries: list[str] | None = None) -> Path:
    data = build_spine(head_path, seed_queries)
    head_path = Path(head_path)
    head_path.write_text(json.dumps(data, indent=2, ensure_ascii=False)
                         + "\n", encoding="utf-8")
    return head_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Build a head's spine.")
    ap.add_argument("head", nargs="?", default="head.json")
    ap.add_argument("--seed", nargs="*", default=None)
    args = ap.parse_args()
    write_spine(args.head, args.seed)
    print(f"spine written: {args.head}")
