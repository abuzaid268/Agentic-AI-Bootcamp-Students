# The five demo skills — where they came from

Vendored on 2026-09-12 so Part 1 works offline and nobody depends on a repo
staying up mid-session. All five are permissively licensed (MIT / Apache-2.0).
No GPL. Read `README.md` for how to teach them; this file is only provenance.

| # | folder | upstream | license | fetched |
|:-:|---|---|---|---|
| 1 | `1-file-organizer/` | `ComposioHQ/awesome-claude-skills` → `file-organizer/` | Apache-2.0 (repo) | full |
| 2 | `2-canvas-design/` | `ComposioHQ/awesome-claude-skills` → `canvas-design/` | Apache-2.0 (`LICENSE.txt`) | full, incl. 5.5 MB `canvas-fonts/` |
| 3 | `3-artifacts-builder/` | `ComposioHQ/awesome-claude-skills` → `artifacts-builder/` | Apache-2.0 (`LICENSE.txt`) | full, incl. `scripts/` |
| 4 | `4-ui-ux-pro-max/` | `nextlevelbuilder/ui-ux-pro-max-skill` → `.claude/skills/ui-ux-pro-max/` | MIT | the skill only, not the 29 MB repo |
| 5 | `5-open-slide/` | `1weiho/open-slide` → `packages/core/skills/` | MIT | the 5 bundled skills only, not the monorepo |

## To make 1–4 fire in Claude Code

```bash
mkdir -p ~/.claude/skills
cp -r 1-file-organizer     ~/.claude/skills/file-organizer
cp -r 2-canvas-design      ~/.claude/skills/canvas-design
cp -r 3-artifacts-builder  ~/.claude/skills/artifacts-builder
cp -r 4-ui-ux-pro-max      ~/.claude/skills/ui-ux-pro-max
```

Demo 5 is not installed this way — it ships with its own scaffold:

```bash
npx @open-slide/cli init my-slide && cd my-slide && pnpm dev
```

`5-open-slide/` here is the five `SKILL.md` files, for reading on screen when
the live scaffold is not worth the risk.

## Verified counts for demo 4

From `4-ui-ux-pro-max/data/catalog-summary.json`, `verifiedAt: 2026-08-26`,
skill v2.13.0 — quote these rather than the older numbers:

| item | count |
|---|---|
| product palettes | 192 |
| reasoning profiles | 192 |
| UX guidelines | 119 |
| searchable styles | 79 (50 active, of 88 total) |
| font pairings | 74 |
| stacks | 22 (1,260 stack guidelines) |
| chart types | 25 |
| curated icons | 105 |

The `192` in the older notes is the **palettes and reasoning profiles**, not the
UX rules. The rule count is **119**. Both make the point; only one is true.

## Re-fetching

```bash
git clone --depth 1 https://github.com/ComposioHQ/awesome-claude-skills
git clone --depth 1 https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
git clone --depth 1 https://github.com/1weiho/open-slide
```
