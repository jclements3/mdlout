# Continuous Integration

This repo ships two GitHub Actions workflows under `.github/workflows/`.

## Workflows

### `ci.yml` — build + snippet regression

- **Trigger**: every `push` (any branch) and every `pull_request`
  (opened, reopened, synchronize).
- **Job**: `build-and-test` on `ubuntu-latest`.
- **What it does**:
  1. Checks out the repo with `submodules: recursive` so `lout/` is
     populated.
  2. Switches the `lout` submodule to the maintainer's fork
     (`https://github.com/jclements3/lout.git`) and pins it to the
     `svg-backend` branch.
  3. Installs build deps: `build-essential`, `ghostscript`,
     `poppler-utils`, `librsvg2-bin`, `imagemagick`, `python3`.
  4. Caches `lout/lout`, `lout/prg2lout`, and `lout/*.o` keyed on the
     hash of `lout/makefile`, `lout/*.c`, `lout/*.h`.
  5. Builds `lout` (`cd lout && make lout`).
  6. Runs `bash tests/run_all.sh` — the full snippet regression suite.

### `user-guide-diff.yml` — weekly PS vs SVG diff

- **Trigger**: manual (`workflow_dispatch`) and on a cron at
  `0 6 * * 1` (Monday 06:00 UTC).
- **Job**: `user-guide-diff` on `ubuntu-latest`.
- **What it does**:
  1. Same checkout + submodule + deps + build-lout steps as `ci.yml`.
  2. Builds `lout/doc/user/all` twice — seven passes of PostScript,
     then seven passes of SVG (`-Z`) — so cross-references settle.
  3. Runs `bash tests/user_guide_diff.sh` to diff the two.
  4. Uploads `tests/user_guide_diff/` as an artifact (30-day retention)
     even if the diff job fails.

## Pushing workflow changes

The local `gh` CLI's OAuth token in this dev env does not include the
`workflow` scope, so pushes that touch `.github/workflows/**` are
refused by GitHub with:

```
refusing to allow an OAuth App to create or update workflow ...
```

To push them yourself:

```bash
gh auth refresh -s workflow
git push origin main
```

After that, the scope persists for the local token and subsequent
workflow edits push without ceremony.

Docs-only files (this one included) don't need the `workflow` scope and
push fine with the default token.

## Local reproduction

Without GitHub Actions, you can run the same commands locally on
Ubuntu (or any Linux with the deps above):

```bash
git submodule update --init
cd lout && git checkout svg-backend && cd ..

cd lout && make lout && cd ..
bash tests/run_all.sh                # what ci.yml runs
bash tests/user_guide_diff.sh        # what user-guide-diff.yml runs
                                     # (after building lout/doc/user/all)
```

If you have [`act`](https://github.com/nektos/act) installed you can
also drive the workflows directly:

```bash
act --list                           # enumerate jobs
act -n -j build-and-test             # dry-run the CI job
act -j build-and-test                # actually run it (needs Docker)
```

`act` was not available in the dev env when these workflows were
authored, so they were validated by `python3 -c "import yaml; ..."`
parse + manual review only.

## Submodule note

Every workflow assumes `lout/` is checked out and switched to the
`svg-backend` branch of `jclements3/lout`. The same applies locally:

```bash
git submodule update --init
cd lout && git checkout svg-backend
```

Skip this and `make lout` fails because `z53.c` is missing.
