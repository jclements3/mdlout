# Publishing mdlout output to the web

This guide walks through getting `mdlout`-generated HTML onto a public
URL. The output is just files -- no server-side runtime is needed --
so almost any static-hosting target works. The instructions below
assume GitHub Pages because it costs nothing and integrates with the
CI that already lives in this repo, but every section translates
directly to Netlify, Cloudflare Pages, S3 + CloudFront, or an old
shared-hosting account behind sftp.

## 1. Single-file output

Each `./mdlout.py foo.md` invocation produces a single self-contained
`foo.html`: every stylesheet, every webfont (when `--subset-fonts` is
used the inlined Nimbus is trimmed to the codepoints the document
actually uses), and -- by default -- KaTeX and abcjsharp are inlined.
There are no sibling files to lose track of.

```bash
./mdlout.py paper.md                  # paper.html, ~1 MB self-contained
./mdlout.py paper.md --external-assets   # paper.html, ~80 KB + CDN
./mdlout.py paper.md --no-math-engine    # drop KaTeX if no math
```

Upload that one file anywhere a static host accepts HTML: scp,
rsync, drag-and-drop into S3, an `<iframe>` on someone else's blog.
There is no install step on the server side.

## 2. GitHub Pages

GitHub Pages has two layouts; both work with mdlout.

### Option A: `/docs` on `main` (recommended)

Build the HTML into `docs/` in the same repository and enable Pages
from **Settings -> Pages -> Source: Deploy from a branch -> main -> /docs**.
Suggested tree:

```
repo/
  src/             # the .md sources
    index.md
    paper.md
    notes.md
  docs/            # mdlout output -- this is what GitHub serves
    index.html
    paper.html
    notes.html
    paper_preview.html
    notes_preview.html
  mdlout.py
  lout/
```

The `_preview.html` files are the same content paginated as a
continuous-flow single page (handy for screen reading vs. the
paginated `paper.html`). The `index.html` is typically built from a
small `examples/index.md`-style landing page that links to the rest.

### Option B: `gh-pages` branch

If you'd rather not have `docs/` cluttering the main branch, push the
same tree to an orphan `gh-pages` branch and set **Settings -> Pages
-> Source -> gh-pages -> /**. The CI workflow in section 3 supports
both layouts via a single boolean toggle.

The `/docs`-on-`main` layout is simpler: one branch, one commit per
update, source and rendered output reviewed in the same PR.

## 3. CI-driven publish

This repo ships a reference workflow at
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml).
It runs on every push to `main` and does the following:

1. Checks out the repo with submodules and switches `lout/` to
   `svg-backend` (the same prelude `ci.yml` uses).
2. Installs `build-essential`, `ghostscript`, and `python3`.
3. Builds `lout/lout` (cached across runs).
4. Runs `./mdlout.py src/*.md -o docs/` to refresh the rendered
   tree.
5. Uploads `docs/` as a Pages artifact and calls
   `actions/deploy-pages@v4` to publish.

The workflow file lives at `.github/workflows/publish.yml` in this
repo; review it before enabling it on your fork. Note that adding or
editing files under `.github/workflows/` requires the OAuth
`workflow` scope on your push token -- see
[`docs/CI.md`](../docs/CI.md) for the one-line `gh auth refresh`
incantation.

## 4. Custom domain + DNS

GitHub Pages serves at `https://<user>.github.io/<repo>/` out of the
box. To attach a custom domain (`example.com` or `docs.example.com`):

1. In **Settings -> Pages -> Custom domain**, enter the hostname and
   save. GitHub writes a `CNAME` file into the published branch on
   your behalf -- keep it there.
2. Add DNS records at your registrar:

   **Apex (`example.com`)** -- four `A` records pointing at GitHub's
   anycast IPs:

   ```
   A   @   185.199.108.153
   A   @   185.199.109.153
   A   @   185.199.110.153
   A   @   185.199.111.153
   ```

   (Also add the matching `AAAA` records to `2606:50c0:8000::153`
   through `...:8003::153` if you want IPv6.)

   **Subdomain (`docs.example.com`)** -- one `CNAME`:

   ```
   CNAME   docs   <user>.github.io.
   ```

3. Tick **Enforce HTTPS** once the cert has provisioned (usually a
   few minutes after DNS propagates).

## 5. Accessibility checklist

mdlout's HTML scaffold ships an accessibility baseline by default;
opt out with `--no-a11y` if you need bare-bones markup.

What you get by default:

- `<html lang="...">` populated from frontmatter `language:` (falls
  back to `en`).
- `<main>`, `<header>`, `<nav>`, `<footer>` landmarks where applicable.
- A "skip to main content" link as the first focusable element.
- ARIA roles on the TOC, footnotes back-links, and admonition blocks.
- `alt=""` on decorative images (`![](file.svg)` with empty alt text);
  meaningful images get the alt verbatim from the source.
- `aria-label` on math foreignObjects mirroring the TeX source so a
  screen reader still reads "x squared plus one".

Screen-reader smoke test before publishing:

- **Windows**: NVDA (free) + Firefox. Cycle headings with `H`, lists
  with `L`, landmarks with `D`. The skip link should be the first
  thing announced on page load.
- **macOS**: VoiceOver (`Cmd+F5`). Use the rotor (`Ctrl+Opt+U`) to
  walk landmarks and headings. KaTeX math should be read aloud from
  the `aria-label`.
- **Linux**: Orca + Firefox is the closest equivalent; behaviour
  matches NVDA closely enough for spot checks.

Run `pa11y https://<your-url>/paper.html` or the Lighthouse
accessibility audit (Chrome DevTools) for a non-interactive sweep.

## 6. Sharing source alongside output

Mixing `.md` source and `.html` output in the same repo is the
convention this project uses for `examples/`. Recommended layout for
a personal site:

```
repo/
  src/             # .md sources -- the thing humans edit
  docs/            # mdlout HTML output -- what GitHub Pages serves
  assets/          # images, .svg files, anything @SVGFile-referenced
  mdlout.py        # vendored or a git submodule
  lout/            # submodule
  .github/workflows/publish.yml
```

Benefits:

- A reader who hits "View source on GitHub" from the rendered page
  lands in `src/`, where they can read the Markdown rather than
  decoding inlined `<svg>`.
- `git blame` on `src/*.md` gives meaningful history; `docs/*.html`
  is a build artifact and noisy to blame.
- The CI publish workflow knows exactly which directory is input and
  which is output.

For repositories where mdlout is *the* project (this one), keep
`examples/*.md` and `examples/out/*.html` -- the existing convention.
For repositories where mdlout is a tool you happen to use, prefer
`src/` + `docs/`.
