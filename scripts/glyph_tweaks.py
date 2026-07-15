"""Glyph tweaks for Moxy.

Moxy adjusts a few of Recursive's glyphs toward shapes Kaush prefers. Each
adjusted glyph is **drawn** directly from explicit geometry in this module
(polygons, circles, ellipses, or hardcoded quadratic outlines) — OFL-clean and
shippable: no outline data is read from, or shipped out of, any external font.
(``reshape_percent_outline`` is a kept variant that derives geometry from
Recursive's own outline; it's no longer wired into the builds.)

Baked-in tweaks (called unconditionally from the builds, not a configurable
option):
  * ``%`` (slash + two oval ring dots), ``/`` and ``\\`` (clean straight
    slashes), ``✓`` (fuller 6-point check), ``•`` (fuller circle), ``$``
    (dollar sign), ``@`` (spiral at-sign) and ``&`` (ampersand) — all drawn
    directly from explicit geometry. The shapes match a popular monospace
    terminal aesthetic, reconstructed here, not borrowed.

For each drawn glyph, the variable build installs gvar masters and the static
build interpolates/shears per instance. ``✓`` ``•`` ``/`` ``\\`` ``%`` use two
point-compatible masters (Regular + Heavy) for full weight variation; ``$``
``@`` ``&`` are single-master (constant across wght; italic shears ~15°) because
the reference design's Regular/Heavy outlines aren't point-compatible for those
glyphs.
"""

from __future__ import annotations

from copy import deepcopy
import math

from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib.tables import otTables as ot
from fontTools.otlLib import builder as otl
from fontTools.varLib.models import VariationModel, supportScalar

AXIS_ORDER = ["MONO", "CASL", "wght", "slnt", "CRSV"]

# Recursive wght axis spans 300..1000; normalise a user weight into [0, 1].
_WGHT_MIN, _WGHT_MAX = 300.0, 1000.0


def _wght_t(wght: float) -> float:
    return max(0.0, min(1.0, (wght - _WGHT_MIN) / (_WGHT_MAX - _WGHT_MIN)))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# --------------------------------------------------------------------------------------
# Geometry helpers


def _contours(end_pts):
    out, start = [], 0
    for end in end_pts:
        out.append((start, end + 1))
        start = end + 1
    return out


def _bbox(coords, sl):
    pts = coords[sl[0]:sl[1]]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _inside(a, b):
    return b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]


# --------------------------------------------------------------------------------------
# percent: two stubby diagonal bars -> one continuous overshooting slash; dots
# shrunk and pushed into the corners.


def percent_params(wght: float) -> dict:
    """Weight-aware reshape parameters for ``%`` (see module docstring)."""
    t = _wght_t(wght)
    return dict(
        dot_scale=_lerp(0.85, 0.82, t),    # shrink dots about their centres
        dot_push=_lerp(50.0, 75.0, t),     # push dots into corners (font units)
        extend=_lerp(62.0, 40.0, t),       # slash overshoot past the dots
        thick_scale=_lerp(1.0, 0.90, t),   # thin the slash a touch when heavy
    )


def reshape_percent_outline(coords, end_pts, flags, *, dot_scale, dot_push,
                            extend, thick_scale):
    """Pure geometry: reshape a ``percent`` outline.

    Input is Recursive's 6-contour ``%`` (two dots = outer ring + inner counter,
    plus two diagonal bars). Output is 5 contours (the two dots unchanged in
    topology, plus ONE straight slash parallelogram). The transform is derived
    entirely from the glyph's own geometry, so it works at any weight/slant.

    Returns ``(new_coords, new_end_pts, new_flags)``.
    """
    slices = _contours(end_pts)
    boxes = [_bbox(coords, s) for s in slices]

    counters, outers, pairs = set(), set(), {}
    for i in range(len(slices)):
        for j in range(len(slices)):
            if i != j and _inside(boxes[i], boxes[j]):
                counters.add(i)
                outers.add(j)
                pairs.setdefault(j, []).append(i)
                break
    bars = [i for i in range(len(slices)) if i not in counters and i not in outers]
    if len(bars) != 2 or len(outers) != 2:
        raise ValueError(
            f"unexpected percent structure: {len(outers)} dots, {len(bars)} bars"
        )

    def centroid(i):
        pts = coords[slices[i][0]:slices[i][1]]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    ca, cb = centroid(bars[0]), centroid(bars[1])
    clo, chi = (ca, cb) if ca[1] < cb[1] else (cb, ca)
    vx, vy = chi[0] - clo[0], chi[1] - clo[1]
    length = math.hypot(vx, vy) or 1.0
    ux, uy = vx / length, vy / length     # along the slash (lower-left -> upper-right)
    px, py = -uy, ux                       # perpendicular (up-left)

    new_coords, new_flags, new_end_pts = [], [], []

    # dots: shrink about their own centre, push along +/- perpendicular into corners
    dot_centers = {o: ((boxes[o][0] + boxes[o][2]) / 2, (boxes[o][1] + boxes[o][3]) / 2)
                   for o in outers}
    top_y = max(c[1] for c in dot_centers.values())
    for o in sorted(outers):
        cx, cy = dot_centers[o]
        sign = 1.0 if cy == top_y else -1.0    # top dot pushes up-left, bottom down-right
        dx, dy = px * dot_push * sign, py * dot_push * sign
        for ci in [o] + pairs[o]:
            a, b = slices[ci]
            for k in range(a, b):
                x, y = coords[k]
                new_coords.append((cx + (x - cx) * dot_scale + dx,
                                   cy + (y - cy) * dot_scale + dy))
                new_flags.append(flags[k])
            new_end_pts.append(len(new_coords) - 1)

    # slash: one straight parallelogram spanning both bars' full extent + overshoot.
    on_pts, all_t = [], []
    for bi in bars:
        a, b = slices[bi]
        for k in range(a, b):
            x, y = coords[k]
            all_t.append(x * ux + y * uy)
            if flags[k] & 1:                    # on-curve corner
                on_pts.append((x * ux + y * uy, x * px + y * py))
    t_min, t_max = min(all_t) - extend, max(all_t) + extend
    s_lo = min(p[1] for p in on_pts)
    s_hi = max(p[1] for p in on_pts)
    s_mid = (s_lo + s_hi) / 2
    s_lo = s_mid + (s_lo - s_mid) * thick_scale
    s_hi = s_mid + (s_hi - s_mid) * thick_scale
    for t, s in [(t_min, s_lo), (t_min, s_hi), (t_max, s_hi), (t_max, s_lo)]:
        new_coords.append((t * ux + s * px, t * uy + s * py))
        new_flags.append(1)
    new_end_pts.append(len(new_coords) - 1)

    return new_coords, new_end_pts, new_flags


# --------------------------------------------------------------------------------------
# Applying a reshape to a glyph: static (one instance) and variable (gvar rebuild).


_CELL = 600  # Moxy is pure monospace: every glyph advances one 600-unit cell.


def _zero_hvar_index(hvar_table):
    """Find an all-zero-delta variation index in HVAR (Recursive has one)."""
    for outer, ivd in enumerate(hvar_table.VarStore.VarData):
        for inner, row in enumerate(ivd.Item):
            if all(d == 0 for d in row):
                return (outer << 16) | inner
    return None


def _write_outline(font, glyph_name, new_coords, new_end_pts, new_flags):
    glyf = font["glyf"]
    g = glyf[glyph_name]
    g.coordinates = g.coordinates.__class__(new_coords)
    g.endPtsOfContours = new_end_pts
    g.flags = g.flags.__class__(bytearray(new_flags))
    g.numberOfContours = len(new_end_pts)
    g.recalcBounds(glyf)
    lsb = g.xMin if g.numberOfContours else 0
    # Pure-mono: pin the advance to the 600 cell. The source glyph's own default
    # may be a proportional width (e.g. JetBrains/Recursive U = 650 in Sans); force
    # 600 and clear any advance VARIATION (gvar phantom deltas are already zeroed;
    # also point HVAR at a zero-delta index) so instancing can't restore the wide
    # advance and break monospacing.
    font["hmtx"].metrics[glyph_name] = (_CELL, lsb)
    if "HVAR" in font:
        awm = font["HVAR"].table.AdvWidthMap
        if awm is not None and hasattr(awm, "mapping"):
            zero_idx = _zero_hvar_index(font["HVAR"].table)
            if zero_idx is not None:
                awm.mapping[glyph_name] = zero_idx


