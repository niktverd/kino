# AGENTS.md

## Purpose

This repository stores a manually curated film catalog in YAML and generates a Markdown report from it.

## Repo Structure

- `package.json` — `npm start` runs the report builder.
- `src/code/build.report.js` — scans `films/*`, parses simple YAML records, and writes `films-report.md`.
- `films/00-init` — intake bucket for new recommendations. Add new candidate films here first.
- `films/01-amazing` to `films/07-next` — manually curated status buckets for accepted catalog entries.
- `films-report.md` — generated report. Rebuild it after catalog changes.
- `src/init/*` — one-off import/extraction helpers used to bootstrap the catalog.

## YAML Rules

- Keep one film per `.yaml` file.
- Supported keys are `name`, `description`, and `opinion`.
- Use single-line scalar values only. The parser does not support nested YAML, arrays, or multiline blocks.
- Prefer double-quoted strings.
- Prefer Russian titles and Russian descriptions to match the existing catalog.
- Use lowercase kebab-case filenames, usually a transliterated title plus year when helpful.

## Required Workflow

1. Build the current report with `npm start -- --no-interactive`.
2. Analyze `films-report.md` and the existing section layout before suggesting anything.
3. Offer exactly 3 new films that are not already present anywhere in `films/`.
4. Create one YAML file per proposed film inside `films/00-init` with `name` and `description`.
5. Do not move, delete, or re-rank those intake files unless the user explicitly asks. The user manages them manually after creation.
6. Rebuild the report again so `films/00-init` is included and verify the result.

## Editing Guidance

- Treat `films-report.md` as generated output.
- Do not bulk-rewrite existing film files unless the task specifically requires it.
- Preserve unrelated user changes if the worktree is dirty.
