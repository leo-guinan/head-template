# head-template

A **head** is a mind-node: a photo plus a link to a person's searchable
**corpus** (the "body" of work) and a **spine** — the connection manifest
built by searching that corpus at multiple resolutions.

The head is the mind. The corpus is the body. The spine is built up from
the collective search space of the body, so you can attach things to the
mind at any resolution: coarse (whole corpus) → medium (project/topic) →
fine (idea) → atom (single claim).

## Use it

Clone this template per person:

```bash
git clone --bare https://github.com/leo-guinan/head-template.git && \
  git clone https://github.com/leo-guinan/head-template.git defender-head && \
  cd defender-head
```

Then:
1. Edit `head.json` — set `id`, `name`, `aliases`, `bio`, `corpus`.
2. Replace `assets/headshot.svg` with a real headshot (keep the path or
   update `headshot` in head.json).
3. Run the spine builder:

```bash
python build_spine.py head.json
```

That seeds one evidence-backed connection per (resolution × corpus node)
and stamps `last_built`. Replace `probe_corpus` in `build_spine.py` with
live search (GitHub code search, a local index, an LLM over the export)
when you want the spine to actually crawl.

## Schema

`head.schema.json` is the contract. Required: `schema_version`, `id`,
`name`, `headshot`, `corpus`, `spine`. Corpus entries link to searchable
nodes; the spine carries `resolutions` (grain tiers) and `connections`
(evidence-backed links to other heads / projects / concepts).

## Layout

```
head.json            # the mind-node + corpus links + spine
head.schema.json     # schema contract
assets/headshot.svg  # the photo
build_spine.py       # spine assembler (deterministic, testable)
corpus.example.txt   # sample body-of-work pointer
tests/               # structure + build_spine tests
```