def reshape_percent_instance(font, wght: float = 400.0):
    """Static build: reshape the already-instanced ``percent`` in place."""
    g = font["glyf"]["percent"]
    params = percent_params(wght)
    nc, ne, nf = reshape_percent_outline(
        [tuple(p) for p in g.coordinates],
        list(g.endPtsOfContours),
        list(g.flags),
        **params,
    )
    _write_outline(font, "percent", nc, ne, nf)


def _rebuild_glyph_variable(font, glyph_name, outline_fn, params_fn):
    """Variable build: rebuild a glyph's outline + gvar from reshaped masters.

    ``outline_fn(coords, end_pts, flags, **params) -> (coords, end_pts, flags)``
    must produce identical topology for every master. ``params_fn(loc) -> dict``
    returns the reshape params for a (normalised) master location, allowing
    weight-aware tuning. The master set is derived from the glyph's existing gvar
    regions (so this adapts to whichever axes the glyph actually varies on).
    """
    glyf = font["glyf"]
    gvar = font["gvar"]
    g = glyf[glyph_name]
    base = [tuple(p) for p in g.coordinates]
    npts = len(base)
    tvs = gvar.variations.get(glyph_name, [])
    end_pts = list(g.endPtsOfContours)
    flags = list(g.flags)

    def orig_abs(loc):
        pts = [list(p) for p in base]
        for tv in tvs:
            scalar = supportScalar(loc, tv.axes)
            if not scalar:
                continue
            for i in range(npts):
                d = tv.coordinates[i]
                if d is not None:
                    pts[i][0] += scalar * d[0]
                    pts[i][1] += scalar * d[1]
        return [(x, y) for x, y in pts]

    # Master locations = default (origin) + each tuple's peak (deduped).
    locs = [{}]
    seen = {()}
    for tv in tvs:
        peak = {tag: lo_pk_hi[1] for tag, lo_pk_hi in tv.axes.items()}
        key = tuple(sorted(peak.items()))
        if key not in seen:
            seen.add(key)
            locs.append(peak)

    reshaped = {}
    new_end_pts = new_flags = None
    for loc in locs:
        nc, ne, nf = outline_fn(orig_abs(loc), end_pts, flags, **params_fn(loc))
        reshaped[tuple(sorted(loc.items()))] = nc
        new_end_pts, new_flags = ne, nf

    model = VariationModel(locs, axisOrder=AXIS_ORDER)
    n_new = new_end_pts[-1] + 1
    # getDeltas wants master values in the ORIGINAL `locs` order; returns deltas in
    # model.supports order.
    ordered = [reshaped[tuple(sorted(l.items()))] for l in locs]
    deltas_x = [model.getDeltas([ordered[m][i][0] for m in range(len(ordered))])
                for i in range(n_new)]
    deltas_y = [model.getDeltas([ordered[m][i][1] for m in range(len(ordered))])
                for i in range(n_new)]

    base_idx = model.supports.index({})
    default_coords = [(deltas_x[i][base_idx], deltas_y[i][base_idx]) for i in range(n_new)]
    _write_outline(font, glyph_name, default_coords, new_end_pts, new_flags)

    new_variations = []
    for sidx, support in enumerate(model.supports):
        if support == {}:
            continue
        coords = [(round(deltas_x[i][sidx]), round(deltas_y[i][sidx])) for i in range(n_new)]
        coords += [(0, 0)] * 4  # phantom points (advance is the constant 600 cell)
        new_variations.append(TupleVariation(dict(support), coords))
    gvar.variations[glyph_name] = new_variations


def rebuild_percent_variable(font):
    """Variable build: rebuild ``percent`` with the connected slash + corner dots."""
    _rebuild_glyph_variable(
        font, "percent", reshape_percent_outline,
        lambda loc: percent_params(_WGHT_MIN + loc.get("wght", 0.0) * (_WGHT_MAX - _WGHT_MIN)),
    )


# --------------------------------------------------------------------------------------
# ss08: shortened-terminal C alternate. This is kept as an alternate rather than a
# baked-in change so the VF remains plain Recursive until ss08/moxy is enabled.


def reshape_c_outline(coords, end_pts, flags):
    """Shorten the upper vertical terminal of Recursive's uppercase ``C``.

    Recursive's C is one 63-point contour. Its terminals take a long detour
    down/up the right edge before closing the stroke. Keep that original
    character, including the small outer curve, but move the lower end of each
    vertical leg toward the bowl so the protrusions are shorter. The contour
    topology stays unchanged, making the result safe to interpolate across
    Recursive's existing gvar masters.

    The upper terminal is cut at roughly 47% of its original leg length, which
    matches the cutoff explored in the version-0 screenshot. The lower terminal
    remains unchanged.
    """
    # Recursive 1.085's C is a stable, point-compatible 63-point contour.
    if len(end_pts) != 1 or end_pts[0] != 62 or len(coords) != 63:
        raise ValueError(
            f"unexpected C structure: {len(coords)} points, end points {end_pts}"
        )

    original = [tuple(p) for p in coords]
    out = list(original)

    # Upper terminal: retain the original outer nib (15–19), but shorten the
    # outer vertical leg ending at point 22. The horizontal cap and inner edge
    # (23–32) follow the new cutoff while retaining their original curvature.
    old_inner_y = original[22][1]
    upper_cut = original[19][1] + 0.47 * (old_inner_y - original[19][1])
    upper_scale = (original[19][1] - upper_cut) / (original[19][1] - old_inner_y)
    for i in (20, 21, 22):
        out[i] = (
            original[i][0],
            upper_cut + (original[i][1] - old_inner_y) * upper_scale,
        )
    for i in range(23, 29):
        out[i] = (original[i][0], upper_cut)
    old_inner_edge_start = original[28][1]
    old_inner_edge_end = original[32][1]
    for i in range(29, 33):
        t = (original[i][1] - old_inner_edge_start) / (
            old_inner_edge_end - old_inner_edge_start
        )
        out[i] = (
            original[i][0],
            upper_cut + t * (old_inner_edge_end - upper_cut),
        )

    # The lower terminal is intentionally left at its Recursive coordinates.
    return out, list(end_pts), list(flags)


def reshape_c_glyph_outline(coords, end_pts, flags):
    """Apply the shortened-terminal C shape inside an accented C glyph."""
    slices = _contours(end_pts)
    candidates = []
    for index, sl in enumerate(slices):
        box = _bbox(coords, sl)
        if sl[1] - sl[0] == 63 and box[1] < 0 and box[3] > 600 and box[0] < 100:
            candidates.append(index)
    if len(candidates) != 1:
        raise ValueError(f"could not identify C contour in accented glyph: {end_pts}")

    index = candidates[0]
    start, stop = slices[index]
    local_coords, _, local_flags = reshape_c_outline(
        coords[start:stop], [stop - start - 1], flags[start:stop]
    )
    out = list(coords)
    out[start:stop] = local_coords
    return out, list(end_pts), list(flags)


def _append_feature_mapping(font, feature_tag, mapping):
    """Append a single-sub lookup to an existing feature record."""
    gsub = font["GSUB"].table
    records = [r for r in gsub.FeatureList.FeatureRecord if r.FeatureTag == feature_tag]
    if len(records) != 1:
        raise ValueError(f"expected one {feature_tag} feature record")

    lookup = ot.Lookup()
    lookup.LookupType = 1
    lookup.LookupFlag = 0
    lookup.SubTable = [otl.buildSingleSubstSubtable(mapping)]
    lookup.SubTableCount = 1
    lookup_index = len(gsub.LookupList.Lookup)
    gsub.LookupList.Lookup.append(lookup)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)

    feature = records[0].Feature
    feature.LookupListIndex.append(lookup_index)
    feature.LookupCount = len(feature.LookupListIndex)


