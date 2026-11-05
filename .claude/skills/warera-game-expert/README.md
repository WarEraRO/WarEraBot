# warera-game-expert — maintainer notes

A Claude Agent Skill that makes Claude a WarEra domain expert: mechanics, formulas, Romanian strategy/policy (kept separate),
version history, and calculators for reasoning over live game data. Entry point: [SKILL.md](SKILL.md).

## Layout

```
SKILL.md                    trigger description, authority model, routing, reasoning rules (keep it short)
references/                 one domain per file; loaded on demand (progressive disclosure)
  formulas.md               every sourced formula with exactness and version
  scenarios.md              reusable decision patterns (S1-S25)
  data-model.md             normalized state schema for scripts/API data
  versioned-mechanics.md    registry schema, resolution rules, known history
  unresolved-mechanics.md   conflicts, gaps, approximations (verification queue)
  update-process.md         how to ingest patches without losing history
  source-map.md             provenance: guide chapter -> file, live cross-check
  evaluation.md             20 acceptance questions + regression commands
data/
  mechanics.yaml            versioned registry of volatile values (single source of truth)
  patch-history.yaml        dated patch EVENT LOG (v0.0.2 .. v0.17.7 from the wiki, plus admin-article entries with their own `source`) - history, not rules
  military-ranks.yaml       rank table (wiki-only)
  recipes.yaml cooldowns.yaml combat-bonuses.yaml progression-values.yaml (incl. XP table) equipment.yaml
  snapshot-schema.yaml      entity/field schema for validate_game_snapshot.py
scripts/                    deterministic helpers (Python 3.9+, PyYAML optional - a subset parser is bundled)
```

## Maintenance rules

1. Volatile numbers live in `data/mechanics.yaml`; prose should cite the mechanic ID and avoid duplicating many numbers.
2. Never overwrite history — follow [references/update-process.md](references/update-process.md).
3. Keep authority labels (`[RULE]`, `[STRAT-RO]`, `[POLICY-RO]`, `[OBS]`, `[CONFLICT]`, `[GAP]`) on every new statement.
4. After any data edit run:
   ```
   python scripts/validate_mechanics.py
   python scripts/combat_bonus_calculator.py --selftest
   ```
5. If PyYAML is not installed, keep YAML inside the supported subset (block maps/lists, flow `[..]`/`{..}`, single-line quoted
   strings, `#` comments; no anchors or multi-line scalars). `wlib.MiniYaml` was cross-checked against PyYAML on all data files.
6. Add a CHANGELOG entry for every change.

## Relationship to sibling skills

- `warera-config` holds the live `gameConfig` snapshot and drift check — when it reports drift, run the update process here.
- `warera-api` documents the API used to build snapshots matching [references/data-model.md](references/data-model.md).

## Source rules

warera.wiki is **outdated** (owner's instruction, confirmed by cross-check): use it only to fill gaps, keep a wiki fact only if the
live config (warera-config / warera.realmarijn.nl) or the guide agrees, and otherwise label it `[WIKI-ONLY]`. Re-run
`python ../warera-config/scripts/check_config.py` before relying on config-backed values.

## Known limits

Damage per hit is an estimate (crit rule wiki-only, multiplier stacking inferred); the rank table, case rarity split and paper
formulas are wiki-only; elite-case drops and per-law paper costs are unknown. No patch notes exist between v0.17.7 and v0.26.1. See [references/unresolved-mechanics.md](references/unresolved-mechanics.md).
