# Contributing

Soul Forge is a markdown-first personality tuning harness for agent makers.

## Principles

- No personal results in-repo.
- Prefer small, composable questionnaires and scenarios.
- Keep the default workflow non-destructive.

## How to contribute

- Add scenarios under `scenarios/` with:
  - a short prompt
  - what good looks like (bullets)
  - optional failure modes
- Improve rubrics under `rubrics/`.
- Keep UI changes dependency-free where possible.

## Safety

Do not add code that auto-executes shell commands based on untrusted input.