def _add_variable_reshaped_alternate(font, source_name, alternate_name, outline_fn):
    """Add a variable alternate by reshaping every source gvar master."""
    glyf = font["glyf"]
    gvar = font["gvar"]
    source = glyf[source_name]
    base = [tuple(p) for p in source.coordinates]
    npts = len(base)
    tvs = gvar.variations.get(source_name, [])
    end_pts = list(source.endPtsOfContours)
    flags = list(source.flags)

    def orig_abs(loc):
        points = [list(p) for p in base]
        for tv in tvs:
            scalar = supportScalar(loc, tv.axes)
            if not scalar:
                continue
            for i in range(npts):
                delta = tv.coordinates[i]
                if delta is not None:
                    points[i][0] += scalar * delta[0]
                    points[i][1] += scalar * delta[1]
        return [(x, y) for x, y in points]

    locs = [{}]
    seen = {()}
    for tv in tvs:
        peak = {tag: lo_pk_hi[1] for tag, lo_pk_hi in tv.axes.items()}
        key = tuple(sorted(peak.items()))
        if key not in seen:
            seen.add(key)
            locs.append(peak)

    reshaped = {}
    new_end_pts = new_flags = None
    for loc in locs:
        nc, ne, nf = outline_fn(orig_abs(loc), end_pts, flags)
        if len(nc) != npts or ne != end_pts or nf != flags:
            raise ValueError(f"{alternate_name}: reshape changed outline topology")
        reshaped[tuple(sorted(loc.items()))] = nc
        new_end_pts, new_flags = ne, nf

    model = VariationModel(locs, axisOrder=AXIS_ORDER)
    ordered = [reshaped[tuple(sorted(loc.items()))] for loc in locs]
    deltas_x = [model.getDeltas([ordered[m][i][0] for m in range(len(ordered))])
                for i in range(npts)]
    deltas_y = [model.getDeltas([ordered[m][i][1] for m in range(len(ordered))])
                for i in range(npts)]

    if alternate_name not in font.getGlyphOrder():
        font.setGlyphOrder(font.getGlyphOrder() + [alternate_name])
    glyf[alternate_name] = deepcopy(source)

    base_idx = model.supports.index({})
    default_coords = [
        (deltas_x[i][base_idx], deltas_y[i][base_idx]) for i in range(npts)
    ]
    _write_outline(font, alternate_name, default_coords, new_end_pts, new_flags)

    new_variations = []
    for sidx, support in enumerate(model.supports):
        if support == {}:
            continue
        deltas = [
            (round(deltas_x[i][sidx]), round(deltas_y[i][sidx]))
            for i in range(npts)
        ]
        deltas += [(0, 0)] * 4
        new_variations.append(TupleVariation(dict(support), deltas))
    gvar.variations[alternate_name] = new_variations


def _add_composite_alternate(font, source_name, alternate_name):
    """Copy a C composite and make its base component use the shortened C."""
    glyf = font["glyf"]
    if alternate_name not in font.getGlyphOrder():
        font.setGlyphOrder(font.getGlyphOrder() + [alternate_name])
    glyph = deepcopy(glyf[source_name])
    for component in glyph.components:
        if component.glyphName == "C":
            component.glyphName = "C.sans"
    glyf[alternate_name] = glyph
    source_advance, source_lsb = font["hmtx"].metrics[source_name]
    font["hmtx"].metrics[alternate_name] = (source_advance, source_lsb)
    font["gvar"].variations[alternate_name] = deepcopy(
        font["gvar"].variations.get(source_name, [])
    )


def add_shortened_c_alternate(font):
    """Add the shortened-terminal C alternates to Recursive's ``ss08`` feature."""
    if "C.sans" in font.getGlyphOrder():
        return

    _add_variable_reshaped_alternate(font, "C", "C.sans", reshape_c_outline)
    for source_name in ("Cdotaccent", "Ccaron"):
        _add_variable_reshaped_alternate(
            font, source_name, f"{source_name}.sans", reshape_c_glyph_outline
        )
    for source_name in ("Ccedilla", "Cacute", "Ccircumflex", "uni1E08"):
        _add_composite_alternate(font, source_name, f"{source_name}.sans")

    _append_feature_mapping(
        font,
        "ss08",
        {
            "C": "C.sans",
            "Ccedilla": "Ccedilla.sans",
            "Cacute": "Cacute.sans",
            "Ccircumflex": "Ccircumflex.sans",
            "Cdotaccent": "Cdotaccent.sans",
            "Ccaron": "Ccaron.sans",
            "uni1E08": "uni1E08.sans",
        },
    )


# --------------------------------------------------------------------------------------
# Italic helper: shear upright coords by Recursive's ~15° lean to produce the
# slnt (italic) master. Used by the draw helpers below.

_SHEAR_15 = math.tan(math.radians(15))   # Recursive slnt=-15 ≈ 15° forward lean


def _shear(coords, shear):
    return [(x + shear * y, y) for x, y in coords]


def _install_variable_glyph(font, glyph_name, locs, coords_by_loc, end_pts, flags):
    """Replace a glyph's outline + gvar from externally-built, point-compatible
    masters. ``locs`` are normalised locations; ``coords_by_loc`` is keyed by
    ``tuple(sorted(loc.items()))``."""
    n = end_pts[-1] + 1
    model = VariationModel(locs, axisOrder=AXIS_ORDER)
    ordered = [coords_by_loc[tuple(sorted(l.items()))] for l in locs]
    deltas_x = [model.getDeltas([ordered[m][i][0] for m in range(len(ordered))])
                for i in range(n)]
    deltas_y = [model.getDeltas([ordered[m][i][1] for m in range(len(ordered))])
                for i in range(n)]
    base_idx = model.supports.index({})
    default_coords = [(deltas_x[i][base_idx], deltas_y[i][base_idx]) for i in range(n)]
    _write_outline(font, glyph_name, default_coords, end_pts, flags)

    new_variations = []
    for sidx, support in enumerate(model.supports):
        if support == {}:
            continue
        coords = [(round(deltas_x[i][sidx]), round(deltas_y[i][sidx])) for i in range(n)]
        coords += [(0, 0)] * 4  # phantom points (advance stays the 600 cell)
        new_variations.append(TupleVariation(dict(support), coords))
    font["gvar"].variations[glyph_name] = new_variations


# --------------------------------------------------------------------------------------
# Baked-in Moxy glyph tweaks. Called unconditionally from the builds.
#
# ``%`` ``/`` ``\\`` ``✓`` ``•`` ``$`` ``@`` ``&`` are all drawn below from
# OFL-clean geometry (no external outline is read or shipped).


# --------------------------------------------------------------------------------------
# Fuller ✓ and •, clean / and \, and the Moxy % — DRAWN directly (pure
# geometry), not grafted.
#
# The shapes match a popular monospace terminal design (measured once,
# cap-scaled into Moxy's 700-cap / 600 cell), but are reconstructed from the
# explicit coordinates below — nothing is read from, or shipped out of, any
# external font. This keeps them OFL-clean.
# Two point-compatible masters (Regular + Heavy) give the weight variation; the
# italic master is the upright sheared by Recursive's ~15° lean.

# ✓ (U+2713): a clean 6-point checkmark (all straight edges). The bottom point,
# the right tip and the left tip (P1/P2/P6) hold across weight; the inner edge
# (P3/P4/P5) thickens the stroke from Regular → Heavy.
_CHECK_LIGHT = [
    (217.0, 100.0), (607.0, 492.0), (554.0, 548.0),
    (217.0, 213.0), (46.0, 380.0), (-7.0, 324.0),
]
_CHECK_HEAVY = [
    (217.0, 100.0), (607.0, 492.0), (498.0, 601.0),
    (217.0, 320.0), (102.0, 433.0), (-7.0, 324.0),
]
_CHECK_END_PTS = [5]
_CHECK_FLAGS = [1] * 6  # every point on-curve (straight edges)

# • (U+2022): a true circle, centred in the 600 cell. Centre-y and radius are
# tuned across Regular → Heavy; drawn as an 8-segment TrueType
# quadratic, so it stays a perfectly round, point-compatible circle at any weight.
_BULLET_CX = 300.0
_BULLET_LIGHT = (310.5, 205.0)   # (centre-y, radius)
_BULLET_HEAVY = (311.9, 226.1)

# / (slash) and \ (backslash): a clean 4-point parallelogram (one slanted stroke,
# no brushy flair). Corners tuned across Regular → Heavy, cap-scaled
# and centred in the cell; the stroke thickens with weight. Backslash is the
# mirror; its composites (backslash.code, .case, the \b \n \r \t \v escape
# ligatures) reference ``backslash``, so they inherit.
_SLASH_LIGHT = [(169.5, -66.5), (511.0, 766.5), (430.0, 766.5), (89.0, -66.5)]
_SLASH_HEAVY = [(223.8, -131.0), (549.3, 831.0), (371.3, 831.0), (50.7, -131.0)]
_BACKSLASH_LIGHT = [(430.5, -66.5), (511.0, -66.5), (170.0, 766.5), (89.0, 766.5)]
_BACKSLASH_HEAVY = [(376.2, -131.0), (549.3, -131.0), (228.7, 831.0), (50.7, 831.0)]
_SLASH_END_PTS = [3]
_SLASH_FLAGS = [1] * 4  # every point on-curve (straight edges)


