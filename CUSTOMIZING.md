# Customizing & building Moxy

Moxy is generated from the Recursive variable font (`font-data/Recursive_VF_1.085.ttf`)
plus a set of scripts that graft in the Lilex tweaks. There are two artifacts:

- **Static fonts** (`fonts/Moxy-Static/`) — 8 frozen styles, built by
  `scripts/instantiate-code-fonts.py` from `premade-configs/config.moxy.yaml`.
  **This is what the homebrew cask ships.** The look is frozen per the config; there
  are no runtime toggles.
- **Variable font** (`fonts/Moxy-VF/`) — one 4-axis file built by
  `scripts/build-variable-font.py` from `premade-configs/config.moxy-vf.yaml`. It
  stays close to Recursive: Recursive's own feature tags mean what they mean in
  Recursive, and Moxy adds two forward opt-in toggles — `moxy` (letterform bundle)
  and `lilx` (Lilex borrowings). Install it yourself if you want the toggles; it
  is not part of the cask.

> **Static vs variable, plainly:** the shipped static font has the full Moxy look
> baked in with **no** toggles. The variable font defaults to Recursive's look;
> enable `font-feature = moxy, lilx` for the full Moxy look. (Generating the
> static styles directly from the variable font is a possible future step; today
> they're built independently.)

## Setup

Requires Python 3.11 and a checkout of this repo.

```bash
# one time
pyenv local 3.11.8                 # or otherwise use Python 3.11
python -m venv venv                # virtual environment named "venv"
source venv/bin/activate
pip install -r requirements.txt
```

`make setup` runs the equivalent steps.

## Build the static fonts (what ships)

```bash
make build      # builds fonts/Moxy-Static/ and installs to ~/Library/Fonts (macOS)
```

or directly:

```bash
venv/bin/python scripts/instantiate-code-fonts.py \
    premade-configs/config.moxy.yaml font-data/Recursive_VF_1.085.ttf
```

This produces `Moxy-{Regular,Italic,Semibold,SemiboldItalic,Bold,BoldItalic,Black,BlackItalic}-<fontver>.ttf`.

## Build the variable font (the canonical Moxy, with toggles)

```bash
make build-vf   # builds fonts/Moxy-VF/Moxy[CASL,wght,slnt,CRSV].ttf
```

or directly:

```bash
venv/bin/python scripts/build-variable-font.py
```

or with the config explicit:

```bash
venv/bin/python scripts/build-variable-font.py \
    premade-configs/config.moxy-vf.yaml font-data/Recursive_VF_1.085.ttf
```

Install that `.ttf` manually to use the toggles. In Ghostty:

```ini
font-family = Moxy
# bare = close to Recursive; full Moxy look:
# font-feature = moxy, lilx
```

How the variable font is wired (see `scripts/build-variable-font.py` for the
details):

- The bare VF is **close to Recursive** — Recursive's own feature tags
  (`ssNN`, `titl`, `dlig`, …) mean exactly what they mean in Recursive and are
  opt-in the same way. The bare font renders Recursive's letterforms and
  Recursive's native parens/dashes/backslash.
- Two forward opt-in features are added on top:
  - `moxy` — bundles Recursive's `ss02 ss03 ss06 ss08 ss09 ss10 ss11 titl`
    lookups, so one toggle gives the Moxy letterform set (single-story `g`,
    simplified `f r 6 9 1`, shortened-terminal `C`, serifless `L/Z`, dotted `0`,
    fancy long-tail `Q`). Each member also stays
    independently available under its own tag.
  - `lilx` — the Lilex borrowings: curvy parens (cv13), connected dashes/bars
    (cv11), a thin escape-only backslash.
- Always-on (not behind any toggle): the 12 added single-char arrows (cmap'd
  straight), the Recursive-style long-arrow fix (`--->`, `<--`, …, any length)
  in a default-on `calt`, the connected `%`, the clean `/`, pure-mono, and the
  axis rebase. Recursive's own code ligatures stay in `dlig` (opt-in, same as
  Recursive).
- Moxy is **pure monospace**: Recursive's `MONO` axis is pinned to Mono (1) and
  dropped (see `Pure Mono` in `config.moxy-vf.yaml`), so the VF carries four axes
  (CASL, wght, slnt, CRSV). This also bakes out ~half of Recursive's `gvar`
  deltas (≈28% smaller VF) and lets the font honestly flag itself fixed-pitch.

## Tweak which features are baked into the static fonts

Edit `premade-configs/config.moxy.yaml`. It controls the family name, the eight
axis instances, line-height / spacing, and which features are frozen on:

- **Borrowed Glyphs / Join Dashes / Add Characters / Stylistic Sets** — the Lilex
  tweaks grafted in (curvy parens, connected dashes/bars, thin backslash, added
  arrows).
- **Features** (`ss02 ss03 ss06 ss08 ss09 ss10 ss11 titl`) — Recursive's own stylistic
  sets (plus the `titl` titling Q) frozen into the static output. Remove an entry
  to keep Recursive's plain form for that glyph instead; add others (see the
  comments in the file) to bake them on.

To experiment, duplicate the config with a new `Family Name` and point the build
script at it:

```bash
venv/bin/python scripts/instantiate-code-fonts.py premade-configs/<your-config>.yaml
```

## Tweak the variable font recipe

Edit `premade-configs/config.moxy-vf.yaml`. It controls the VF family/output
names, the default axis location, the `moxy` letterform bundle (which Recursive
`ssNN`/`titl` tags it turns on), code ligatures, long arrows, and the
Lilex-derived glyph tweaks behind `lilx`.

## Cut a release

`make package` (or the `update-moxy` skill) builds the static set, zips it (with the
Lilex OFL notice + LICENSE), creates a GitHub release on `kaushikgopal/font-moxy`,
and updates the homebrew cask `font-moxy.rb`. The release version comes from
`Version:` in `config.moxy.yaml`.

## Updating to a new version of Recursive

1. Drop the latest `Recursive_VF_1.0xx.ttf` into `font-data/` and delete the old one.
2. Rebuild (`make build`, `make build-vf`).
3. Re-run the variable-font verification — the `moxy` bundle reuses Recursive's
   own `ssNN`/`titl` lookup indices, so confirm them after an upstream bump.

## Syncing with upstream Recursive tooling

This project began as a fork of
[arrowtype/recursive-code-config](https://github.com/arrowtype/recursive-code-config).
To pull in upstream build-tooling changes:

```bash
git remote add upstream https://github.com/arrowtype/recursive-code-config.git
git fetch upstream
git pull upstream main
```

## Notes

- `Pillow` and `uharfbuzz` are used only for dev-time rendering/shaping checks and
  are intentionally **not** in `requirements.txt`. Install them ad hoc
  (`venv/bin/python -m pip install Pillow uharfbuzz`) when verifying, then remove.
- The README specimen images are generated from the built fonts by
  `scripts/dev/render_specimens.py` (needs `Pillow`): rebuild the fonts, then
  `venv/bin/python scripts/dev/render_specimens.py` writes `images/specimen.png`
  and `images/comparison.png`.
- The variable font carries four axes (Casual, Weight, Slant, Cursive) — Moxy is
  pure monospace, so Recursive's Monospace axis is pinned to Mono and dropped. Its
  default instance is Mono Linear Regular (CASL=0); the bare font renders
  Recursive's letterforms (enable `moxy` for the Moxy letterform set).
