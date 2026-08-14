# Project SHION brand asset audit — 2026-08-14

## Scope

The current repository, all reachable Git refs and deleted-file history were
searched for `logo`, `icon`, `brand`, `mark`, `emblem`, `symbol`, `favicon`,
`shion_logo` and `project_shion`. README references, `assets/`, `docs/`, legacy
paths represented in Git history and the current Character manifest were checked.
The safely named local roots `C:\Users\PC\Documents\ChatGPT\Project_SHION` and
`D:\AI\Project_SHION` were also searched by filename without opening private
runtime data; they produced no logo/favicon candidate.

## Result

No concrete Owner-approved **Project SHION brand logo** or derived favicon was
found in the current tree or reachable Git history. The repository documents the
requirements for such a logo in `docs/character/brand_assets.md` and
`docs/character/official_design_guide.md`, but those documents are specifications,
not image assets. The earlier documentation audit reached the same conclusion.

`app/static/assets/shion/avatar.svg` is a fallback SHION character mark, not a
Project SHION logo. It must not be promoted to the Project brand or favicon.

The following Owner-approved files are Character assets, not Project logo
candidates:

| Path | Format and dimensions | Intended use |
| --- | --- | --- |
| `app/static/assets/characters/shion/official/static_2d/shion_avatar.png` | RGBA PNG, 1254×1254 | Chat, header, future Character selector |
| `app/static/assets/characters/shion/official/static_2d/shion_panel.png` | RGBA PNG, 1024×1536 | Character presence panel |
| `app/static/assets/characters/shion/official/static_2d/shion_official_2d_master.png` | RGBA PNG, 1024×1536 | Characters page, SHION Room, design reference |

## UX decision

Workspace brand presentation uses a neutral typographic `PS` placeholder clearly
marked `logo pending`. SHION's face remains in Character/Chat surfaces. No favicon
is added, because deriving one from a Character face would violate the requested
brand separation. The Floating Assistant includes a small non-official presence
symbol as a UI affordance; it is not registered as an official brand asset.

## Owner Gate

**PROJECT SHION LOGO REQUIRED.** Owner approval is required before adding a brand
logo, creating a derived favicon or registering a Companion-specific official icon.
Multiple future candidates must be reviewed rather than silently promoted.