def _circle_quad(cx, cy, r, segments=8):
    """A circle as a TrueType quadratic contour, drawn clockwise.

    Places ``segments`` on-curve points evenly around the circle, each followed
    by one off-curve control on the bisector at radius ``r / cos(pi/segments)``
    (the tangent-intersection radius) so the quadratic arcs hug the true circle.
    Returns ``(coords, flags)`` with on/off-curve interleaved.
    """
    coords, flags = [], []
    step = 2 * math.pi / segments
    rc = r / math.cos(step / 2)
    for i in range(segments):
        a = -i * step                                   # clockwise
        coords.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        flags.append(1)                                 # on-curve
        ac = a - step / 2
        coords.append((cx + rc * math.cos(ac), cy + rc * math.sin(ac)))
        flags.append(0)                                 # off-curve control
    return coords, flags


def _ellipse_quad(cx, cy, rx, ry, segments=8, clockwise=True):
    """An ellipse as a TrueType quadratic contour (like ``_circle_quad`` but with
    separate rx/ry and a winding direction). Counters pass ``clockwise=False`` so
    they wind opposite the outer ring and cut a hole under non-zero fill."""
    coords, flags = [], []
    step = 2 * math.pi / segments
    kc = 1.0 / math.cos(step / 2)                       # bisector control scale
    for i in range(segments):
        a = (-i if clockwise else i) * step
        coords.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        flags.append(1)                                 # on-curve
        ac = a + (-step / 2 if clockwise else step / 2)
        coords.append((cx + rx * kc * math.cos(ac), cy + ry * kc * math.sin(ac)))
        flags.append(0)                                 # off-curve control
    return coords, flags


def _bullet_master(spec):
    """Build one bullet master (coords, end_pts, flags) from a (cy, r) spec."""
    cy, r = spec
    coords, flags = _circle_quad(_BULLET_CX, cy, r)
    return coords, [len(coords) - 1], flags


# % (U+0025): the Moxy style — a diagonal slash plus two vertical-oval ring dots
# (each an outer ellipse with an inner counter), point-symmetric about the cell
# centre. Tuned across Regular → Heavy; the counters shrink as the
# ring wall thickens with weight. Each spec: a 4-corner slash + four ellipses
# ordered (top-left outer, top-left inner, bottom-right outer, bottom-right inner).
_PERCENT_LIGHT = dict(
    slash=[(607.1, 700.0), (-7.1, 75.2), (-7.1, 0.0), (607.1, 624.8)],
    rings=[(127.1, 535.8, 132.7, 173.4), (127.1, 535.8, 70.6, 112.3),
           (472.9, 164.2, 132.7, 173.4), (472.9, 164.2, 70.6, 112.3)],
)
_PERCENT_HEAVY = dict(
    slash=[(607.1, 700.0), (-7.1, 77.1), (-7.1, 0.0), (607.1, 622.9)],
    rings=[(150.1, 539.7, 147.5, 179.2), (150.1, 539.7, 46.6, 83.4),
           (449.9, 159.4, 147.5, 179.2), (449.9, 159.4, 46.6, 83.4)],
)


def _percent_master(spec, segments=8):
    """Build % (coords, end_pts, flags) from a spec. Outer rings wind clockwise;
    inner counters wind opposite so they cut holes. Slash is a 4-point bar."""
    coords, flags, end_pts = [], [], []
    for j, (cx, cy, rx, ry) in enumerate(spec["rings"]):
        inner = (j % 2 == 1)
        ec, ef = _ellipse_quad(cx, cy, rx, ry, segments, clockwise=not inner)
        coords += ec; flags += ef; end_pts.append(len(coords) - 1)
    for p in spec["slash"]:
        coords.append(p); flags.append(1)
    end_pts.append(len(coords) - 1)
    return coords, end_pts, flags


def _draw_glyph_variable(font, glyph_name, light, heavy, end_pts, flags):
    """Install a drawn glyph + gvar from point-compatible light/heavy masters,
    varying on wght (light→heavy) and slnt (upright sheared ~15°). Pass
    ``light == heavy`` for a single-master glyph (constant across wght)."""
    locs = [{}, {"wght": 1.0}, {"slnt": -1.0}, {"wght": 1.0, "slnt": -1.0}]
    coords_by_loc = {
        (): light,
        (("wght", 1.0),): heavy,
        (("slnt", -1.0),): _shear(light, _SHEAR_15),
        (("slnt", -1.0), ("wght", 1.0)): _shear(heavy, _SHEAR_15),
    }
    _install_variable_glyph(font, glyph_name, locs, coords_by_loc, end_pts, flags)


# --------------------------------------------------------------------------------------
# Weight calibration for the seven hand-drawn glyphs @ $ & 2 4 5 7.
#
# These glyphs were drawn as a Regular-ish "light" and a Bold-ish "heavy" master
# but were anchored to the wght axis as if light=300 and heavy=1000 — so at
# Recursive's Regular (the Moxy default, wght 375) they rendered a too-heavy
# blend, and they didn't sit at the same visual stroke weight as Recursive's own
# glyphs. Calibration retargets each glyph's stroke to Recursive's reference stem
# (measured perpendicular thickness, in 600-cell raster units):
#
#     thin  ≈ 50   at wght 300 (Light)
#     light ≈ 81   at wght 375 (Regular / Moxy default)
#     heavy ≈ 140  (≈ Recursive Bold; the curvy glyphs distort past this)
#
# Each master is the glyph's own light→heavy line blended to hit a target stem
# (pure interpolation along an existing axis = no new distortion). Coefficients
# were found offline against Recursive's stem; see scripts/dev/calibrate_stems.py
# to reproduce or re-tune them. ``@`` caps at its existing heavy (1.0) because its
# spiral self-intersects past that; it therefore reads a touch lighter at Bold.
#
# VF: three wght masters (thin@300, light@375=default, heavy@1000); Recursive's
# native avar then follows the same weight curve as every other glyph. Static:
# light@375 plus a Bold tuned to Recursive's Bold stem (see _static_calib_frac).
_CALIB = {
    # name:        (thin,  light,  heavy)   blend factors on the light→heavy line
    "two":         (-0.40,  0.04,  0.89),
    "four":        (-0.35,  0.03,  0.63),
    "five":        (-0.44,  0.04,  0.81),
    "seven":       (-0.39,  0.00,  0.70),
    "ampersand":   (-0.45,  0.11,  1.05),
    "at":          (-0.36,  0.66,  1.00),
    "dollar":      (-0.52,  0.00,  0.85),
}


def _blend(a, b, t):
    """Linear blend of two point-compatible coordinate lists."""
    return [(a[i][0] + (b[i][0] - a[i][0]) * t,
             a[i][1] + (b[i][1] - a[i][1]) * t) for i in range(len(a))]


def _widen_dollar_bar(coords, left_x, right_x, target_w, tol=2.0):
    """Push the ``$`` central bar's edges outward to ``target_w``.

    The bar barely thickens along $'s own light→heavy line, so a blend alone
    leaves it thinner than the bowls. Points on the bar's left/right edge (and
    the counter edges that sit against it) share the two edge x-values, so we
    shift those symmetrically about the bar centre."""
    d = (target_w - (right_x - left_x)) / 2.0
    out = []
    for x, y in coords:
        if abs(x - left_x) <= tol:
            out.append((x - d, y))
        elif abs(x - right_x) <= tol:
            out.append((x + d, y))
        else:
            out.append((x, y))
    return out


def _calib_masters(name, light, heavy):
    """Return (thin, light, heavy) calibrated masters for a drawn glyph."""
    if name == "dollar":
        light = _widen_dollar_bar(light, 274.8, 332.5, 84.0)
        heavy = _widen_dollar_bar(heavy, 269.9, 338.3, 150.0)
    ct, cl, ch = _CALIB[name]
    return _blend(light, heavy, ct), _blend(light, heavy, cl), _blend(light, heavy, ch)


