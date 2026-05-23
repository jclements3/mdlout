# Publishing mdlout to PyPI

`mdlout` ships as a single-file Python module with a `pyproject.toml`. This
doc walks through cutting a release to **TestPyPI** first, then **PyPI
proper**, plus how to wire up CI to do it for you.

## 1. PyPI account setup

1. Register two accounts (they're separate user databases):
   - <https://test.pypi.org/account/register/>
   - <https://pypi.org/account/register/>
2. Enable 2FA on **both** (TOTP or hardware key). PyPI requires 2FA for
   any account that owns a project.
3. Verify your email on each.

## 2. Generate an API token

Tokens are the only supported credential since the password-auth
deprecation. Generate one per host:

1. Sign in -> *Account settings* -> *API tokens* -> *Add API token*.
2. Scope: *Entire account* the first time you upload `mdlout` (the
   project doesn't exist yet so you can't scope narrower). After the
   first upload, regenerate a token scoped to **project: mdlout** and
   delete the wider one.
3. Copy the token immediately - PyPI shows it exactly once. It starts
   with `pypi-` (production) or `pypi-` on TestPyPI too (different
   secret, same prefix).

## 3. `~/.pypirc`

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJ...   # production token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgENdGVzdC5weXBpLm9yZwIk...   # TestPyPI token
```

`chmod 600 ~/.pypirc` so the tokens aren't world-readable.

## 4. Build the artifacts

```bash
cd /path/to/mdlout
rm -rf dist/ build/ *.egg-info
python3 -m pip install --user --upgrade build twine
python3 -m build --sdist --wheel
ls dist/
# expect: mdlout-X.Y.Z.tar.gz + mdlout-X.Y.Z-py3-none-any.whl
```

Validate before any upload:

```bash
python3 -m twine check dist/*
# Both lines should print PASSED.
```

## 5. Upload to TestPyPI first

```bash
python3 -m twine upload --repository testpypi dist/*
```

Then verify in a throwaway venv:

```bash
python3 -m venv /tmp/mdlout-testpypi && . /tmp/mdlout-testpypi/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            mdlout
mdlout --version    # should print: mdlout X.Y.Z
deactivate && rm -rf /tmp/mdlout-testpypi
```

The `--extra-index-url` is required because TestPyPI doesn't mirror
runtime deps. `mdlout` itself has none, but the flag is muscle memory.

## 6. Upload to PyPI proper

Once TestPyPI looks good:

```bash
python3 -m twine upload --repository pypi dist/*
```

Verify the same way against the production index:

```bash
python3 -m venv /tmp/mdlout-pypi && . /tmp/mdlout-pypi/bin/activate
pip install mdlout
mdlout --version
deactivate && rm -rf /tmp/mdlout-pypi
```

## 7. Yanking a bad release

Yanking hides a version from `pip install mdlout` (default resolution)
but keeps it reachable for anyone who pinned to it. Always prefer
yanking over deletion.

Via the web UI:

1. <https://pypi.org/manage/project/mdlout/release/X.Y.Z/> -> *Yank*.
2. Type the version, paste a reason ("broken sdist", "regressed CLI"),
   confirm.

Via `gh` CLI (PyPI itself has no CLI; use `gh` to coordinate the
follow-up release on the repo side):

```bash
# Tag and PR the fix:
git tag -a vX.Y.Z+1 -m "Fix yanked vX.Y.Z"
git push origin vX.Y.Z+1
gh release create vX.Y.Z+1 --notes "Replaces yanked vX.Y.Z."
```

Then upload `X.Y.Z+1` via the steps above.

## 8. CI-driven publish (GitHub Actions)

The existing `.github/workflows/publish.yml` deploys the *examples
gallery* to GitHub Pages; it does **not** publish to PyPI. To automate
PyPI uploads, add a sibling workflow named `pypi-publish.yml` that uses
PyPI's **OIDC trusted publishing** -- no token secret needed in the
repo, no rotation. Minimal shape:

```yaml
# .github/workflows/pypi-publish.yml
name: Publish to PyPI
on:
  release:
    types: [published]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.x' }
      - run: |
          python3 -m pip install --upgrade build twine
          rm -rf dist/ build/ *.egg-info
          python3 -m build --sdist --wheel
          python3 -m twine check dist/*
      - uses: actions/upload-artifact@v4
        with: { name: dist, path: dist/ }

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: { name: pypi, url: 'https://pypi.org/project/mdlout/' }
    permissions:
      id-token: write   # OIDC trusted publishing
    steps:
      - uses: actions/download-artifact@v4
        with: { name: dist, path: dist/ }
      - uses: pypa/gh-action-pypi-publish@release/v1
```

Enable it once:

1. <https://pypi.org/manage/project/mdlout/settings/publishing/> ->
   *Add a new pending publisher* -> fill in:
   - Owner: `jclements3`
   - Repository name: `mdlout`
   - Workflow filename: `pypi-publish.yml`
   - Environment name: `pypi`
2. Repeat at <https://test.pypi.org/manage/account/publishing/> if you
   want a TestPyPI dry-run path too.
3. `gh release create vX.Y.Z --notes-file docs/RELEASE_NOTES_vX.Y.Z.md`
   and the workflow uploads automatically.
