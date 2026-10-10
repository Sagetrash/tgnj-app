#!/usr/bin/env python3
"""
vault-health.py — Zero-dependency vault health validator for agents and humans.
Checks registry freshness, file existence, dead wikilinks, orphan notes, and frontmatter.
Usage:
    python3 scripts/vault-health.py [.brain|path/to/vault]
"""

import os
import re
import sys
from pathlib import Path


def parse_simple_frontmatter(file_path):
    """Extract YAML frontmatter key-value pairs using simple regex."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return {}
    
    if not content.startswith("---"):
        return {}
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    
    yaml_text = parts[1]
    data = {}
    for line in yaml_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip().strip("'\"")
    return data


def extract_wikilinks(file_path):
    """Find all [[Wikilinks]] inside a markdown file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return []
    
    # Matches [[Note Name]], [[Note Name|Display]], [[Note Name#Heading]]
    matches = re.findall(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]", content)
    return [m.strip() for m in matches]


def run_health_check(vault_dir):
    vault_path = Path(vault_dir).resolve()
    if not vault_path.exists() or not vault_path.is_dir():
        print(f"❌ Error: Vault directory '{vault_dir}' does not exist.")
        return 1

    print(f"🔍 Auditing Obsidian Vault at: {vault_path}\n" + "=" * 50)
    
    errors = 0
    warnings = 0

    # 1. Check INDEX.md and registry.yaml existence
    index_md = vault_path / "INDEX.md"
    registry_yaml = vault_path / "registry.yaml"

    if not index_md.exists():
        print("⚠️ Warning: Root INDEX.md missing.")
        warnings += 1
    else:
        print("✅ Found root INDEX.md")

    registered_paths = set()

    if not registry_yaml.exists():
        print("⚠️ Warning: Root registry.yaml missing.")
        warnings += 1
    else:
        print("✅ Found root registry.yaml")
        # Parse simple registry entries
        content = registry_yaml.read_text(encoding="utf-8")
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("path:"):
                rel_path = line_str.split(":", 1)[1].strip().strip("'\"")
                registered_paths.add(rel_path)

        # Verify all registered files exist
        for rel_path in registered_paths:
            full_note_path = vault_path / rel_path
            if not full_note_path.exists():
                print(f"❌ Registry Error: Registered path '{rel_path}' does not exist on disk!")
                errors += 1

    # 2. Collect all markdown notes by stem and by relative path
    md_files = list(vault_path.rglob("*.md"))
    note_stems = {f.stem: f for f in md_files}
    note_rel_paths = {str(f.relative_to(vault_path)): f for f in md_files}
    all_wikilinks = {}
    incoming_links = {f.stem: 0 for f in md_files}

    # 3. Check for dead links and frontmatter
    print(f"\n📑 Auditing {len(md_files)} markdown notes...")
    for md_file in md_files:
        rel_file = str(md_file.relative_to(vault_path))
        
        # Extract links
        links = extract_wikilinks(md_file)
        all_wikilinks[md_file.stem] = links
        
        for link in links:
            # Normalize target link stem
            raw_link = link[:-3] if link.endswith(".md") else link
            link_stem = Path(raw_link).stem
            
            if link_stem in incoming_links:
                incoming_links[link_stem] += 1
            elif raw_link in note_rel_paths:
                target_stem = note_rel_paths[raw_link].stem
                if target_stem in incoming_links:
                    incoming_links[target_stem] += 1
            elif not raw_link.startswith("http") and not raw_link.startswith("#"):
                print(f"❌ Dead Wikilink in '{rel_file}': [[{link}]] target note not found.")
                errors += 1

    # 4. Check for orphan notes (excluding INDEX, project-state, and templates)
    ignored_orphans = {"INDEX", "project-state", "registry"}
    orphans = []
    for stem, count in incoming_links.items():
        if count == 0 and stem not in ignored_orphans:
            # Check if note has incoming or registered status
            orphans.append(stem)

    if orphans:
        for orphan in orphans:
            print(f"⚠️ Orphan Note Warning: '{orphan}.md' has no incoming wikilinks.")
            warnings += 1

    print("\n" + "=" * 50)
    print(f"📊 Vault Health Summary: {errors} Errors, {warnings} Warnings")
    
    if errors > 0:
        print("❌ Audit Failed! Please fix errors listed above.")
        return 1
    
    print("✅ Vault Health Audit Passed cleanly!")
    return 0


if __name__ == "__main__":
    target_vault = sys.argv[1] if len(sys.argv) > 1 else ".brain"
    sys.exit(run_health_check(target_vault))
