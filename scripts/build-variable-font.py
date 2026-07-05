"""
Build a variable-font source of "Moxy" from premade-configs/config.moxy-vf.yaml.

This is separate from the static code-font build
(scripts/instantiate-code-fonts.py + premade-configs/config.moxy.yaml), which
instantiates fixed fonts and bakes the Moxy look into ``calt``. The VF keeps
Recursive's CASL/wght/slnt/CRSV axes live and stays close to Recursive:
Recursive's own feature tags (ssNN, titl, dlig, …) mean exactly what they mean
in Recursive and are opt-in the same way. Moxy adds two forward opt-in features
on top. (Moxy is pure monospace: Recursive's MONO axis is pinned to Mono and
dropped — see "Pure Mono" in the config.)

Two forward opt-in features:

  * ``moxy`` (custom 4-char feature tag) — bundles Recursive's own
    ss02/ss03/ss06/ss09/ss10/ss11/titl lookups, so one toggle applies the Moxy
    letterform set: single-story g, simplified f/r/6/9/1, dotted 0, fancy Q.
    Each member also stays independently available under its own tag.
  * ``lilx`` (custom 4-char feature tag) — the ported-from-Lilex tweaks:
    curvy parens (cv13), connected dashes, connected bars (cv11), a thin
    escape-only backslash. Off by default; enabling it adds the Lilex look.

Always-on (not behind any toggle): the 12 added single-char arrows (cmap'd
straight), the Recursive-style long-arrow fix (--->, <--, …, any length) in a
default-on ``calt``, the connected %, the clean /, pure-mono, and the axis
rebase. Recursive's own code ligatures stay in ``dlig`` (opt-in, same as
Recursive).

Usage:
    venv/bin/python scripts/build-variable-font.py \
        [premade-configs/config.moxy-vf.yaml] [font-data/Recursive_VF_1.085.ttf] [out.ttf]

Lilex is SIL OFL 1.1 (see font-data/Lilex-OFL.txt); bundle that notice on
distribution.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.otlLib import builder as otl
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vf_lilex import (  # noqa: E402
    add_feature,
    append_lookup,
    feature_lookup_indices,
    free_name_id,
    graft_variable_alternate,
    repair_hvar,
    single_sub_lookup,
    source_bounds,
    wght_anchors,
)

DEFAULT_CONFIG = "premade-configs/config.moxy-vf.yaml"
RECURSIVE_VF = "font-data/Recursive_VF_1.085.ttf"
LILEX_VF = "font-data/Lilex[wght].ttf"

FAMILY = "Moxy"
# The VF and the static build share the family name "Moxy", but the VF gets a
# distinct PostScript name so it can't silently clash with the static instances'
# "Moxy-Regular" etc. if both are ever installed.
PS_NAME = "Moxy-VF"
DEFAULT_OUT = "fonts/Moxy-VF/Moxy[CASL,wght,slnt,CRSV].ttf"
DEFAULT_AXIS_LOCATION = {"MONO": 1, "CASL": 0, "wght": 360}

# OFL-1.1 license metadata baked into the name table (id 0/13/14), so the license
# travels with the binary. Moxy derives from Recursive + Lilex (both OFL-1.1), so
# the font itself must stay OFL-1.1; "Moxy" is a Reserved Font Name. See OFL.txt.
COPYRIGHT = (
    'Copyright 2026 Kaushik Gopal (https://github.com/kaushikgopal/font-moxy), '
    'with Reserved Font Name "Moxy". Portions copyright 2019 The Recursive Project '
    'Authors; portions copyright 2019 The Lilex Project Authors.'
)
LICENSE_DESC = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at https://openfontlicense.org"
)
LICENSE_URL = "https://openfontlicense.org"

# Recursive source features bundled under the forward `moxy` toggle (one switch
# for the full Moxy letterform set). Each member also stays independently
# available under its own tag.
MOXY_BUNDLE = ["ss02", "ss03", "ss06", "ss09", "ss10", "ss11", "titl"]


def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def resolve_glob(path: str) -> str:
    matches = sorted(glob.glob(path))
    return matches[0] if matches else path


def font_version(src_path: str) -> str:
    match = re.search(r"_VF_([0-9.]+)\.ttf$", os.path.basename(src_path))
    return match.group(1) if match else "1.085"


def configure_globals(options: dict) -> None:
    global FAMILY, PS_NAME, LILEX_VF, MOXY_BUNDLE, ARROW_GLYPHS

    FAMILY = options.get("Family Name", FAMILY)
    PS_NAME = options.get("PostScript Name", PS_NAME)
    LILEX_VF = options.get("Lilex VF", LILEX_VF)
    if "Moxy Bundle" in options:
        MOXY_BUNDLE = list(options.get("Moxy Bundle") or [])

    add_chars = options.get("Add Characters") or {}
    if add_chars.get("source"):
        LILEX_VF = add_chars["source"]
    if add_chars.get("glyphs"):
        ARROW_GLYPHS = list(add_chars["glyphs"])


def has_glyph_mapping(options: dict, target: str, source: str) -> bool:
    for spec in options.get("Borrowed Glyphs") or []:
        if (spec.get("glyphs") or {}).get(target) == source:
            return True
    return False


def has_stylistic_set(options: dict, target: str, source: str) -> bool:
    for spec in options.get("Stylistic Sets") or []:
        if (spec.get("glyphs") or {}).get(target) == source:
            return True
    return False


def default_axis_location(options: dict) -> dict:
    if "Default Axis Location" in options:
        return dict(options.get("Default Axis Location") or {})
    return dict(DEFAULT_AXIS_LOCATION)


# ----------------------------------------------------------------------------
# Name table — rename the family to "Moxy", keep every axis.


def rename_family(font: TTFont, source_version: str) -> None:
    name = font["name"]

    def setname(nid, value):
        name.setName(value, nid, 3, 1, 0x409)  # macOS only (Windows skipped)

    setname(1, FAMILY)               # Font Family
    setname(2, "Regular")            # Subfamily (RIBBI default-instance label)
    setname(3, f"{source_version};ARRW;{PS_NAME}")  # Unique ID
    setname(4, FAMILY)               # Full font name (default instance)
    setname(6, PS_NAME)              # PostScript name (distinct from static build)
    setname(16, FAMILY)              # Typographic Family
    setname(17, "Regular")           # Typographic Subfamily
    setname(0, COPYRIGHT)            # Copyright (+ Reserved Font Name "Moxy")
    setname(13, LICENSE_DESC)        # License description (OFL-1.1)
    setname(14, LICENSE_URL)         # License URL


# ----------------------------------------------------------------------------
# "moxy" — a custom 4-char feature bundling Recursive's own ssNN + titl lookups
# behind one forward opt-in toggle. Enabling `moxy` applies the full Moxy
# letterform set (single-story g, simplified f/r/6/9/1, dotted 0, fancy Q).
# Each member also stays independently available under its own ssNN / titl tag.


def add_moxy_feature(font: TTFont) -> None:
    lookups = feature_lookup_indices(font, MOXY_BUNDLE)
    add_feature(
        font,
        feature_tag="moxy",
        lookup_indices=lookups,
    )
    print(f"  • moxy -> lookups {lookups} ({'/'.join(MOXY_BUNDLE)})")


# ----------------------------------------------------------------------------
# lilx tweak: curvy parentheses (Lilex cv13) as variable alternates.


def add_curvy_parens(font: TTFont, recursive_path: str) -> list[int]:
    """Graft parenleft/right.lilx (variable) and return the substituting lookup.

    Parens barely change stroke across MONO (≈50 at wght300, ≈240 at wght1000 for
    both MONO 0 and 1), so MONO is frozen — only wght (300→1000) + slnt shear.
    """
    light, heavy = wght_anchors(
        recursive_path,
        target_glyph="parenleft",
        source_path=LILEX_VF,
        probe_source="parenleft.cv13",
        axis="horizontal",
    )
    mapping = {}
    for base, src in (("parenleft", "parenleft.cv13"),
                      ("parenright", "parenright.cv13")):
        alt = f"{base}.lilx"
        graft_variable_alternate(
            font,
            source_path=LILEX_VF,
            alt_name=alt,
            source_glyphs=[src],
            light_wght=light,
            heavy_wght=heavy,
        )
        mapping[base] = alt
    font.getReverseGlyphMap(rebuild=True)
    idx = append_lookup(font, single_sub_lookup(mapping))
    print(f"  • curvy parens (cv13): Lilex wght {light}->{heavy}, lookup {idx}")
    return [idx]


# ----------------------------------------------------------------------------
# lilx tweak: connected bars |> and <| (Lilex cv11).


def add_connected_bars(font: TTFont, recursive_path: str) -> list[int]:
    """Graft connected |> and <| (Lilex cv11) as variable 2-cell alternates.

    Recursive's dlig ligates bar+greater -> bar_greater.code (a forward 2-cell
    glyph, adv 1200) and less+bar -> less_bar.code. lilx substitutes those for
    connected versions built from Lilex's bar_greater.liga.cv11 /
    less_bar.liga.cv11, repositioned onto Recursive's 1200-unit ligature cell.
    It also forms those two ligatures directly, so lilx works without enabling
    all of Recursive's dlig code ligatures.
    """
    light, heavy = wght_anchors(
        recursive_path,
        target_glyph="bar",
        source_path=LILEX_VF,
        probe_source="bar",
        axis="horizontal",
    )
    rec = TTFont(recursive_path)
    rg = rec["glyf"]
    single_mapping = {}
    lig_mapping = {}
    specs = [
        (("bar", "greater"), "bar_greater.code", "bar_greater.liga.cv11"),
        (("less", "bar"), "less_bar.code", "less_bar.liga.cv11"),
    ]
    for sequence, target, src in specs:
        tg = rg[target]
        tg.recalcBounds(rg)
        adv = rec["hmtx"].metrics[target][0]
        sb = source_bounds(LILEX_VF, light, [src])
        dx = tg.xMin - sb[0]                                    # align left ink edge
        dy = (tg.yMin + tg.yMax) / 2.0 - (sb[1] + sb[3]) / 2.0  # vertical centre
        alt = f"{target}.lilx"
        graft_variable_alternate(
            font,
            source_path=LILEX_VF,
            alt_name=alt,
            source_glyphs=[src],
            light_wght=light,
            heavy_wght=heavy,
            advance=adv,
            dx=dx,
            dy=dy,
        )
        single_mapping[target] = alt
        lig_mapping[sequence] = alt
    font.getReverseGlyphMap(rebuild=True)
    lig = ot.Lookup()
    lig.LookupType = 4
    lig.LookupFlag = 0
    lig.SubTable = [otl.buildLigatureSubstSubtable(lig_mapping)]
    lig.SubTableCount = 1
    lig_idx = append_lookup(font, lig)
    sub_idx = append_lookup(font, single_sub_lookup(single_mapping))
    print(f"  • connected bars (cv11): Lilex wght {light}->{heavy}, lookups {[lig_idx, sub_idx]}")
    return [lig_idx, sub_idx]


# ----------------------------------------------------------------------------
# lilx tweak: connected dashes (--- and longer), Lilex-style.


def add_connected_dashes(font: TTFont, recursive_path: str) -> list[int]:
    """Connect hyphen runs Lilex-style (--- and longer), as opt-in variable glyphs.

    Recursive's dlig ligates only ``--`` and ``---`` (runs of 4+ stay as loose
    ``hyphen`` glyphs). So, like the static build, lilx:
      * substitutes the dlig-formed hyphen_hyphen_hyphen.code -> a connected 3-cell
        bar (.lilx) for ``---``;
      * runs a chain that re-cuts loose runs of >= 4 hyphens into Lilex's
        start/middle/end .seq pieces.
    ``--`` is left as Recursive draws it (two dashes, like Lilex). Variable seq
    pieces + connected bar thicken with wght and shear with slnt.
    """
    from join_dashes import _chain3

    light, heavy = wght_anchors(
        recursive_path,
        target_glyph="hyphen",
        source_path=LILEX_VF,
        probe_source="hyphen",
        axis="vertical",
    )

    # Vertical align: shift Lilex seq pieces onto Recursive's hyphen centre so
    # the joined run sits at the dash height (≈ -6 units).
    rec = TTFont(recursive_path)
    rg = rec["glyf"]
    h = rg["hyphen"]; h.recalcBounds(rg)
    rec_dash_cy = (h.yMin + h.yMax) / 2.0
    seq = ["hyphen_start.seq", "hyphen_middle.seq", "hyphen_end.seq"]
    mid_b = source_bounds(LILEX_VF, light, ["hyphen_middle.seq"])
    dy = rec_dash_cy - (mid_b[1] + mid_b[3]) / 2.0

    for name in seq:
        graft_variable_alternate(
            font,
            source_path=LILEX_VF,
            alt_name=name,
            source_glyphs=[name],
            light_wght=light,
            heavy_wght=heavy,
            dy=dy,
        )

    # Connected "---": tile the three seq pieces onto Recursive's 1800-unit
    # hyphen_hyphen_hyphen.code ink cell.
    tri = rg["hyphen_hyphen_hyphen.code"]; tri.recalcBounds(rg)
    tiled = source_bounds(LILEX_VF, light, seq)
    dx3 = tri.xMin - tiled[0]
    code_lilx = "hyphen_hyphen_hyphen.code.lilx"
    graft_variable_alternate(
        font,
        source_path=LILEX_VF,
        alt_name=code_lilx,
        source_glyphs=seq,
        light_wght=light,
        heavy_wght=heavy,
        advance=rec["hmtx"].metrics["hyphen_hyphen_hyphen.code"][0],
        dx=dx3,
        dy=dy,
    )

    glyph_map = font.getReverseGlyphMap(rebuild=True)

    # lilx lookups: the --- single-sub, three seq single-subs, and a chain.
    lookups: list[int] = []
    i_tri = append_lookup(
        font, single_sub_lookup({"hyphen_hyphen_hyphen.code": code_lilx})
    )
    lookups.append(i_tri)

    i_start = append_lookup(font, single_sub_lookup({"hyphen": "hyphen_start.seq"}))
    i_mid = append_lookup(font, single_sub_lookup({"hyphen": "hyphen_middle.seq"}))
    i_end = append_lookup(font, single_sub_lookup({"hyphen": "hyphen_end.seq"}))

    seq_back = ["hyphen_start.seq", "hyphen_middle.seq"]
    min_run = 4
    start_lookahead = [["hyphen"]] * (min_run - 1)
    chain = ot.Lookup()
    chain.LookupType = 6
    chain.LookupFlag = 0
    chain.SubTable = [
        _chain3([seq_back], [["hyphen"]], [["hyphen"]], i_mid, glyph_map),  # middle
        _chain3([seq_back], [["hyphen"]], [], i_end, glyph_map),            # end
        _chain3([], [["hyphen"]], start_lookahead, i_start, glyph_map),     # start
    ]
    chain.SubTableCount = len(chain.SubTable)
    i_chain = append_lookup(font, chain)
    lookups.append(i_chain)

    print(f"  • connected dashes: Lilex wght {light}->{heavy}, "
          f"lookups {lookups} (+inner {[i_start, i_mid, i_end]})")
    return lookups


# ----------------------------------------------------------------------------
# lilx tweak: thin escape-only backslash (Lilex ss03 glyph).


def add_thin_backslash(font: TTFont, recursive_path: str) -> list[int]:
    """Thin the backslash, but ONLY when it acts as an escape (Lilex glyph).

    Reuses the static build's escape-only contextual logic (add_stylistic_set):
    thin when the backslash is followed by an escape character, but not a Windows
    drive path (``:\\``) and not the 2nd of a consecutive pair (``\\\\``). Escape
    chars are resolved through GSUB single-subs so the moxy-bundled forms
    (r.simple etc.) are covered too. With dlig on, Recursive ligates \\b \\n \\r \\t \\v into
    backslash_X.code (just backslash+letter, no special drawing), so a multiple-sub
    decomposes those to thin-backslash + the base letter.
    """
    from add_stylistic_set import (
        _resolve_glyphs, _ignore_subtable, _sub_subtable, DEFAULT_ESCAPE_CHARS,
    )

    light, heavy = wght_anchors(
        recursive_path,
        target_glyph="hyphen",
        source_path=LILEX_VF,
        probe_source="hyphen",
        axis="vertical",
    )
    alt = "backslash.lilx"
    graft_variable_alternate(
        font,
        source_path=LILEX_VF,
        alt_name=alt,
        source_glyphs=["backslash.ss03"],
        light_wght=light,
        heavy_wght=heavy,
    )
    gm = font.getReverseGlyphMap(rebuild=True)

    base = "backslash"
    inner = append_lookup(font, single_sub_lookup({base: alt}))

    colon = font.getBestCmap().get(ord(":"))
    escape_cov: set[str] = set()
    for ch in DEFAULT_ESCAPE_CHARS:
        escape_cov |= _resolve_glyphs(font, ch)
    escape_cov.add(base)  # so `\\` (backslash before backslash) thins the first

    # _resolve_glyphs follows GSUB single-subs, but the MONO/CASL forms (e.g.
    # '0' -> zero.sans at MONO 0) come from FEATURE VARIATIONS it can't see. Expand
    # to every stem-sibling so escapes thin at all axis locations (\0 \1 \r etc.).
    stem_index: dict[str, list[str]] = {}
    for g in font.getGlyphOrder():
        stem_index.setdefault(g.split(".")[0], []).append(g)
    for g in list(escape_cov):
        escape_cov.update(stem_index.get(g.split(".")[0], []))

    chain = ot.Lookup()
    chain.LookupType = 6
    chain.LookupFlag = 0
    subtables = []
    if colon:  # don't thin a drive-path backslash ( :\ )
        subtables.append(_ignore_subtable([[colon]], [[base]], gm))
    # don't thin the 2nd of a consecutive pair (it's the escaped literal)
    subtables.append(_ignore_subtable([[alt]], [[base]], gm))
    # thin when followed by an escape character
    subtables.append(_sub_subtable([[base]], [sorted(escape_cov)], inner, gm))
    chain.SubTable = subtables
    chain.SubTableCount = len(subtables)
    lookups = [append_lookup(font, chain)]

    # dlig escape ligatures -> thin backslash + base letter
    cmap = font.getBestCmap()
    decomp = {}
    for ch in "bnrtv":
        code = f"backslash_{ch}.code"
        letter = cmap.get(ord(ch))
        if code in font["glyf"] and letter:
            decomp[code] = [alt, letter]
    if decomp:
        mult = ot.Lookup()
        mult.LookupType = 2
        mult.LookupFlag = 0
        mult.SubTable = [otl.buildMultipleSubstSubtable(decomp)]
        mult.SubTableCount = 1
        lookups.append(append_lookup(font, mult))

    print(f"  • thin backslash (escape-only): Lilex wght {light}->{heavy}, "
          f"lookups {lookups}")
    return lookups


# ----------------------------------------------------------------------------
# lilx tweak: 12 added single-char arrows Recursive lacks (always-on).

# Lilex glyph names == uniXXXX of the hooked / looping / circular / double arrows.
ARROW_GLYPHS = [
    "uni21A9", "uni21AA", "uni21B0", "uni21B1", "uni21B2", "uni21B3",
    "uni21B6", "uni21B7", "uni21BA", "uni21BB", "uni21C4", "uni21C6",
]


def add_arrow_chars(font: TTFont, recursive_path: str) -> list[int]:
    """Add 12 fancy single-char arrows from Lilex, ALWAYS-ON (cmap'd straight).

    Recursive maps none of these codepoints (they render as .notdef). Moxy
    grafts the real, variable arrow from Lilex and cmap's the codepoint
    straight to it — no placeholder, no feature gating. The arrows are visible
    in the bare font, independent of `lilx` or `moxy`.
    """
    light, heavy = wght_anchors(
        recursive_path,
        target_glyph="hyphen",
        source_path=LILEX_VF,
        probe_source="hyphen",
        axis="vertical",
    )
    cmap_tables = [t for t in font["cmap"].tables if t.isUnicode()]

    for name in ARROW_GLYPHS:
        cp = int(name[3:], 16)
        graft_variable_alternate(
            font,
            source_path=LILEX_VF,
            alt_name=name,
            source_glyphs=[name],
            light_wght=light,
            heavy_wght=heavy,
        )
        for t in cmap_tables:
            t.cmap[cp] = name

    font.getReverseGlyphMap(rebuild=True)
    print(f"  • added {len(ARROW_GLYPHS)} arrows (always-on): Lilex wght "
          f"{light}->{heavy}")
    return []


# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Moxy-owned named instances. Recursive's inherited instances keep Recursive
# PostScript names, and CoreText/Ghostty can use those while resolving styles.
# Replace them outright after MONO is pinned away so every advertised instance is
# named as Moxy and only contains live axes.

# (subfamily name, wght, slnt, CRSV); MONO=1, CASL=0 for all.
LINEAR_INSTANCES = [
    ("Light", 300, 0, 0.5),
    ("Regular", 360, 0, 0.5),           # == the fvar default
    ("Medium", 500, 0, 0.5),
    ("Bold", 700, 0, 0.5),
    ("Black", 900, 0, 0.5),
    ("Light Italic", 300, -15, 0.5),
    ("Italic", 360, -15, 0.5),
    ("Medium Italic", 500, -15, 0.5),
    ("Bold Italic", 700, -15, 0.5),
    ("Black Italic", 900, -15, 0.5),
]


def instance_postscript_name(subfamily: str) -> str:
    base = re.sub(r"[^A-Za-z0-9-]", "", PS_NAME) or "MoxyVF"
    suffix = re.sub(r"[^A-Za-z0-9]", "", subfamily) or "Regular"
    return f"{base}-{suffix}"


def replace_named_instances(font: TTFont, instances: list[dict] | None = None) -> None:
    from fontTools.varLib.instancer import names as instancer_names
    from fontTools.ttLib.tables._f_v_a_r import NamedInstance

    name = font["name"]
    configured = instances if instances is not None else [
        {
            "name": subfamily,
            "MONO": 1.0,
            "CASL": 0.0,
            "wght": wght,
            "slnt": slnt,
            "CRSV": crsv,
        }
        for subfamily, wght, slnt, crsv in LINEAR_INSTANCES
    ]
    # Only coordinate axes that still exist on the font (Moxy is pure-mono: MONO
    # is pinned away, so drop it from instance coordinates).
    live_axes = {a.axisTag for a in font["fvar"].axes}

    with instancer_names.pruningUnusedNames(font):
        font["fvar"].instances = []
        seen: set[tuple[tuple[str, float], ...]] = set()
        for spec in configured:
            subfamily = spec["name"]
            coords = {
                tag: float(spec[tag])
                for tag in ("MONO", "CASL", "wght", "slnt", "CRSV")
                if tag in spec and tag in live_axes
            }
            key = tuple(sorted(coords.items()))
            if key in seen:
                continue
            seen.add(key)

            subfamily_id = free_name_id(font)
            name.setName(subfamily, subfamily_id, 3, 1, 0x409)
            ps_id = free_name_id(font)
            name.setName(instance_postscript_name(subfamily), ps_id, 3, 1, 0x409)

            inst = NamedInstance()
            inst.coordinates = coords
            inst.subfamilyNameID = subfamily_id
            inst.postscriptNameID = ps_id
            inst.flags = 0
            font["fvar"].instances.append(inst)

    casl_counts: dict[float, int] = {}
    for inst in font["fvar"].instances:
        c = inst.coordinates.get("CASL", 0.0)
        casl_counts[c] = casl_counts.get(c, 0) + 1
    casl_summary = ", ".join(f"CASL={c}: {n}" for c, n in sorted(casl_counts.items()))
    print(f"  • replaced named instances with Moxy-owned set ({casl_summary})")


def prune_stat_to_live_axes(font: TTFont) -> None:
    if "STAT" not in font or "fvar" not in font:
        return

    stat = font["STAT"].table
    if not stat.DesignAxisRecord:
        return

    live_axes = [axis.axisTag for axis in font["fvar"].axes]
    live = set(live_axes)
    old_axes = list(stat.DesignAxisRecord.Axis)
    old_to_new: dict[int, int] = {}
    new_axes = []
    for old_index, axis in enumerate(old_axes):
        if axis.AxisTag not in live:
            continue
        old_to_new[old_index] = len(new_axes)
        axis.AxisOrdering = len(new_axes)
        new_axes.append(axis)

    if len(new_axes) == len(old_axes):
        return

    stat.DesignAxisRecord.Axis = new_axes
    stat.DesignAxisCount = len(new_axes)

    if not stat.AxisValueArray:
        print(f"  • pruned STAT axes to live fvar axes ({', '.join(live_axes)})")
        return

    new_values = []
    for axis_value in stat.AxisValueArray.AxisValue:
        if axis_value.Format in (1, 2, 3):
            if axis_value.AxisIndex not in old_to_new:
                continue
            axis_value.AxisIndex = old_to_new[axis_value.AxisIndex]
            new_values.append(axis_value)
        elif axis_value.Format == 4:
            records = []
            for record in axis_value.AxisValueRecord:
                if record.AxisIndex not in old_to_new:
                    continue
                record.AxisIndex = old_to_new[record.AxisIndex]
                records.append(record)
            if len(records) < 2:
                continue
            axis_value.AxisValueRecord = records
            axis_value.AxisCount = len(records)
            new_values.append(axis_value)
        else:
            new_values.append(axis_value)

    stat.AxisValueCount = len(new_values)
    if new_values:
        stat.AxisValueArray.AxisValue = new_values
    else:
        stat.AxisValueArray = None
    print(f"  • pruned STAT axes to live fvar axes ({', '.join(live_axes)})")


# ----------------------------------------------------------------------------


def build(src_path: str, out_path: str, options: dict | None = None) -> None:
    options = load_config(DEFAULT_CONFIG) if options is None else options
    configure_globals(options)

    print(f"Loading {src_path}")
    font = TTFont(src_path)
    # Force-decompile glyf/gvar/HVAR now, before we add any glyphs. glyf/gvar store
    # a glyphCount asserted against the (still-original) glyph order; HVAR's
    # AdvWidthMap decompiles lazily and, if first touched AFTER we add glyphs, would
    # auto-fill the new glyphs with the repeat-last varidx — so decompile its map
    # now (1304 entries) and let repair_hvar add the new glyphs explicitly later.
    _ = font["glyf"]
    _ = font["gvar"]
    _ = font["HVAR"].table.AdvWidthMap.mapping

    # ---- Moxy glyph tweaks, on the raw variable source -----------------------
    # Done first, while each tweaked glyph still carries its full gvar, so the
    # later MONO-pin + default-rebase re-normalise the result cleanly. The
    # %, /, \, $, @, & and fuller ✓, • are all drawn directly (OFL-clean
    # geometry) — no external outline is read or shipped. All baked into Moxy
    # (not configurable).
    import glyph_tweaks
    print("Applying glyph tweaks: percent, slash, backslash, checkmark, bullet")
    glyph_tweaks.draw_percent(font)
    glyph_tweaks.draw_slash(font)
    glyph_tweaks.draw_backslash(font)
    glyph_tweaks.draw_checkmark(font)
    glyph_tweaks.draw_bullet(font)
    # NOTE: the seven weight-calibrated glyphs ($ @ & 2 4 5 7) are drawn LATER,
    # after the default is rebased to 375, so their light master lands on the
    # default (375). See "calibrated drawn glyphs" below.

    print(f"Renaming family -> '{FAMILY}'")
    rename_family(font, font_version(src_path))

    if MOXY_BUNDLE:
        print("Adding moxy feature (forward letterform bundle)")
        add_moxy_feature(font)

    # ---- default fix: Recursive-style long arrows (extends dlig) --------------
    # Built BEFORE lilx so its lookups get lower indices and HarfBuzz applies them
    # first: the long-arrow chain then claims arrow contexts (dashes next to < or >)
    # before lilx's connected-dash chain would turn those dashes into Lilex seq
    # pieces. Plain dash runs (no arrowhead) fall through to lilx as before.
    if options.get("Long Arrows", True):
        print("Adding long-arrow fix (--->, <--, <-->, …) to dlig + default-on calt")
        from vf_long_arrows import long_arrows
        la = long_arrows(font, src_path)
        print(f"  • long arrows -> dlig lookups {la}")
        # Also wire the long-arrow lookups into a default-on calt so they render
        # without dlig (Recursive ships no calt; Moxy's long-arrow fix is additive
        # and always-on). Recursive's own code ligatures stay in dlig (opt-in).
        add_feature(font, feature_tag="calt", lookup_indices=la)
        print(f"  • long arrows -> calt (default-on) lookups {la}")

    # ---- lilx: the ported-from-Lilex tweaks, all behind one opt-in tag --------
    print("Building lilx feature (opt-in Lilex tweaks)")
    lilx_lookups: list[int] = []
    if has_glyph_mapping(options, "parenleft", "parenleft.cv13"):
        lilx_lookups += add_curvy_parens(font, src_path)
    if has_glyph_mapping(options, "bar_greater.code", "bar_greater.liga.cv11"):
        lilx_lookups += add_connected_bars(font, src_path)
    if options.get("Join Dashes"):
        lilx_lookups += add_connected_dashes(font, src_path)
    if has_stylistic_set(options, "backslash", "backslash.ss03"):
        lilx_lookups += add_thin_backslash(font, src_path)
    if options.get("Add Characters"):
        lilx_lookups += add_arrow_chars(font, src_path)

    if lilx_lookups:
        add_feature(font, feature_tag="lilx", lookup_indices=lilx_lookups)
        print(f"  • lilx -> lookups {lilx_lookups}")

    # ---- keep HVAR but make the new glyphs advance-correct -------------------
    # Recursive ships HVAR; HarfBuzz reads advances from it, and glyphs beyond its
    # map repeat the last entry's +700 wght delta (our alternates would balloon to
    # 800 at heavy weights). Point every new glyph at a zero-delta entry instead.
    n = repair_hvar(font)
    print(f"Repaired HVAR: {n} new glyphs pinned to zero advance variation")

    # rebuild glyph-name cache before any compile/cmap touches new glyphs
    font.getReverseGlyphMap(rebuild=True)

    # ---- pure-mono + mono-by-default -----------------------------------------
    # Moxy is a coding font, so MONO is PINNED to its default value (1, Mono) and
    # the axis is dropped — there's no useful Sans (proportional) mode in a
    # terminal, and baking MONO out removes ~half of Recursive's gvar deltas
    # (≈28% smaller VF) plus the MONO-conditioned feature variations. The other
    # axes are only REBASED (default moved, full range kept): CASL=0, wght=360,
    # with slnt/CRSV still fully reachable. Set "Pure Mono: false" in the config to
    # keep MONO live instead.
    pure_mono = options.get("Pure Mono", True)
    axis_defaults = default_axis_location(options)
    if axis_defaults:
        from fontTools.varLib import instancer
        axis_limits = {}
        for axis in font["fvar"].axes:
            tag = axis.axisTag
            if tag == "MONO" and pure_mono:
                axis_limits["MONO"] = float(axis_defaults.get("MONO", 1))  # pin -> drop axis
            elif tag in axis_defaults:
                axis_limits[tag] = (axis.minValue, float(axis_defaults[tag]), axis.maxValue)
        instancer.instantiateVariableFont(
            font,
            axis_limits,
            inplace=True,
        )
        font.getReverseGlyphMap(rebuild=True)
        prune_stat_to_live_axes(font)
        kept = [a.axisTag for a in font["fvar"].axes]
        pinned = " (MONO pinned=1, axis dropped)" if pure_mono else ""
        pretty = ", ".join(f"{tag}={value}" for tag, value in axis_defaults.items())
        print(f"Re-based default -> {pretty}{pinned}; axes now {kept}")

    # ---- calibrated drawn glyphs ($ @ & 2 4 5 7) -----------------------------
    # Drawn AFTER the default rebase so each glyph's "light" master lands on the
    # new default (wght 375 = Recursive Regular) with a "thin" master at wght 300
    # and a "heavy" at wght 1000. This makes their stroke weight track Recursive's
    # own glyphs across the wght axis (they previously rendered a too-heavy blend
    # at 375). All baked into Moxy (not configurable). See scripts/glyph_tweaks.py.
    print("Applying calibrated glyph tweaks: dollar, at, ampersand, two, four, five, seven")
    glyph_tweaks.draw_dollar(font)
    glyph_tweaks.draw_at(font)
    glyph_tweaks.draw_ampersand(font)
    glyph_tweaks.draw_two(font)
    glyph_tweaks.draw_four(font)
    glyph_tweaks.draw_five(font)
    glyph_tweaks.draw_seven(font)

    # ---- replace inherited Recursive named instances -------------------------
    # Recursive's fvar instances carry Recursive PostScript names. Replacing them
    # keeps CoreText/Ghostty style matching inside the Moxy family.
    replace_named_instances(font, options.get("Named Instances"))

    # ---- advertise true monospace --------------------------------------------
    # With MONO pinned to Mono, every glyph is the 600-unit cell at every axis
    # location, so Moxy is genuinely fixed-pitch now. Flag it (post.isFixedPitch +
    # OS/2 Panose bProportion=Monospaced + xAvgCharWidth=600) so terminals and
    # editors that gate on these detect Moxy as a monospace font. (The static
    # build already sets these per instance; the VF couldn't truthfully claim it
    # while the Sans end of MONO was reachable.)
    if options.get("Pure Mono", True):
        font["post"].isFixedPitch = 1
        font["OS/2"].panose.bProportion = 9  # 9 = Monospaced
        font["OS/2"].xAvgCharWidth = 600
        print("  • flagged true monospace (isFixedPitch, Panose, xAvgCharWidth=600)")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    font.save(out_path)
    print(f"\n→ Saved {out_path}")


def parse_args(argv: list[str]) -> tuple[dict, str, str]:
    args = list(argv)
    config_path = DEFAULT_CONFIG
    if args and args[0].endswith((".yaml", ".yml")):
        config_path = args.pop(0)

    options = load_config(config_path)
    source = args.pop(0) if args else options.get("Source VF", RECURSIVE_VF)
    out = args.pop(0) if args else options.get("Output Path", DEFAULT_OUT)
    if args:
        raise SystemExit(
            "Usage: build-variable-font.py "
            "[premade-configs/config.moxy-vf.yaml] [source-vf.ttf] [out.ttf]"
        )
    return options, resolve_glob(source), out


if __name__ == "__main__":
    config, src, out = parse_args(sys.argv[1:])
    build(src, out, config)