def _draw_glyph_variable3(font, glyph_name, thin, light, heavy, end_pts, flags):
    """Install a drawn glyph + gvar from three point-compatible wght masters
    (thin@wght-min, light@default, heavy@wght-max) plus the slnt shear. MUST be
    called AFTER the VF default is rebased to 375, so ``{}`` (the default) is the
    light master and ``{wght:-1}`` / ``{wght:1}`` are wght 300 / 1000."""
    locs = [
        {}, {"wght": 1.0}, {"wght": -1.0},
        {"slnt": -1.0}, {"wght": 1.0, "slnt": -1.0}, {"wght": -1.0, "slnt": -1.0},
    ]
    coords_by_loc = {
        (): light,
        (("wght", 1.0),): heavy,
        (("wght", -1.0),): thin,
        (("slnt", -1.0),): _shear(light, _SHEAR_15),
        (("slnt", -1.0), ("wght", 1.0)): _shear(heavy, _SHEAR_15),
        (("slnt", -1.0), ("wght", -1.0)): _shear(thin, _SHEAR_15),
    }
    _install_variable_glyph(font, glyph_name, locs, coords_by_loc, end_pts, flags)



def draw_checkmark(font):
    """Variable build: draw ``✓`` (U+2713) as Moxy's fuller 6-point check.

    Recursive's own check is a brushy 42-point stroke; this is a clean 6-point
    check that sits better next to code. No composites reference it."""
    _draw_glyph_variable(font, "uni2713", _CHECK_LIGHT, _CHECK_HEAVY,
                         _CHECK_END_PTS, _CHECK_FLAGS)


def draw_bullet(font):
    """Variable build: draw ``•`` (U+2022) as Moxy's fuller circle.

    A fuller, perfectly round bullet. The composites ``bullet.case`` and
    ``uni2219`` (bullet operator) reference ``bullet`` as a component, so they
    inherit this automatically."""
    light, end_pts, flags = _bullet_master(_BULLET_LIGHT)
    heavy, _, _ = _bullet_master(_BULLET_HEAVY)
    _draw_glyph_variable(font, "bullet", light, heavy, end_pts, flags)


def draw_slash(font):
    """Variable build: draw ``/`` as Moxy's clean straight slash (no brushy
    flair) — a 4-point parallelogram that thickens with weight."""
    _draw_glyph_variable(font, "slash", _SLASH_LIGHT, _SLASH_HEAVY,
                         _SLASH_END_PTS, _SLASH_FLAGS)


def draw_backslash(font):
    """Variable build: draw ``\\`` as Moxy's clean straight backslash.

    The composites (backslash.code, .case, and the \\b \\n \\r \\t \\v escape
    ligatures) reference ``backslash`` as a component, so they inherit."""
    _draw_glyph_variable(font, "backslash", _BACKSLASH_LIGHT, _BACKSLASH_HEAVY,
                         _SLASH_END_PTS, _SLASH_FLAGS)


def draw_percent(font):
    """Variable build: draw ``%`` as a diagonal slash + two oval ring dots."""
    light, end_pts, flags = _percent_master(_PERCENT_LIGHT)
    heavy, _, _ = _percent_master(_PERCENT_HEAVY)
    _draw_glyph_variable(font, "percent", light, heavy, end_pts, flags)


# --------------------------------------------------------------------------------------
# @ & $ — DRAWN directly (OFL-clean geometry), matching the target monospace
# aesthetic.
#
# The reference design's Regular and Heavy masters are NOT point-compatible for
# these glyphs (different point counts/structure), so the two-master light/heavy
# trick used for ✓ • / \ % doesn't apply. Instead each glyph is drawn from a
# SINGLE master (derived via cu2qu from a reference outline, cap-scaled into
# Moxy's 700-cap / 600 cell, then hardcoded here so the build reads no external
# font). The glyph stays constant across wght; italic still shears by Recursive's
# ~15°. Pass light == heavy to the existing helpers to get single-master
# behaviour.

# $ (U+0024): S-curve with two bowls and a central vertical bar that overshoots
# the top and bottom. 3 contours: outer S+bar, top-bowl counter, bottom-bowl
# counter (counters wind opposite the outer so non-zero fill cuts the holes).
_DOLLAR_LIGHT = [
    # contour 0 — outer S + central bar (points 0..41)
    (55.5, 184.8), (59.4, 127.6), (114.7, 41.2), (210.7, -9.7),
    (274.8, -14.6), (274.8, -68.4), (332.5, -68.4), (332.5, -14.1),
    (397.5, -8.7), (492.6, 43.7), (544.5, 131.5), (544.5, 189.2),
    (544.5, 241.6), (504.7, 316.8), (418.4, 368.7), (348.5, 385.7),
    (332.5, 390.0), (332.5, 641.8), (384.4, 634.5), (449.4, 572.9),
    (455.7, 523.9), (532.4, 523.9), (529.5, 577.3), (478.5, 659.3),
    (390.7, 708.7), (332.5, 714.1), (332.5, 768.4), (274.8, 768.4),
    (274.8, 714.1), (213.2, 709.2), (122.5, 658.8), (73.0, 575.3),
    (73.0, 520.5), (73.0, 444.8), (165.6, 350.7), (264.6, 326.5),
    (274.8, 324.0), (274.8, 58.2), (235.0, 63.1), (173.9, 96.0),
    (137.0, 149.9), (133.1, 184.8),
    # contour 1 — top-bowl counter (points 42..48)
    (152.5, 522.9), (152.5, 572.9), (217.5, 635.5), (274.8, 641.8),
    (274.8, 404.6), (208.8, 423.0), (152.5, 477.8),
    # contour 2 — bottom-bowl counter (points 49..56)
    (465.4, 185.3), (465.4, 150.9), (432.4, 97.0), (372.8, 63.1),
    (332.5, 58.2), (332.5, 309.5), (402.8, 291.5), (465.4, 232.8),
]
_DOLLAR_HEAVY = [
    (18.2, 194.5), (20.6, 133.4), (83.6, 41.2), (194.7, -12.6),
    (269.9, -17.0), (269.9, -68.4), (338.3, -68.4), (338.3, -16.5),
    (414.5, -10.2), (523.1, 47.5), (581.8, 144.6), (581.8, 209.6),
    (581.8, 264.4), (539.6, 342.0), (451.4, 393.9), (338.3, 417.7),
    (338.3, 417.7), (338.3, 595.7), (377.1, 587.9), (427.1, 541.4),
    (431.5, 506.9), (569.2, 506.9), (567.3, 564.7), (508.1, 654.4),
    (405.8, 710.2), (338.3, 716.5), (338.3, 768.4), (269.9, 768.4),
    (269.9, 717.0), (198.1, 711.6), (92.4, 654.9), (34.2, 560.8),
    (34.2, 499.2), (34.2, 499.2), (224.3, 299.3), (269.9, 289.6),
    (269.9, 289.6), (269.9, 103.8), (222.9, 110.6), (222.9, 110.6),
    (164.2, 158.6), (159.8, 194.5),
    (181.2, 511.8), (181.2, 545.3), (228.7, 590.4), (269.9, 596.7),
    (269.9, 432.7), (222.9, 445.3), (181.2, 483.2),
    (435.8, 191.1), (435.8, 157.2), (382.5, 110.6), (382.5, 110.6),
    (338.3, 103.8), (338.3, 274.6), (390.2, 261.0), (435.8, 221.2),
]
_DOLLAR_END_PTS = [41, 48, 56]
_DOLLAR_FLAGS = [
    1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1,
    0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1,
    1, 0, 0, 1, 1, 0, 0,
    1, 0, 0, 0, 1, 1, 0, 0,
]


def draw_dollar(font):
    """Variable build: draw ``$`` (U+0024) as Moxy's reference dollar sign.

    Calibrated three-master (thin@300, light@375, heavy@1000) so it matches
    Recursive's stroke weight; the central bar is widened to the bowls. MUST be
    drawn after the VF default is rebased to 375. OFL-clean hardcoded geometry."""
    thin, light, heavy = _calib_masters("dollar", _DOLLAR_LIGHT, _DOLLAR_HEAVY)
    _draw_glyph_variable3(font, "dollar", thin, light, heavy,
                          _DOLLAR_END_PTS, _DOLLAR_FLAGS)


