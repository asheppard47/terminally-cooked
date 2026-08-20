---
version: "1.0.0"
schema_version: 2
title: "Art — Badge Visual System"
doc_type: index
parent: ../../INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "llm grader art"
  - "badge art"
  - "badge style guide"
---
# Art — Badge Visual System

**This section owns how badges look and how they are produced: the style rules that make 24 images read as one collectible series, the pipeline that guarantees uniform output, and the protocol that decides which render ships.**

| Doc | Answers |
|---|---|
| [style-guide.md](./style-guide.md) | What does a badge look like, and what is forbidden? |
| [production-pipeline.md](./production-pipeline.md) | How is a badge generated, checked, graded, and exported? |
| [voting-protocol.md](./voting-protocol.md) | How is the winning render chosen, by whom? |

## The short version

Painterly splash art with luminous, saturated color; one central subject with a strong silhouette; absolutely no text in the image; one declared focus mode and one canonical direction per badge; square 1024 px masters with 72 px and 32 px derivatives. Names are drawn by the card renderer, not painted.

## Asset location

Masters, derivatives, prompts, comparison composites and pipeline scripts live on the Mini scratch volume at `/Volumes/WD Black (2TB)/Game Dev/scratch/llm-grader/badge-art/` per the workshop storage rule. Only the winning derivatives are promoted into this repo once the vote closes.
