---
type: discovery
status: active
title: Vault Health Validator & Wikilink Stem Resolution
created: 2026-08-07
updated: 2026-08-07
tags:
  - discovery
  - validation
  - gotcha
---

# Vault Health Validator & Wikilink Stem Resolution

## Context
Automating memory vault verification requires validating wikilinks, registry entries, and orphan notes without relying on external dependencies or running an Obsidian process.

## Finding
> [!important] Wikilink Stem Resolution Rule
> The stdlib script `scripts/vault-health.py` parses wikilinks using regex `\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]` and normalizes the target by stripping trailing `.md` and taking `Path(target).stem`.

### Key Validation Behaviors:
1. **Stem Matching**: A link like `[[decisions/2026-08-07-adopt-agentskills-io-spec]]` resolves to stem `2026-08-07-adopt-agentskills-io-spec`, matching file `decisions/2026-08-07-adopt-agentskills-io-spec.md`.
2. **Registry Verification**: Every relative path specified under `path:` in `registry.yaml` must exist on disk.
3. **Orphan Note Warnings**: Notes with 0 incoming wikilinks (except `INDEX`, `project-state`, and `registry`) trigger orphan warnings.
4. **Dead Link Errors**: Unresolvable targets trigger dead wikilink errors.

## Solution & Recommendations
Always maintain incoming links from `INDEX.md` or `project-state.md` to every decision, discovery, and session log note to guarantee 0 errors and 0 warnings during health checks.

## Related Notes
- [[architecture]]
- [[decisions/2026-08-07-adopt-agentskills-io-spec]]
- [[project-state]]