# @ (U+0040): the modern single-contour spiral at-sign — one continuous path
# that forms the outer ring, swings in to become the inner counter wall, and
# curls into the central tail. Two-master (1 contour, 50 points). The heavy
# master is hand-built from the Regular's topology with coordinates mapped from
# the reference Heavy. Bold thickens. The composite ``at.case`` references
# ``at`` as a component, so it inherits.
_AT_LIGHT = [
    (310.9, -96.0), (346.8, -96.0), (412.3, -85.4), (429.8, -77.1),
    (429.8, -19.9), (419.6, -24.7), (384.2, -33.0), (341.5, -37.4),
    (319.6, -37.4), (209.0, -37.4), (104.7, 113.5), (104.7, 274.6),
    (104.7, 349.8), (104.7, 508.4), (201.3, 656.8), (303.2, 656.8),
    (398.7, 656.8), (496.2, 531.2), (496.2, 407.0), (496.2, 270.7),
    (496.2, 234.3), (468.6, 204.2), (435.1, 204.2), (355.5, 204.2),
    (355.5, 405.5), (355.5, 432.7), (330.3, 464.7), (309.0, 464.7),
    (287.6, 464.7), (261.9, 432.7), (261.9, 405.5), (261.9, 207.1),
    (261.9, 180.5), (293.9, 148.4), (321.1, 148.4), (444.8, 148.4),
    (497.2, 148.4), (555.4, 213.9), (555.4, 272.6), (555.4, 417.7),
    (555.4, 513.7), (496.7, 646.6), (384.2, 715.5), (303.6, 715.5),
    (176.5, 715.5), (44.6, 531.2), (44.6, 354.1), (44.6, 263.4),
    (44.6, 86.3), (179.9, -96.0),
]
_AT_HEAVY = [
    (326.7, -101.4), (345.1, -101.4), (421.8, -89.7), (432.9, -85.4),
    (419.3, -11.6), (419.3, -11.6), (363.5, -17.9), (330.1, -17.9),
    (330.1, -17.9), (193.3, 16.0), (143.3, 89.7), (120.5, 292.0),
    (120.5, 332.8), (140.4, 530.7), (253.9, 634.5), (304.4, 634.5),
    (368.9, 634.5), (448.0, 579.2), (484.3, 360.4), (484.3, 245.9),
    (484.3, 245.9), (462.0, 199.9), (436.3, 199.9), (379.6, 199.9),
    (379.6, 418.2), (379.6, 418.2), (343.2, 490.9), (313.1, 490.9),
    (283.5, 490.9), (246.6, 418.2), (246.6, 418.2), (246.6, 199.4),
    (246.6, 166.9), (283.5, 126.6), (313.1, 126.6), (458.1, 126.6),
    (513.0, 126.6), (569.7, 192.6), (569.7, 255.6), (569.7, 381.8),
    (569.7, 553.0), (448.0, 579.2), (440.2, 718.9), (305.8, 718.9),
    (210.7, 718.9), (30.3, 462.8), (30.3, 327.4), (30.3, 282.3),
    (30.3, 149.4), (223.8, -101.4),
]
_AT_END_PTS = [49]
_AT_FLAGS = [
    1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 1,
    1, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1,
    0, 0,
]


def draw_at(font):
    """Variable build: draw ``@`` (U+0040) as Moxy's reference at-sign (spiral).

    Calibrated three-master (thin@300, light@375, heavy@1000); the heavy caps at
    the existing master because the spiral self-intersects past it, so ``@`` reads
    a touch lighter at Bold. MUST be drawn after the VF default is rebased to 375.
    OFL-clean hardcoded geometry. The composite ``at.case`` references ``at`` as a
    component, so it inherits."""
    thin, light, heavy = _calib_masters("at", _AT_LIGHT, _AT_HEAVY)
    _draw_glyph_variable3(font, "at", thin, light, heavy,
                          _AT_END_PTS, _AT_FLAGS)


# & (U+0026): the intricate ampersand — a figure-eight "et" shape with two
# enclosed counters (the upper loop and the lower loop). Two-master (3 contours,
# 64 points). The heavy master is hand-built from the Regular's topology with
# coordinates mapped from the reference Heavy. Bold thickens. Counters wind
# opposite the outer so non-zero fill cuts the holes.
_AMP_LIGHT = [
    # contour 0 — outer body (points 0..36)
    (482.6, 0.0), (578.7, 0.0), (470.5, 131.5), (495.3, 174.6),
    (521.4, 281.4), (523.4, 345.9), (523.4, 353.2), (453.0, 353.2),
    (453.0, 348.8), (450.1, 253.2), (423.9, 191.6), (273.1, 381.3),
    (321.1, 412.8), (378.3, 470.1), (403.6, 529.7), (403.6, 564.7),
    (403.6, 609.3), (364.3, 676.7), (294.4, 714.6), (248.8, 714.6),
    (202.7, 714.6), (131.9, 676.7), (92.1, 609.3), (92.1, 564.7),
    (92.1, 526.8), (130.9, 442.9), (170.7, 393.9), (148.4, 378.9),
    (21.3, 295.9), (21.3, 181.4), (21.3, 138.7), (51.9, 67.4),
    (107.7, 15.5), (183.8, -12.6), (229.9, -12.6), (343.4, -12.6),
    (426.9, 71.8),
    # contour 1 — upper-loop counter (points 37..51)
    (248.3, 646.6), (272.1, 646.6), (309.9, 624.8), (331.8, 587.5),
    (331.8, 563.7), (331.8, 538.0), (313.3, 495.8), (269.7, 454.1),
    (231.8, 428.8), (195.5, 472.5), (164.9, 534.1), (164.9, 563.7),
    (164.9, 587.5), (186.7, 624.8), (224.6, 646.6),
    # contour 2 — lower-loop counter (points 52..63)
    (192.6, 327.9), (212.0, 340.5), (384.7, 124.7), (358.0, 93.1),
    (279.9, 59.7), (232.8, 59.7), (193.0, 59.7), (132.4, 91.2),
    (98.9, 148.0), (98.9, 185.3), (98.9, 228.5), (144.5, 298.3),
]
_AMP_HEAVY = [
    (433.6, 0.0), (596.5, 12.2), (486.0, 150.2), (506.7, 181.4),
    (531.3, 249.7), (541.3, 310.1), (541.3, 346.1), (465.5, 362.4),
    (411.3, 349.8), (411.3, 322.7), (405.7, 281.4), (399.2, 267.0),
    (307.5, 372.6), (367.3, 416.0), (422.0, 507.3), (422.0, 559.9),
    (406.8, 621.7), (342.6, 689.4), (269.0, 714.1), (210.3, 714.1),
    (130.3, 685.9), (65.8, 615.5), (53.8, 555.8), (53.8, 509.4),
    (92.6, 424.9), (130.8, 380.2), (93.5, 357.8), (33.6, 307.2),
    (-6.8, 219.4), (-6.8, 162.4), (9.2, 102.4), (58.9, 36.4),
    (135.6, -4.5), (196.9, -14.1), (251.8, -14.1), (349.4, 15.7),
    (392.9, 47.1),
    (237.7, 595.7), (255.6, 595.7), (277.4, 578.5), (290.1, 557.3),
    (290.1, 539.0), (290.1, 520.7), (269.3, 485.1), (248.6, 462.3),
    (229.3, 460.0), (210.0, 480.7), (189.1, 517.3), (185.3, 535.8),
    (185.3, 552.3), (191.7, 572.1), (215.3, 595.7),
    (187.2, 279.9), (197.8, 287.4), (298.1, 170.3), (294.0, 120.1),
    (250.9, 111.1), (217.6, 111.1), (187.1, 121.2), (156.4, 147.5),
    (141.6, 179.1), (141.6, 201.8), (143.9, 225.7), (166.4, 266.3),
]
_AMP_END_PTS = [36, 51, 63]
_AMP_FLAGS = [
    1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1,
    0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 0, 1,
    1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0,
    1, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0,
]


def draw_ampersand(font):
    """Variable build: draw ``&`` (U+0026) as Moxy's reference ampersand.

    Calibrated three-master (thin@300, light@375, heavy@1000) so it matches
    Recursive's stroke weight. MUST be drawn after the VF default is rebased to
    375. OFL-clean hardcoded geometry."""
    thin, light, heavy = _calib_masters("ampersand", _AMP_LIGHT, _AMP_HEAVY)
    _draw_glyph_variable3(font, "ampersand", thin, light, heavy,
                          _AMP_END_PTS, _AMP_FLAGS)


