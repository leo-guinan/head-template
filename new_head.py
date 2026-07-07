#!/usr/bin/env python3
"""new_head — launch a new 'head' repo from a source.

Sources for the headshot:
  twitter-archive  <path>   a local unzipped Twitter archive (reads profile image)
  substack         <url>    a Substack publication/profile URL (fetches avatar)
  gravatar         <email|hash>  gravatar by email or md5 hash
  local            <path>   a local image file (copied as-is)

The launcher:
  1. clones head-template,
  2. fetches the headshot from the chosen source into assets/,
  3. writes head.json (id, name, aliases, corpus -> the source + a body repo),
  4. builds the spine (build_spine),
  5. creates the head repo AND a paired body repo that connects to the source.

The body repo is the searchable 'body of work'; its corpus link points at
the origin source, and the head repo's corpus points at the body repo. That
is the spine: head -> body -> source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

TEMPLATE_REPO = "leo-guinan/head-template"
HEAD_REMOTE = "https://github.com/leo-guinan/{id}-head.git"
BODY_REMOTE = "https://github.com/leo-guinan/{id}-body.git"


# ─── headshot fetchers ──────────────────────────────────────────────────────

def fetch_twitter_archive(path: str, dest: Path) -> str:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"twitter-archive path not found: {path}")
    # Twitter archive: profile image referenced in data/account.js
    account_js = p / "data" / "account.js"
    avatar_url = None
    if account_js.exists():
        txt = account_js.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'"avatarMediaUrl"\s*:\s*"([^"]+)"', txt)
        if m:
            avatar_url = m.group(1)
    if avatar_url:
        return _download(avatar_url, dest)
    # fallback: any image under data/account-media
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        hits = sorted(p.glob(f"data/account-media/**/{ext}"),
                      key=lambda f: f.stat().st_size, reverse=True)
        if hits:
            return _copy_file(hits[0], dest)
    raise SystemExit("no profile image found in twitter archive")


def fetch_substack(url: str, dest: Path) -> str:
    html = _get_text(url)
    # Substack author avatar is in <meta property="og:image" ...> or
    # "avatarUrl":"..." in the embedded JSON.
    m = re.search(r'"avatarUrl"\s*:\s*"([^"]+)"', html)
    if not m:
        m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    if not m:
        m = re.search(r'"image"\s*:\s*"([^"]+\.(?:png|jpg|jpeg))"', html)
    if not m:
        raise SystemExit("could not find avatar URL on substack page")
    return _download(m.group(1), dest)


def fetch_gravatar(email_or_hash: str, dest: Path) -> str:
    if "@" in email_or_hash:
        h = hashlib.md5(email_or_hash.strip().lower().encode()).hexdigest()
    else:
        h = email_or_hash.strip().lower()
    # 200px, identicon fallback so we always get something
    url = f"https://www.gravatar.com/avatar/{h}?s=200&d=identicon"
    return _download(url, dest)


def fetch_local(path: str, dest: Path) -> str:
    src = Path(path)
    if not src.exists():
        raise SystemExit(f"local image not found: {path}")
    return _copy_file(src, dest)


def _download(url: str, dest: Path) -> str:
    # dest is a directory; write into dest/headshot.<ext>
    dest.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    m = re.search(r"\.(png|jpe?g|gif|webp)", url.split("?")[0])
    if m:
        ext = "." + m.group(1)
    out = dest / f"headshot{ext}"
    urllib.request.urlretrieve(url, out)
    return out.name


def _copy_file(src: Path, dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"headshot{src.suffix}"
    shutil.copy(src, out)
    return out.name


FETCHERS = {
    "twitter-archive": fetch_twitter_archive,
    "substack": fetch_substack,
    "gravatar": fetch_gravatar,
    "local": fetch_local,
}


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "head-launcher/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
        return r.read().decode("utf-8", errors="ignore")


# ─── repo scaffolding ────────────────────────────────────────────────────────

def clone_template(dest: Path) -> None:
    subprocess.run(
        ["git", "clone", "--quiet",
         f"https://github.com/{TEMPLATE_REPO}.git", str(dest)],
        check=True)


def write_head(head_dir: Path, *, id_: str, name: str, aliases: list[str],
               bio: str, headshot: str, source_kind: str, source_ref: str,
               body_url: str) -> None:
    data = {
        "schema_version": "1.0",
        "id": id_,
        "name": name,
        "aliases": aliases,
        "headshot": f"assets/{headshot}",
        "bio": bio,
        "corpus": [
            {
                "name": f"{name} body repo",
                "url": body_url,
                "type": "github",
                "search": f"{body_url}/search?q={{q}}&type=code",
            },
            {
                "name": f"source ({source_kind})",
                "url": source_ref,
                "type": source_kind if source_kind in ("github", "docs", "site", "rss", "supabase", "other") else "other",
                "search": "manual" if source_kind in ("twitter-archive", "local", "gravatar") else f"{source_ref}/search?q={{q}}",
            },
        ],
        "spine": {
            "resolutions": [
                {"name": "project", "grain": "coarse"},
                {"name": "topic", "grain": "medium"},
                {"name": "idea", "grain": "fine"},
                {"name": "claim", "grain": "atom"},
            ],
            "connections": [],
        },
        "last_built": "",
    }
    (head_dir / "head.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_body(body_dir: Path, *, id_: str, name: str, source_kind: str,
               source_ref: str) -> None:
    """The body repo is the searchable corpus. Its corpus points at the source."""
    body_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": "1.0",
        "id": f"{id_}-body",
        "name": f"{name} — body of work",
        "aliases": [],
        "headshot": "",
        "bio": f"Searchable body of work for {name}. Feeds the {id_}-head spine.",
        "corpus": [
            {
                "name": f"source ({source_kind})",
                "url": source_ref,
                "type": source_kind if source_kind in ("github", "docs", "site", "rss", "supabase", "other") else "other",
                "search": "manual" if source_kind in ("twitter-archive", "local", "gravatar") else f"{source_ref}/search?q={{q}}",
            }
        ],
        "spine": {
            "resolutions": [
                {"name": "project", "grain": "coarse"},
                {"name": "topic", "grain": "medium"},
                {"name": "idea", "grain": "fine"},
                {"name": "claim", "grain": "atom"},
            ],
            "connections": [],
        },
        "last_built": "",
    }
    (body_dir / "head.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (body_dir / "README.md").write_text(
        f"# {name} — body of work\n\n"
        f"Searchable corpus for the `{id_}-head` mind-node.\n"
        f"Source: {source_kind} → {source_ref}\n\n"
        f"Run `python build_spine.py head.json` to refresh the spine.\n",
        encoding="utf-8")


def build_spine(head_dir: Path) -> None:
    sys.path.insert(0, str(head_dir))
    import build_spine as bs  # noqa: E402
    bs.write_spine(head_dir / "head.json")


def create_repo(local_dir: Path, remote_url: str, public: bool = True) -> None:
    subprocess.run(["git", "-C", str(local_dir), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(local_dir), "commit", "-q",
                    "-m", "Initial head/body scaffold"], check=True)
    visibility = "--public" if public else "--private"
    # gh repo create with --source pushes too; if remote already set, push.
    r = subprocess.run(
        ["gh", "repo", "create", remote_url.split("/")[-1].replace(".git", ""),
         visibility, "--source", str(local_dir), "--remote", "origin", "--push"],
        capture_output=True, text=True)
    if r.returncode != 0:
        # remote may already exist from a prior set-url; just push.
        subprocess.run(["git", "-C", str(local_dir), "push", "-q", "origin", "main"],
                       check=True)


# ─── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Launch a new head repo (+ body repo).")
    ap.add_argument("--id", required=True, help="slug, e.g. defender")
    ap.add_argument("--name", required=True, help="display name / pseudonym")
    ap.add_argument("--aliases", nargs="*", default=[], help="alt identities")
    ap.add_argument("--bio", default="", help="one or two sentences")
    ap.add_argument("--source", required=True,
                    choices=list(FETCHERS),
                    help="headshot source")
    ap.add_argument("--source-ref", required=True,
                    help="path/url/email for the source")
    ap.add_argument("--out", default=".", help="parent dir for the new repos")
    ap.add_argument("--no-push", action="store_true",
                    help="scaffold locally; do not create GitHub repos")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    head_dir = out / f"{args.id}-head"
    body_dir = out / f"{args.id}-body"

    # 1. headshot -> stage in a temp file first (don't create head_dir yet,
    #    git clone needs an empty/non-existent target dir)
    staging = out / f".{args.id}-headshot-staging"
    staging.parent.mkdir(parents=True, exist_ok=True)
    headshot = FETCHERS[args.source](args.source_ref, staging)

    # 2. clone template into head dir
    clone_template(head_dir)

    # 3. move staged headshot into head_dir/assets/
    head_dir.joinpath("assets").mkdir(parents=True, exist_ok=True)
    final_shot = head_dir / "assets" / headshot
    shutil.move(str(staging / headshot), str(final_shot))
    headshot = final_shot.name

    # 4. write head.json (corpus -> body repo + source)
    body_url = BODY_REMOTE.format(id=args.id).replace(".git", "")
    write_head(head_dir, id_=args.id, name=args.name, aliases=args.aliases,
               bio=args.bio, headshot=headshot, source_kind=args.source,
               source_ref=args.source_ref, body_url=body_url)

    # 5. body repo (corpus -> source)
    write_body(body_dir, id_=args.id, name=args.name,
               source_kind=args.source, source_ref=args.source_ref)

    # 6. spine
    build_spine(head_dir)

    print(f"head: {head_dir} (headshot: {headshot})")
    print(f"body: {body_dir} (source: {args.source} -> {args.source_ref})")

    if args.no_push:
        print("(--no-push: not creating GitHub repos)")
        return 0

    create_repo(head_dir, HEAD_REMOTE.format(id=args.id))
    create_repo(body_dir, BODY_REMOTE.format(id=args.id))
    print(f"created: {HEAD_REMOTE.format(id=args.id)} and {BODY_REMOTE.format(id=args.id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
