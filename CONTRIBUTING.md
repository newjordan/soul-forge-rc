# Contributing

Soul Forge is a markdown-first personality tuning harness for agent makers.

## Principles

- No personal results in-repo.
- Prefer small, composable questionnaires and scenarios.
- Keep the default workflow non-destructive.

## Development

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m soulforge demo
```

`soulforge demo` and the test suite do not need an API key. Live scoring reads `SOULFORGE_API_KEY` (or the variable named by `api_key_env`) from the environment. Do not commit `.env` files, and do not put keys in `config.example.toml`. The config loader rejects an inline key field.

## How to contribute

- Add scenarios under `scenarios/` with:
  - a short prompt
  - what good looks like (bullets)
  - optional failure modes
- Improve rubrics under `rubrics/`.
- Keep UI changes dependency-free where possible.

## Safety

Do not add code that auto-executes shell commands based on untrusted input.
