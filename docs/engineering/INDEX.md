---
version: "1.0.0"
schema_version: 2
title: "Engineering"
doc_type: index
parent: ../../INDEX.md
last_updated: 2026-08-19
last_audit: 2026-08-19
audit_status: current
domain: docs
triggers:
  - "llm grader engineering"
  - "llm grader architecture"
  - "llm grader tests"
---
# Engineering

**This section owns how the tool is built, what it can observe, and how correctness is proven.** The behavior it implements is specified in [design/](../design/INDEX.md); the constraints it must never violate are in [product/privacy-contract.md](../product/privacy-contract.md).

| Doc | Answers |
|---|---|
| [architecture.md](./architecture.md) | What are the moving parts and how does data flow? |
| [transcript-observables.md](./transcript-observables.md) | What can actually be read from a session transcript, and how reliably? |
| [testing.md](./testing.md) | What is proven, and how do I add to it? |

## Shape of the thing

One Python file, no third-party runtime dependencies for grading, no network calls, no persistent state. A session transcript goes in; an ANSI card and optionally an HTML card come out. Everything else in this repo is documentation or tests.
