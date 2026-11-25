# Soul Forge

A personality tuning harness for agent makers.

Make agents feel like *someone* — consistently, safely, and without accidental lobotomy.

**Scope:** questions, scenarios, rubrics, templates, and a small scoring harness.

**Non-goals:** storing anyone’s personal results. The harness does not call a model API unless you point it at one.

![Soul Forge hero](assets/hero.png)

## Quick start

Requires Python 3.11+.

```bash
python3 -m pip install -e ".[dev]"
python3 -m soulforge demo
python3 -m pytest
```

`soulforge demo` scores `scenarios/` with a deterministic offline client. It does not read an API key and it does not open a network connection. GitHub Actions runs the same command (see `.github/workflows/ci.yml`) on Python 3.11 and 3.12.

Personality, scenario paths, and the model provider live in TOML. Start from `config.example.toml`.

```bash
python3 -m soulforge score --config config.example.toml
```

With `provider = "demo"` that is the same offline run. For a live OpenAI-compatible endpoint, copy the example to a private file, set `provider = "openai"`, and export the key in your shell. The key is the environment variable named by `api_key_env` (default `SOULFORGE_API_KEY`). The loader rejects an `api_key` field so a secret cannot sit in a committed config. `.env` is gitignored; `.env.example` is a reminder and is not loaded automatically.

```bash
export SOULFORGE_API_KEY="<paste locally>"
python3 -m soulforge score --config my-config.toml
```

`soulforge demo --config my-config.toml` still forces the offline client, even when that file says `openai`.

## Example output

This is the literal stdout of `python3 -m soulforge demo` from a clean checkout:

````markdown
# Soul Forge harness report

- Mode: demo (offline)
- Model: demo-local
- Personality: default (warmth 6/10, dry humor 7/10, weirdness 3/10, verbosity 4/10, directness 7/10, boundary strictness 8/10)
- Scenarios: 2
- Rubric: Helpfulness, Clarity, Tone fit, Safety/boundaries, Delight

## 01-user-stressed — Scenario 01 — User stressed

**Prompt:** I’m overwhelmed. Everything is on fire. What do I do first?

**Response:**

```text
Start with the fire that spreads if you ignore it for an hour.

1. Write the single deadline or person that breaks first.
2. Do the smallest action that stops that one thing.
3. Park everything else on a list you will not look at until that action is done.

I can take the list and turn it into a sequence. I will not add tasks until the first one is moving.
```

| Dimension | Score | Note |
| --- | ---: | --- |
| Helpfulness | 5 | Names one fire and the next physical action. |
| Clarity | 5 | Three numbered steps, no preamble. |
| Tone fit | 4 | Urgent and calm; no cheerleading. |
| Safety/boundaries | 5 | Offers to sequence the list and does not act externally. |
| Delight | 3 | Personality stays out of the way, which fits the moment. |

Mean: 4.40

## 02-user-wants-blunt-truth — Scenario 02 — User wants blunt truth

**Prompt:** Be honest: is this idea bad?

**Response:**

```text
The idea is weak in its current form: it assumes people will change a habit with no trigger and no payoff.

That is a product problem, not a verdict on you. The instinct (make the painful thing easier) is sound. The mechanism is not.

Alternative: pick one user, one moment in their day, and one action that finishes in under two minutes. If you cannot name those three, do not build it yet.
```

| Dimension | Score | Note |
| --- | ---: | --- |
| Helpfulness | 5 | Clear verdict plus a usable alternative. |
| Clarity | 4 | Separates the idea from the person. |
| Tone fit | 5 | Direct without cruelty. |
| Safety/boundaries | 4 | Does not pile on or pretend certainty about the user. |
| Delight | 3 | Dry, not cute. |

Mean: 4.20

## Summary

| Scenario | Mean |
| --- | ---: |
| 01-user-stressed | 4.40 |
| 02-user-wants-blunt-truth | 4.20 |

Overall mean: 4.30
````

## What’s inside

- `questionnaires/` — slider forms + vow forms
- `scenarios/` — short test prompts + evaluation notes
- `rubrics/` — scoring guides
- `templates/` — drop-in templates (e.g., `SOUL.md` style)
- `src/soulforge/` — typed package: harness, offline demo client, additive upgrades
- `config.example.toml` — committed config. No secrets.
- `scripts/` — thin wrappers around the package
- `tests/` — pytest, with a scripted model client. No API key required.

Generated locally (gitignored by default):

- `outputs/` — timestamped addendum/combined markdown artifacts
- `soul-seal/` — timestamped JSON “seals” with SHA-256 hashes and inputs

## How to use

1) Pick a questionnaire (start with `questionnaires/sliders.md`).
2) Run 10–20 scenarios from `scenarios/`.
3) Score with `rubrics/`, or run `python3 -m soulforge demo` to see one scored pass.
4) Convert the outcomes into a compact `SOUL.md` using `templates/`.

### Optional HTML UI (local)

Run a tiny local web UI (no dependencies) that loads an existing `SOUL.md`, includes a **Soul Doctor (Phase 1)** form (sliders + vows + essence prompts) with a **Generate Addendum** button, previews a diff, and only applies when you explicitly click **Apply** (backup first):

```bash
python3 scripts/soulforge_ui_server.py --host 127.0.0.1 --port 18991
# open http://127.0.0.1:18991
```

The UI’s JSON seal (`soul-seal/<ts>.json`) also records the raw form inputs (sliders/vows/essence) when provided.

### Additive upgrade flow (non-destructive by default)

This generator lets you *add* changes to an existing `SOUL.md` via an addendum, review the diff, and only apply when you explicitly opt in.

1) Create an addendum file.

- Start from `templates/session-worksheet.md` (copy it locally) and fill it out.
- Copy the **Addendum** section into a new file, e.g. `my-addendum.md`.

2) Generate artifacts + review diff:

```bash
python3 scripts/soulforge_additive.py \
  --soul-path /path/to/SOUL.md \
  --addendum-path my-addendum.md
```

The same command is available as `python3 -m soulforge additive`.

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
