# Soul Forge

A personality tuning harness for agent makers.

Make agents feel like *someone* — consistently, safely, and without accidental lobotomy.

**Scope:** questions, scenarios, rubrics, and templates.

**Non-goals:** storing anyone’s personal results.

![Soul Forge hero](assets/hero.png)

## What’s inside

- `questionnaires/` — slider forms + vow forms
- `scenarios/` — short test prompts + evaluation notes
- `rubrics/` — scoring guides
- `templates/` — drop-in templates (e.g., `SOUL.md` style)
- `scripts/` — small helper CLIs

Generated locally (gitignored by default):

- `outputs/` — timestamped addendum/combined markdown artifacts
- `soul-seal/` — timestamped JSON “seals” with SHA-256 hashes and inputs

## How to use

1) Pick a questionnaire (start with `questionnaires/sliders.md`).
2) Run 10–20 scenarios from `scenarios/`.
3) Score with `rubrics/`.
4) Convert the outcomes into a compact `SOUL.md` using `templates/`.

### Additive upgrade flow (non-destructive by default)

### Optional HTML UI (local)

Run a tiny local web UI (no dependencies) that loads an existing `SOUL.md`, includes a **Soul Doctor (Phase 1)** form (sliders + vows + essence prompts) with a **Generate Addendum** button, previews a diff, and only applies when you explicitly click **Apply** (backup first):

```bash
python3 scripts/soulforge_ui_server.py --host 127.0.0.1 --port 18991
# open http://127.0.0.1:18991
```

This repo includes a tiny generator that lets you *add* changes to an existing `SOUL.md` via an addendum, review the diff, and only apply when you explicitly opt in.

The UI’s JSON seal (`soul-seal/<ts>.json`) also records the raw form inputs (sliders/vows/essence) when provided.

1) Create an addendum file.

- Start from `templates/session-worksheet.md` (copy it locally) and fill it out.
- Copy the **Addendum** section into a new file, e.g. `my-addendum.md`.

2) Generate artifacts + review diff:

```bash
python3 scripts/soulforge_additive.py \
  --soul-path /path/to/SOUL.md \
  --addendum-path my-addendum.md
```

This will create:

- `outputs/SOUL.ADDENDUM.<ts>.md`
- `outputs/SOUL.COMBINED.<ts>.md`
- `soul-seal/<ts>.json` (hashes for base/addendum/combined + inputs)

…and it prints a unified diff between the base and the combined output.

3) Apply (overwrites only with explicit flag; makes a backup first):

```bash
python3 scripts/soulforge_additive.py \
  --soul-path /path/to/SOUL.md \
  --addendum-path my-addendum.md \
  --apply
```

When applying, it writes `SOUL.backup.<ts>.md` next to `SOUL.md` before overwriting.

This repo is intentionally markdown-first so it’s easy to fork.
