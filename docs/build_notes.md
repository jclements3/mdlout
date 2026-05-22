# Build notes

Per-platform notes for getting mdlout built and running. The runtime
requirements split into three groups:

- **Build deps** — needed to build the `lout` binary from the submodule
  (gcc or another ANSI-C compiler, `make`).
- **PDF-path deps** — `ps2pdf` from Ghostscript.
- **HTML-path deps** — `rsvg-convert` (librsvg) and ImageMagick are needed
  only for the regression tests under `tests/`; the HTML pipeline itself
  only needs Python 3.10+ and a modern browser. `fontTools` is optional
  and only used for `--text-as-paths`.

Python 3.10+ is required for `mdlout.py`. No third-party Python packages
are needed for the converter itself.

## Linux

### Ubuntu / Debian

Tested. The maintainer's primary development environment is Ubuntu under
WSL2, so this is the best-exercised path.

```
sudo apt update
sudo apt install -y build-essential git python3 ghostscript \
                    librsvg2-bin imagemagick \
                    fonts-urw-base35
```

Package map:

| Package             | Provides                                              |
| ------------------- | ----------------------------------------------------- |
| `build-essential`   | `gcc`, `make`, `libc6-dev`                            |
| `python3`           | Python 3 (Ubuntu 22.04+ ships 3.10 or newer)          |
| `ghostscript`       | `gs` and `ps2pdf` for the PDF path                    |
| `librsvg2-bin`      | `rsvg-convert` for the regression tests               |
| `imagemagick`       | `compare`, `convert`, `identify` for the tests        |
| `fonts-urw-base35`  | URW++ Nimbus fonts at `/usr/share/fonts/opentype/urw-base35/` (used for HTML `@font-face` embedding) |

Optional, for finer-grained regression diffs:

```
sudo apt install -y python3-pil python3-numpy python3-skimage
```

This enables SSIM in `tests/compare.py`. Without it the pixel-diff
metric alone gates pass/fail.

Optional, for `--text-as-paths`:

```
sudo apt install -y python3-fonttools
```

### Fedora / RHEL / CentOS Stream

Likely-but-not-fully-verified by the maintainer. The package names below
are taken from Fedora 39+; older RHEL/CentOS releases may need EPEL or a
different Python version.

```
sudo dnf install -y gcc make git python3 ghostscript \
                    librsvg2-tools ImageMagick \
                    urw-base35-fonts
```

Package map:

| Package              | Provides                                         |
| -------------------- | ------------------------------------------------ |
| `gcc`, `make`        | Toolchain (build-essential equivalent)            |
| `python3`            | Python 3.10+ on Fedora 36+                        |
| `ghostscript`        | `gs` and `ps2pdf`                                 |
| `librsvg2-tools`     | `rsvg-convert`                                    |
| `ImageMagick`        | `compare`, `convert`, `identify`                  |
| `urw-base35-fonts`   | URW++ Nimbus fonts (path may differ from Debian) |

Optional SSIM:

```
sudo dnf install -y python3-pillow python3-numpy python3-scikit-image
```

If `python3 --version` reports older than 3.10, install
`python3.11` or `python3.12` from Fedora's package set and adjust the
shebang on `mdlout.py` or invoke explicitly: `python3.12 ./mdlout.py
input.md`.

## macOS

**Untested by the maintainer.** The expected install path uses Homebrew.
Report back if a step is wrong.

```
brew install gcc make python ghostscript librsvg imagemagick poppler
```

Notes:

- Apple's default `clang` should be sufficient to build Lout; the explicit
  `brew install gcc` is only needed if a specific gcc dialect surfaces a
  bug in clang's `-ansi` mode. Try `cd lout && make lout` with the
  toolchain you already have first.
- `python` on Homebrew is currently 3.12+, satisfying the 3.10 floor.
- `ghostscript` provides `gs` and `ps2pdf`.
- `librsvg` provides `rsvg-convert`.
- `imagemagick` provides `compare`, `convert` (or `magick convert` on
  ImageMagick 7), and `identify`.
- `poppler` is listed for completeness — `pdftocairo` and `pdftoppm` are
  occasionally useful for hand-debugging PDF output, but mdlout itself
  does not depend on them.