# --------------------------------------------------------------------------------------
# Numerals 2 4 5 7 — DRAWN directly (OFL-clean geometry), matching the target
# monospace numeral aesthetic. These override Recursive's own numerals (they are
# not, and never were, grafted). ``4`` and ``7`` are point-compatible across the
# reference Regular/Heavy weights, so they get two masters (Bold thickens); ``2``
# and ``5`` are not point-compatible, so they are single-master (constant across
# wght; italic shears ~15°). No composites reference the base numerals, so
# overriding ``two``/``four``/``five``/``seven`` in place is safe (the fraction
# glyphs like ``twothirds`` are independently drawn).

# 2 (U+0032): a curved two with a top bowl, diagonal shoulder, and flat base.
# Two-master (1 contour, 38 points). The reference design's Regular/Heavy
# outlines aren't point-compatible (different point counts), so the heavy master
# is hand-built from the Regular's topology with coordinates mapped/interpolated
# from the reference Heavy. Bold thickens.
_TWO_LIGHT = [
    (76.6, 503.0), (76.6, 500.1), (159.1, 500.1), (159.1, 503.0),
    (159.1, 544.3), (192.6, 605.4), (252.7, 639.4), (293.0, 639.4),
    (333.7, 639.4), (394.4, 608.3), (427.3, 552.5), (427.3, 514.7),
    (427.3, 493.8), (417.6, 456.5), (393.4, 414.3), (350.7, 359.9),
    (317.2, 322.6), (80.5, 59.2), (80.5, 0.0), (523.4, 0.0),
    (523.4, 77.6), (202.7, 77.6), (202.7, 85.9), (367.7, 265.3),
    (409.4, 310.9), (465.2, 381.3), (498.2, 439.0), (512.2, 490.9),
    (512.2, 518.1), (512.2, 561.7), (480.7, 634.0), (423.0, 686.4),
    (343.4, 714.6), (295.4, 714.6), (247.4, 714.6), (167.3, 683.5),
    (108.6, 626.7), (76.6, 549.1),
]
_TWO_HEAVY = [
    (28.8, 480.7), (28.8, 477.8), (191.8, 477.8), (191.8, 481.2),
    (191.8, 510.3), (217.5, 554.5), (263.6, 579.7), (293.7, 579.7),
    (336.9, 579.7), (389.3, 532.6), (389.3, 513.2), (389.3, 493.8),
    (389.3, 477.8), (377.1, 446.3), (348.5, 408.0), (298.1, 357.0),
    (260.2, 322.1), (39.0, 118.8), (39.0, 0.0), (571.2, 0.0),
    (571.2, 138.7), (276.2, 138.7), (276.2, 148.0), (391.7, 249.3),
    (453.3, 303.7), (528.0, 390.0), (561.5, 467.2), (561.5, 486.8),
    (561.5, 506.4), (561.5, 553.0), (524.1, 629.2), (454.7, 684.5),
    (358.7, 714.1), (300.0, 714.1), (239.4, 714.1), (139.4, 680.6),
    (67.6, 619.0), (28.8, 533.1),
]
_TWO_END_PTS = [37]
_TWO_FLAGS = [1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
              0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0]


def draw_two(font):
    """Variable build: draw ``2`` (U+0032) overriding Recursive's numeral.

    Calibrated three-master (thin@300, light@375, heavy@1000) so it matches
    Recursive's stroke weight. MUST be drawn after the VF default is rebased to
    375. OFL-clean hardcoded geometry."""
    thin, light, heavy = _calib_masters("two", _TWO_LIGHT, _TWO_HEAVY)
    _draw_glyph_variable3(font, "two", thin, light, heavy,
                          _TWO_END_PTS, _TWO_FLAGS)


# 4 (U+0034): an open four — vertical stem, diagonal flag, horizontal crossbar.
# TWO-master (point-compatible Regular + Heavy), so Bold thickens. 1 contour,
# 16 points, all on-curve (straight edges). Derived from reference outlines,
# cap-scaled into the 600 cell.
_FOUR_LIGHT = [
    (366.9, 0.0), (445.0, 0.0), (445.0, 148.0), (552.3, 148.0),
    (552.3, 223.1), (445.5, 223.1), (445.5, 422.0), (367.9, 422.0),
    (367.9, 222.2), (138.5, 222.2), (138.5, 228.5), (372.8, 700.0),
    (285.4, 700.0), (47.7, 217.3), (47.7, 148.0), (366.9, 148.0),
]
_FOUR_HEAVY = [
    (328.9, 0.0), (496.7, 0.0), (496.7, 123.2), (579.2, 123.2),
    (579.2, 255.2), (492.8, 255.2), (492.8, 422.0), (335.7, 422.0),
    (335.7, 259.0), (209.5, 259.0), (209.5, 269.7), (393.9, 700.0),
    (214.9, 700.0), (20.8, 258.1), (20.8, 123.2), (328.9, 123.2),
]
_FOUR_END_PTS = [15]
_FOUR_FLAGS = [1] * 16


def draw_four(font):
    """Variable build: draw ``4`` (U+0034) overriding Recursive's numeral.

    Calibrated three-master (thin@300, light@375, heavy@1000) so it matches
    Recursive's stroke weight. MUST be drawn after the VF default is rebased to
    375. OFL-clean hardcoded geometry."""
    thin, light, heavy = _calib_masters("four", _FOUR_LIGHT, _FOUR_HEAVY)
    _draw_glyph_variable3(font, "four", thin, light, heavy,
                          _FOUR_END_PTS, _FOUR_FLAGS)


# 5 (U+0035): a curved five — top horizontal bar, descending shoulder into a
# rounded bowl, flat base. Two-master (1 contour, 39 points, has curves). The
# reference design's Regular/Heavy outlines aren't point-compatible (different
# point counts), so the heavy master is hand-built from the Regular's topology
# with coordinates mapped from the reference Heavy. Bold thickens.
_FIVE_LIGHT = [
    (295.6, -14.1), (349.0, -14.1), (436.8, 19.9), (499.9, 83.4),
    (534.3, 170.8), (534.3, 223.6), (534.3, 275.5), (502.3, 360.9),
    (443.6, 424.0), (363.1, 457.9), (314.6, 457.9), (220.9, 457.9),
    (168.5, 394.4), (160.8, 394.4), (180.2, 622.9), (495.5, 622.9),
    (495.5, 700.0), (112.8, 700.0), (77.3, 304.6), (158.4, 304.6),
    (179.2, 342.0), (253.4, 382.7), (300.5, 382.7), (345.6, 382.7),
    (413.0, 342.5), (450.9, 269.7), (450.9, 221.7), (450.9, 174.2),
    (413.5, 102.8), (345.6, 63.1), (300.5, 63.1), (259.7, 63.1),
    (193.3, 94.6), (152.0, 150.4), (148.2, 186.8), (65.7, 186.8),
    (69.6, 126.6), (129.2, 36.4), (230.6, -14.1),
]
_FIVE_HEAVY = [
    (297.3, -14.1), (359.4, -14.1), (460.3, 22.3), (533.1, 89.7),
    (572.4, 183.9), (572.4, 241.6), (572.4, 292.5), (540.9, 376.4),
    (482.6, 437.6), (354.1, 470.5), (302.7, 470.5), (223.6, 433.2),
    (194.0, 399.2), (203.7, 399.2), (206.1, 561.3), (527.3, 561.3),
    (527.3, 700.0), (65.0, 700.0), (33.9, 290.1), (206.6, 290.1),
    (223.6, 318.7), (268.2, 344.9), (298.8, 344.9), (330.8, 344.9),
    (378.8, 317.7), (405.5, 269.7), (405.5, 237.2), (405.5, 205.2),
    (378.8, 156.7), (330.8, 129.5), (298.8, 129.5), (260.0, 129.5),
    (206.1, 171.2), (199.8, 206.2), (27.6, 206.2), (28.1, 157.2),
    (67.9, 76.6), (139.2, 17.9), (237.7, -14.1),
]
_FIVE_END_PTS = [38]
_FIVE_FLAGS = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1,
               0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0]


