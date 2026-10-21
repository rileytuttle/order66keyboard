"""
Record of how the symbol->schematic pin transform used by schlib.py was derived.

Rather than guess KiCad's rotation/mirror convention, this takes a known-good
schematic and, for each candidate transform, counts how many computed pin positions
land on an actual wire end, junction, label or no-connect.

The result: at rotation 0 the transform is unambiguously (x + px, y - py), 178/178.
At 90 and 270 several candidates score identically, because the only rotated symbols
in the reference schematic are two-pin parts whose pins are symmetric about the
origin -- so both the clockwise and counter-clockwise transforms produce the same
*set* of points. That is why schlib.py places everything at rotation 0 and refuses
to rotate: it is the one case this could actually prove.

Run: python3 tools/validate_transform.py [path/to/reference.kicad_sch]
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, get, getall

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       os.pardir, 'order66-pcb', 'order66', 'order66.kicad_sch')
SCH = os.path.normpath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
if not os.path.exists(SCH):
    sys.exit(f'reference schematic not found: {SCH}\n'
             f'pass one as an argument; any KiCad 7+ schematic with rotated symbols works')
root = parse(open(SCH).read())[0]

# pin geometry per lib_id, from the schematic's own lib_symbols cache
libpins = {}
for sym in getall(get(root, 'lib_symbols'), 'symbol'):
    name = str(sym[1])
    pins = {}
    def walk(n):
        for c in n[1:]:
            if isinstance(c, list):
                if c[0] == 'pin':
                    at = get(c, 'at'); num = get(c, 'number')
                    if at and num:
                        pins[str(num[1])] = (float(at[1]), float(at[2]))
                else:
                    walk(c)
    walk(sym)
    if pins:
        libpins[name] = pins

# anchor points that pins are known to land on
anchors = set()
for w in getall(root, 'wire'):
    for xy in getall(get(w, 'pts'), 'xy'):
        anchors.add((round(float(xy[1]), 2), round(float(xy[2]), 2)))
for j in getall(root, 'junction'):
    at = get(j, 'at'); anchors.add((round(float(at[1]), 2), round(float(at[2]), 2)))
for g in getall(root, 'global_label'):
    at = get(g, 'at'); anchors.add((round(float(at[1]), 2), round(float(at[2]), 2)))
for nc in getall(root, 'no_connect'):
    at = get(nc, 'at'); anchors.add((round(float(at[1]), 2), round(float(at[2]), 2)))

CANDIDATES = {
    # name: f(px, py, angle_deg) -> (dx, dy) offset from symbol origin
    'rot_cw_negy':  lambda px, py, a: _rot(px, -py, a),
    'rot_ccw_negy': lambda px, py, a: _rot(px, -py, -a),
    'negy_after':   lambda px, py, a: (lambda t: (t[0], -t[1]))(_rot(px, py, a)),
    'plain':        lambda px, py, a: _rot(px, py, a),
}

def _rot(x, y, a):
    r = math.radians(a)
    c, s = math.cos(r), math.sin(r)
    return (x * c - y * s, x * s + y * c)

for name, fn in CANDIDATES.items():
    hit = miss = 0
    per_angle = {}
    for sym in getall(root, 'symbol'):
        lib = get(sym, 'lib_id')
        if not lib or str(lib[1]) not in libpins:
            continue
        at = get(sym, 'at')
        X, Y = float(at[1]), float(at[2])
        ang = float(at[3]) if len(at) > 3 else 0.0
        mir = get(sym, 'mirror')
        if mir:
            continue  # skip mirrored instances for this test
        for num, (px, py) in libpins[str(lib[1])].items():
            dx, dy = fn(px, py, ang)
            pt = (round(X + dx, 2), round(Y + dy, 2))
            ok = pt in anchors
            hit += ok; miss += (not ok)
            a = per_angle.setdefault(ang, [0, 0]); a[0] += ok; a[1] += (not ok)
    total = hit + miss
    print(f'{name:14s} {hit}/{total} = {100*hit/total:.1f}%   by angle: ' +
          ' '.join(f'{int(k)}:{v[0]}/{v[0]+v[1]}' for k, v in sorted(per_angle.items())))
