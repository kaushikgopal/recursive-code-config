# Moxy — agent notes

Moxy is built on Recursive + Lilex. The **variable font** stays close to
Recursive: Recursive's own feature tags (`ssNN`, `titl`, `dlig`, …) mean exactly
what they mean in Recursive and are opt-in the same way. Moxy adds two forward
opt-in features on top: `moxy` (letterform bundle) and `lilx` (Lilex borrowings).
The **static fonts** (what the homebrew cask ships) bake the full Moxy look in
with no toggles.

## The two VF toggles (both forward, opt-in)

| Feature | What it turns ON | Default |
|---|---|---|
| `moxy` | Recursive letterform set: single-story `g`, simp `f`/`l`/`6`/`9`/`1`, italic diagonals, serifless `L`/`Z`, dotted `0`, fancy long-tail `Q` (bundles `ss02 ss03 ss05 ss07 ss08 ss09 ss10 ss11 titl`) | off |
| `lilx` | Lilex borrowings: curvy parens, connected dashes/bars, thin escape backslash | off |

- **Full Moxy look**: `font-feature = moxy, lilx`
- **Plain Recursive**: bare font (no features)
- Each `ssNN`/`titl` stays independently available too (they compose with `moxy`).

Always-on (not behind any toggle): 12 added arrows, long-arrow fix, connected
`%`, clean `/`, pure-mono, axis rebase.

## Requesting a default change

Three scopes — say which:
- **"default moxy"** = both `premade-configs/config.moxy-vf.yaml` AND
  `premade-configs/config.moxy.yaml`
- **"VF only"** = just the VF config
- **"static only"** = just `config.moxy.yaml` (what the homebrew cask ships)

## Glyph defaults — say the look, this is the action

| Glyph(s) | Desired look | Recursive feature | VF action | Static action |
|---|---|---|---|---|
| g | single-story | `ss02` | add `ss02` to `Moxy Bundle:` | add `ss02` to `Features:` |
| L, Z | serifed (Recursive default) | — | ensure `ss08` is NOT in `Moxy Bundle:` | remove `ss08` from `Features:` |
| L, Z | serifless | `ss08` | add `ss08` to `Moxy Bundle:` | add `ss08` to `Features:` |
| f | simplified | `ss03` | add `ss03` to `Moxy Bundle:` | add `ss03` to `Features:` |
| l | simplified | `ss05` | add `ss05` to `Moxy Bundle:` | add `ss05` to `Features:` |
| k w x y z (italic) | simplified diagonals | `ss07` | add `ss07` to `Moxy Bundle:` | add `ss07` to `Features:` |
| r | simplified | `ss06` | add `ss06` to `Moxy Bundle:` | add `ss06` to `Features:` |
| 6, 9 | simplified | `ss09` | add `ss09` to `Moxy Bundle:` | add `ss09` to `Features:` |
| 0 | dotted | `ss10` | add `ss10` to `Moxy Bundle:` | add `ss10` to `Features:` |
| 1 | simplified | `ss11` | add `ss11` to `Moxy Bundle:` | add `ss11` to `Features:` |
| a | single-story | `ss01` | add `ss01` to `Moxy Bundle:` | add `ss01` to `Features:` |
| @ | simplified | `ss12` | add `ss12` to `Moxy Bundle:` | add `ss12` to `Features:` |
| Q | fancy long-tail (titling) | `titl` | add `titl` to `Moxy Bundle:` | add `titl` to `Features:` |

To REVERT a Moxy default back to Recursive: remove the row from `Moxy Bundle:`
(VF) or `Features:` (static).

Notes:
- `ss04` (simp i) exists but is unconfirmed in Moxy — check before adding.
  `ss05` (simp l) and `ss07` (italic diagonals) are now part of Moxy's
  default bundle; the old "broken upstream, Recursive issue #4" note was
  stale (Moxy's builds handle them).
- In the VF, `moxy` bundles whatever is listed in `Moxy Bundle:`. Adding/removing
  a tag there changes what `moxy` turns on. Each tag also stays independently
  available under its own name.
- In the static build, `Features:` freezes Recursive source features into the
  output (baked into `calt` via `freeze_features`). `titl` works here too.

## Axis defaults

- **VF default**: `Default Axis Location` in `config.moxy-vf.yaml`, and the
  matching `Named Instances` block (keep them in sync, or macOS CoreText
  snaps the default to Recursive's own named instance with the wrong name).
- **Static per-style**: the `Fonts:` block in `config.moxy.yaml`
  (Regular/Italic/Bold/Bold Italic each have their own CASL/wght/slnt/CRSV).

## Build & install

- `make build` — static fonts + install to `~/Library/Fonts`
- `make install-vf` — VF + install to `~/Library/Fonts`
- `make package` — cut a release (bump `Version:` in `config.moxy.yaml` first)

## Verifying after a change

Shape-check the built font with HarfBuzz to confirm a glyph's default and its
toggle behave as intended. The pattern:

```python
import uharfbuzz as hb
from fontTools.ttLib import TTFont
font = TTFont(path)
face = hb.Face(hb.Blob.from_file_path(path))
hf = hb.Font(face)
def shape(t, feat=None):
    b = hb.Buffer(); b.add_utf8(t.encode()); b.guess_segment_properties()
    hb.shape(hf, b, feat or {})
    return [font.getGlyphName(g.codepoint) for g in b.glyph_infos]
# bare vs +moxy / +lilx / +moxy,+lilx / +ssNN
```