def draw_five(font):
    """Variable build: draw ``5`` (U+0035) overriding Recursive's numeral.

    Calibrated three-master (thin@300, light@375, heavy@1000) so it matches
    Recursive's stroke weight. MUST be drawn after the VF default is rebased to
    375. OFL-clean hardcoded geometry."""
    thin, light, heavy = _calib_masters("five", _FIVE_LIGHT, _FIVE_HEAVY)
    _draw_glyph_variable3(font, "five", thin, light, heavy,
                          _FIVE_END_PTS, _FIVE_FLAGS)


# 7 (U+0037): a seven — top horizontal bar, diagonal stroke down to the
# baseline, small foot serif at bottom-left. TWO-master (point-compatible
# Regular + Heavy), so Bold thickens. 1 contour, 8 points, all on-curve.
# Derived from reference outlines, cap-scaled into the 600 cell.
_SEVEN_LIGHT = [
    (128.5, 0.0), (219.7, 0.0), (533.6, 620.9), (533.6, 700.0),
    (66.4, 700.0), (66.4, 623.4), (446.3, 623.4), (446.3, 617.0),
]
_SEVEN_HEAVY = [
    (91.4, 0.0), (277.7, 0.0), (560.5, 562.7), (560.5, 700.5),
    (39.5, 700.5), (39.5, 563.2), (382.0, 563.2), (382.0, 554.0),
]
_SEVEN_END_PTS = [7]
_SEVEN_FLAGS = [1] * 8


def draw_seven(font):
    """Variable build: draw ``7`` (U+0037) overriding Recursive's numeral.

    Calibrated three-master (thin@300, light@375, heavy@1000) so it matches
    Recursive's stroke weight. MUST be drawn after the VF default is rebased to
    375. OFL-clean hardcoded geometry."""
    thin, light, heavy = _calib_masters("seven", _SEVEN_LIGHT, _SEVEN_HEAVY)
    _draw_glyph_variable3(font, "seven", thin, light, heavy,
                          _SEVEN_END_PTS, _SEVEN_FLAGS)


# --------------------------------------------------------------------------------------
# Static-build counterparts (already-instanced font, no gvar): interpolate the
# light/heavy masters by the instance's normalised weight and shear for italic.


def _draw_glyph_static(font, glyph_name, light, heavy, end_pts, flags, wght, slnt=0.0):
    """Static build: interpolate the light→heavy masters by the instance's
    normalised weight and shear for italic. For an already-instanced font (no
    gvar). The static counterpart of ``_draw_glyph_variable``."""
    t = _wght_t(wght)
    coords = [(_lerp(light[i][0], heavy[i][0], t),
               _lerp(light[i][1], heavy[i][1], t)) for i in range(len(light))]
    if slnt:
        coords = _shear(coords, math.tan(math.radians(-slnt)))
    _write_outline(font, glyph_name, coords, end_pts, flags)


# Static-build weight mapping for the seven calibrated glyphs @ $ & 2 4 5 7.
# The static fonts ship Regular/Italic at wght 375 and Bold/Bold-Italic at
# wght 600. wght 375 renders the light master (stem ≈ Recursive Regular); Bold
# (600) renders a light→heavy blend tuned to Recursive's Bold stem. (The VF uses
# its native avar for this; the static has no avar, so we map it explicitly.)
_STATIC_BOLD_WGHT = 600.0
_STATIC_BOLD_FRAC = 0.66


def _static_calib_frac(wght):
    """Light→heavy blend fraction for the calibrated static glyphs: 0 at the
    Regular default (375), _STATIC_BOLD_FRAC at Bold. Clamped at 0 below 375
    (no static Light weight is shipped)."""
    return max(0.0, (wght - 375.0) / (_STATIC_BOLD_WGHT - 375.0) * _STATIC_BOLD_FRAC)


def _draw_glyph_static_calib(font, name, design_light, design_heavy, end_pts, flags,
                             wght, slnt=0.0):
    """Static counterpart of ``_draw_glyph_variable3``: calibrate the masters to
    Recursive's stroke weight, blend light→heavy for the instance's weight, and
    shear for italic. For an already-instanced font (no gvar)."""
    _thin, light, heavy = _calib_masters(name, design_light, design_heavy)
    coords = _blend(light, heavy, _static_calib_frac(wght))
    if slnt:
        coords = _shear(coords, math.tan(math.radians(-slnt)))
    _write_outline(font, name, coords, end_pts, flags)


def draw_checkmark_static(font, wght, slnt=0.0):
    """Static build: draw ``✓`` at the instance's weight/slant."""
    _draw_glyph_static(font, "uni2713", _CHECK_LIGHT, _CHECK_HEAVY,
                       _CHECK_END_PTS, _CHECK_FLAGS, wght, slnt)


def draw_bullet_static(font, wght, slnt=0.0):
    """Static build: draw ``•`` at the instance's weight/slant."""
    light, end_pts, flags = _bullet_master(_BULLET_LIGHT)
    heavy, _, _ = _bullet_master(_BULLET_HEAVY)
    _draw_glyph_static(font, "bullet", light, heavy, end_pts, flags, wght, slnt)


def draw_slash_static(font, wght, slnt=0.0):
    """Static build: draw ``/`` at the instance's weight/slant."""
    _draw_glyph_static(font, "slash", _SLASH_LIGHT, _SLASH_HEAVY,
                       _SLASH_END_PTS, _SLASH_FLAGS, wght, slnt)


def draw_backslash_static(font, wght, slnt=0.0):
    """Static build: draw ``\\`` at the instance's weight/slant.

    Composites (backslash.code, .case, escape ligatures) reference
    ``backslash`` as a component, so they inherit."""
    _draw_glyph_static(font, "backslash", _BACKSLASH_LIGHT, _BACKSLASH_HEAVY,
                       _SLASH_END_PTS, _SLASH_FLAGS, wght, slnt)


def draw_percent_static(font, wght, slnt=0.0):
    """Static build: draw ``%`` at the instance's weight/slant."""
    light, end_pts, flags = _percent_master(_PERCENT_LIGHT)
    heavy, _, _ = _percent_master(_PERCENT_HEAVY)
    _draw_glyph_static(font, "percent", light, heavy, end_pts, flags, wght, slnt)


def draw_dollar_static(font, wght, slnt=0.0):
    """Static build: draw ``$`` at the instance's weight/slant (calibrated)."""
    _draw_glyph_static_calib(font, "dollar", _DOLLAR_LIGHT, _DOLLAR_HEAVY,
                             _DOLLAR_END_PTS, _DOLLAR_FLAGS, wght, slnt)


def draw_at_static(font, wght, slnt=0.0):
    """Static build: draw ``@`` at the instance's weight/slant (calibrated).

    The composite ``at.case`` references ``at`` as a component, so it inherits."""
    _draw_glyph_static_calib(font, "at", _AT_LIGHT, _AT_HEAVY,
                             _AT_END_PTS, _AT_FLAGS, wght, slnt)


def draw_ampersand_static(font, wght, slnt=0.0):
    """Static build: draw ``&`` at the instance's weight/slant (calibrated)."""
    _draw_glyph_static_calib(font, "ampersand", _AMP_LIGHT, _AMP_HEAVY,
                             _AMP_END_PTS, _AMP_FLAGS, wght, slnt)


def draw_two_static(font, wght, slnt=0.0):
    """Static build: draw ``2`` at the instance's weight/slant (calibrated)."""
    _draw_glyph_static_calib(font, "two", _TWO_LIGHT, _TWO_HEAVY,
                             _TWO_END_PTS, _TWO_FLAGS, wght, slnt)


def draw_four_static(font, wght, slnt=0.0):
    """Static build: draw ``4`` at the instance's weight/slant (calibrated)."""
    _draw_glyph_static_calib(font, "four", _FOUR_LIGHT, _FOUR_HEAVY,
                             _FOUR_END_PTS, _FOUR_FLAGS, wght, slnt)


def draw_five_static(font, wght, slnt=0.0):
    """Static build: draw ``5`` at the instance's weight/slant (calibrated)."""
    _draw_glyph_static_calib(font, "five", _FIVE_LIGHT, _FIVE_HEAVY,
                             _FIVE_END_PTS, _FIVE_FLAGS, wght, slnt)


def draw_seven_static(font, wght, slnt=0.0):
    """Static build: draw ``7`` at the instance's weight/slant (calibrated)."""
    _draw_glyph_static_calib(font, "seven", _SEVEN_LIGHT, _SEVEN_HEAVY,
                             _SEVEN_END_PTS, _SEVEN_FLAGS, wght, slnt)
