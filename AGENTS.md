# Project conventions

Keep documents in `docs/`, executable tools in `scripts/`, source and normalized datasets in `data/`, configuration in `config/`, tests in `tests/`, website output in `dist/`, and deliverable archives in `outputs/`. Keep caches in ignored `tmp/`.

For an LH notice URL import or a new notice map build, read the project-local skill at `.agents/skills/lh-notice-map/SKILL.md`. Each run must create a new isolated folder, preserve prior runs and the current site, and avoid copying hosting identity. Do not install this project-specific skill into a shared user skill directory.

Record material feature changes and checked implementation tasks in `docs/design.md`. Run `python -m unittest discover -s tests -v` for dataset/pipeline changes.
