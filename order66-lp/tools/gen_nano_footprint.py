#!/usr/bin/env python3
"""
Derive a mixed through-hole / surface-mount nice!nano footprint.

The nano is socketed on headers rather than soldered flat, and the two pad rows
(15.24 mm apart) cannot both be through-hole on this board: a THT pin emerges on the
top face, where the free band between switch bodies is only 3.00 mm, while the
bottom-side band is 7.70 mm. With rows 15.24 mm apart on a 17 mm row pitch the two
are 1.76 mm out of step, so only one row can be through-hole. Making the other row
surface-mount removes its top-side constraint entirely.

  pins 1-12   -> through-hole   (one long edge; sneaks between key columns)
  pins 13-24  -> surface-mount  (the other long edge)
  pins 31-33  -> surface-mount  (interior pads; see the note below)

Pins 31/32/33 sit at x=+8.89, y=0/2.54/5.08 -- under the middle of the module, not on
either edge row. An edge header cannot reach them, so they need their own 1x3 header
beneath the nano. They are included here only so the footprint still matches the
27-pin symbol. The tidier fix is to move their three nets (COL7, COL8, COL11) onto the
three unused pro_micro connector pins, which also makes the shield portable to any
pro_micro-footprint controller.

Source footprint is the vendored nice-nano-kicad one, left untouched.

Run: python3 tools/gen_nano_footprint.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexpr import parse, dump, get, getall, Str  # noqa: E402
from schlib import uid, n  # noqa: E402

SRC = os.path.join(ROOT, 'libraries/nice-nano-kicad/nice_nano.kicad_mod')
OUTDIR = os.path.join(ROOT, 'libraries/order66lp.pretty')
NAME = 'nice_nano_Hdr_TH1-12_SMD13-33'
OUT = os.path.join(OUTDIR, NAME + '.kicad_mod')

TH_PINS = {str(i) for i in range(1, 13)}

# Surface-mount pad size, centred on the nominal pin position. Deliberately generous
# so it suits either an SMD 2.54 mm header's solder tail or a directly soldered pin.
# Check against the datasheet of whichever header you actually buy.
SMD_W, SMD_H = 1.6, 2.6
# Pins 31-33 run along y at 2.54 mm pitch, not along x like the edge rows. Make them
# square rather than elongated: a 2.6 mm dimension anywhere collides at 2.54 mm pitch
# once the footprint is placed at 90/270 degrees, which is exactly what happened.
INTERIOR = {'31', '32', '33'}
SMD_SQ = 1.6

DESCR = ('nice!nano v2 on headers, mixed mount: pins 1-12 through-hole, pins 13-24 '
         'and 31-33 surface-mount. For boards where a THT pin on both rows would '
         'foul the switch bodies on the opposite face. Pins 31-33 are interior pads '
         'and need their own 1x3 header. Derived from nice-nano-kicad by '
         'tools/gen_nano_footprint.py.')
TAGS = 'nice_nano nrf52840 pro_micro header mixed tht smd socketed'


def main():
    fp = parse(open(SRC).read())[0]
    out = ['(footprint "%s"' % NAME,
           '\t(version 20241229)',
           '\t(generator "gen_nano_footprint.py")',
           '\t(layer "F.Cu")',
           '\t(descr "%s")' % DESCR,
           '\t(tags "%s")' % TAGS,
           '\t(attr through_hole)']

    th = smd = 0
    body = []
    for ch in fp[1:]:
        if not isinstance(ch, list):
            continue
        h = str(ch[0])
        if h in ('version', 'generator', 'generator_version', 'layer', 'at',
                 'descr', 'tags', 'attr', 'uuid', 'tedit', 'property'):
            continue
        if h != 'pad':
            body.append(ch)
            continue

        name = str(ch[1])
        at = get(ch, 'at')
        x, y = float(at[1]), float(at[2])
        if name in TH_PINS:
            th += 1
            body.append(ch)          # keep the original through-hole pad verbatim
            continue
        smd += 1
        w, h = (SMD_SQ, SMD_SQ) if name in INTERIOR else (SMD_W, SMD_H)
        body.append(parse(
            f'(pad "{name}" smd roundrect (at {n(x)} {n(y)}) '
            f'(size {n(w)} {n(h)}) (layers "F.Cu" "F.Paste" "F.Mask") '
            f'(roundrect_rratio 0.15) (uuid "{uid("nanofp/pad/" + name)}"))')[0])

    # Mark which row is which, so it is obvious on the board.
    for text, pos in (('TH 1-12', (0, 10.8)), ('SMD 13-24', (0, -10.8))):
        body.append(parse(
            f'(fp_text user "{text}" (at {n(pos[0])} {n(pos[1])} 0) (layer "F.SilkS") '
            f'(uuid "{uid("nanofp/txt/" + text)}") '
            f'(effects (font (size 1 1) (thickness 0.15))))')[0])

    for ch in body:
        out.append(dump(ch, 1))
    out += ['\t(embedded_fonts no)', ')', '']

    # No two pads may overlap, and none may sit closer than the fab minimum.
    pads = []
    for ch in body:
        if isinstance(ch, list) and str(ch[0]) == 'pad':
            at, sz = get(ch, 'at'), get(ch, 'size')
            pads.append((str(ch[1]), float(at[1]), float(at[2]),
                         float(sz[1]), float(sz[2])))
    MIN = 0.15
    bad = []
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            a, b = pads[i], pads[j]
            gx = abs(a[1] - b[1]) - (a[3] + b[3]) / 2
            gy = abs(a[2] - b[2]) - (a[4] + b[4]) / 2
            if gx < MIN and gy < MIN:
                bad.append(f'pads {a[0]} and {b[0]}: gap {max(gx, gy):+.3f} mm')
    if bad:
        print(f'ERROR: {len(bad)} pad clearance problem(s):')
        for b in bad[:8]:
            print('  ' + b)
        return 1
    print(f'  pad-to-pad clearance: all >= {MIN} mm')

    os.makedirs(OUTDIR, exist_ok=True)
    open(OUT, 'w').write('\n'.join(out))
    print(f'wrote {OUT}')
    print(f'  through-hole pads : {th}  (pins 1-12)')
    print(f'  surface-mount pads: {smd} (pins 13-24, 31-33) @ {SMD_W} x {SMD_H} mm')
    return 0


if __name__ == '__main__':
    sys.exit(main())