URW++ Nimbus fonts on macOS: Homebrew's `ghostscript` ships its own copy
of the URW++ base-35 family under
`/usr/local/share/ghostscript/<version>/Resource/Font/` (or
`/opt/homebrew/...` on Apple Silicon). If the HTML `@font-face` embedding
cannot find those, pass `--no-font-embedding` and accept that the browser
will pick a fallback face — line breaks will then drift relative to the
PDF.

### Confirming the build on macOS

After `brew install`:

```
git clone https://github.com/jclements3/mdlout.git
cd mdlout
git submodule update --init
cd lout && git checkout svg-backend && make lout && cd ..
./mdlout.py examples/01_hello.md
```

If `make lout` complains about `-ansi` under Apple clang, fall back to
`make lout CC=gcc-13` (or whichever gcc Homebrew installed). The maintainer
has not personally walked this path; treat any breakage as a bug worth
filing.

## WSL on Windows

Tested. This is one of the maintainer's primary environments. Inside the
WSL distribution, follow the [Ubuntu / Debian](#ubuntu--debian)
instructions exactly — WSL2 with Ubuntu behaves like Ubuntu for build
purposes.

### Chrome from Windows for `tests/chromium_diff.sh`

The regression harness `tests/chromium_diff.sh` runs Chromium headless to
rasterise the SVG side with the Nimbus `@font-face` fonts actually
applied (rsvg-convert ignores `@font-face`). On WSL it auto-detects a
Windows-side Chrome at:

```
/mnt/c/Program Files/Google/Chrome/Application/chrome.exe
/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe
```

before falling back to Linux Chromium (`/usr/bin/chromium`,
`/snap/bin/chromium`, etc.). It shuttles files through `/mnt/c/temp/` to
avoid a Chrome bug with `\\wsl.localhost\...` file URLs. No extra setup
beyond having Chrome installed on the Windows host. The relevant
environment overrides:

```
WORK=/mnt/c/temp/userguide_chromium     # staging directory (Windows-local)
WIN_WORK='C:\temp\userguide_chromium'   # same path in Windows form
```

The script sets these automatically when it sees `/mnt/c`. Linux Chromium
inside WSL also works but is noticeably slower per page and does not
match what end users see in their browser.

### Other WSL caveats

- File-system performance on `/mnt/c/...` is much worse than on the
  WSL-native filesystem. Keep the mdlout checkout under `~` (which lives
  on the ext4 filesystem inside WSL), not under `/mnt/c/...`.
- If `make lout` fails with character-set or locale errors, ensure
  `LC_ALL` is set to a UTF-8 locale (`export LC_ALL=C.UTF-8`).

## Native Windows (MinGW / MSYS2)

**Untested.** The Lout binary itself is portable ANSI C and has been
reported elsewhere to build under MinGW and MSYS2, so `make lout` likely
works. The full mdlout pipeline (Python wrapper, `ps2pdf`,
`rsvg-convert`, ImageMagick) has not been validated on native Windows
by the maintainer.

If you want to try:

- Use MSYS2 (`pacman -S` package set) for the toolchain, Python, and
  Ghostscript.
- `librsvg` is available as `mingw-w64-x86_64-librsvg` and provides
  `rsvg-convert`.
- ImageMagick can be installed natively or via MSYS2.
- Adjust shebangs and path-quoting in `mdlout.py` as needed.

Recommended alternative: install WSL2 with Ubuntu and follow the WSL
instructions above. That path is exercised regularly.

## Verifying the install

End-to-end smoke test after install on any platform:

```
git clone https://github.com/jclements3/mdlout.git
cd mdlout
git submodule update --init
cd lout && git checkout svg-backend && make lout && cd ..
./mdlout.py examples/01_hello.md                 # produces 01_hello.html
./mdlout.py examples/01_hello.md --format=pdf    # produces 01_hello.pdf
```

Open `examples/01_hello.html` in a browser and `examples/01_hello.pdf` in
a PDF viewer. Both should render without errors. If the HTML page renders
but the math example (`examples/04_math.md`) shows raw LaTeX, KaTeX is
not loading — check that the script tag points at a reachable copy
(`--external-assets` forces the CDN if the local fallbacks aren't found).

To exercise the regression framework:

```
bash tests/run_all.sh
```

This runs every snippet in `tests/snippets/` through both back ends and
writes `tests/report.html`. SSIM is reported only if scikit-image is
installed; without it the framework prints a note and gates on pixel diff
alone.
