# Project conventions

Keep documents in `docs/`, executable tools in `scripts/` (except the entry points `setup_env.sh`, `start_site.sh` and `delete_site.sh`, which stay at the project root and source `scripts/project_env.sh`), source and normalized datasets in `data/`, configuration in `config/`, tests in `tests/`, the website (source and active data) in `public/`, notice builds in `lh-runs/` (committed), the hosted build output in ignored `dist/`, and deliverable archives in `outputs/`. Keep caches in ignored `tmp/`.

For an LH notice URL import or a new notice map build, read the project-local skill at `.agents/skills/lh-notice-map/SKILL.md`. Each run must create a new isolated folder, preserve prior runs and the current site, and avoid copying hosting identity. Do not install this project-specific skill into a shared user skill directory. The Claude Code skill at `.claude/skills/lh-notice-map/SKILL.md` reads that file for shared rules; keep both in sync.

Keep a single source for each document: the data standard and replacement guide live only in `.agents/skills/lh-notice-map/references/` (copied into each run's `docs/`). Do not add duplicate copies under `docs/`.

Record material feature changes and checked implementation tasks in `docs/design.md`. Run `.venv/bin/python -m unittest discover -s tests -v` for dataset/pipeline/backend changes (create `.venv` with `./setup_env.sh`).

Sites are add-only: every notice build adds a new site under `lh-runs/`. Never write a different dataset over an existing site (`scripts/dataset.py activate` refuses a site that already has `data.js`); remove unwanted sites with `./delete_site.sh` only when the user asks.
