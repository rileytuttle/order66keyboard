#!/usr/bin/env python3
"""
Assert the generated PCB placement is what we intended.

These are the checks DRC does not make: that the key grid is on exact Choc pitch,
that every LED sits at its switch's actual LED window rather than the switch centre,
that the component set matches the schematic, and that nothing on the support strip
reaches down into the key field.

Run: python3 tools/check_pcb.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexpr import parse, get, getall  # noqa: E402
import gen_pcb as G  # noqa: E402

PCB = os.path.join(ROOT, 'pcb', 'order66-lp.kicad_pcb')

fails = []


def check(cond, msg):
    print(f'  {"ok  " if cond else "FAIL"} {msg}')
    if not cond:
        fails.append(msg)


def main():
    pcb = parse(open(PCB).read())[0]
    fps = {}
    for fp in getall(pcb, 'footprint'):
        ref = None
        for pr in getall(fp, 'property'):
            if str(pr[1]) == 'Reference':
                ref = str(pr[2])
        at = get(fp, 'at')
        lay = get(fp, 'layer')
        fps[ref] = {
            'lib': str(fp[1]),
            'x': float(at[1]), 'y': float(at[2]),
            'rot': float(at[3]) if len(at) > 3 else 0.0,
            'layer': str(lay[1]),
            'pads': [str(p[1]) for p in getall(fp, 'pad')],
        }
    print(f'{len(fps)} footprints\n')

    # ---------------------------------------------------- matches the schematic
    print('component set')
    sch = open(os.path.join(ROOT, 'pcb', 'order66-lp.kicad_sch')).read()
    sch_refs = set()
    for m in re.finditer(r'\(property "Reference" "([^"]+)"', sch):
        r = m.group(1)
        if not r.startswith('#'):
            sch_refs.add(r)
    # lib_symbols entries carry a Reference property too; keep only real designators
    sch_refs = {r for r in sch_refs if re.fullmatch(r'[A-Za-z]+\d+', r)}
    check(sch_refs == set(fps),
          f'every schematic designator is placed '
          f'(missing {sorted(sch_refs - set(fps))[:4]}, '
          f'extra {sorted(set(fps) - sch_refs)[:4]})')

    # ---------------------------------------------------- sides
    print('\nsides')
    back = [r for r, d in fps.items() if d['layer'] == 'B.Cu']
    front = [r for r, d in fps.items() if d['layer'] == 'F.Cu']
    check(all(r.startswith('H') for r in front),
          f'only mounting holes on F.Cu (got {sorted(front)})')
    check(len(back) == len(fps) - len(front),
          f'{len(back)} components on B.Cu, the keyboard underside')

    # ---------------------------------------------------- key grid
    print('\nkey grid')
    sw = {r: d for r, d in fps.items()
          if re.fullmatch(r'SW\d+', r) and int(r[2:]) <= G.ROWS * G.COLS}
    check(len(sw) == 60, f'60 key switches (found {len(sw)})')
    bad = []
    for r, d in sw.items():
        k = int(r[2:]) - 1
        row, col = divmod(k, G.COLS)
        ex, ey = G.key_x(col), G.key_y(row)
        if abs(d['x'] - ex) > 1e-6 or abs(d['y'] - ey) > 1e-6:
            bad.append(f'{r} at ({d["x"]},{d["y"]}) expected ({ex},{ey})')
    check(not bad, f'all 60 on exact {G.PX} x {G.PY} mm pitch within each half')
    for b in bad[:4]:
        print('       ' + b)

    xs = sorted({d['x'] for d in sw.values()})
    ys = sorted({d['y'] for d in sw.values()})
    check(len(xs) == 12, f'12 distinct column positions (found {len(xs)})')
    # inside each half the pitch is exact; between the halves it is pitch + gap
    gaps = [round(b - a, 6) for a, b in zip(xs, xs[1:])]
    inner = [g for i, g in enumerate(gaps) if i != G.HALF_COLS - 1]
    check(all(abs(g - G.PX) < 1e-6 for g in inner),
          f'columns spaced {G.PX} mm inside each half')
    check(abs(gaps[G.HALF_COLS - 1] - (G.PX + G.GAP)) < 1e-6,
          f'halves separated by {G.GAP} mm of extra space '
          f'(centre-to-centre {gaps[G.HALF_COLS - 1]})')
    check(len(ys) == 5 and all(abs(b - a - G.PY) < 1e-6 for a, b in zip(ys, ys[1:])),
          f'5 rows spaced {G.PY} mm')

    # ---------------------------------------------------- the band is keyless
    print('\ncentral band')
    inband = [r for r, d in sw.items() if G.BAND_X0 < d['x'] < G.BAND_X1]
    check(not inband, f'no keys inside the band (found {inband})')
    check(abs((G.BAND_X1 - G.BAND_X0) - G.GAP) < 1e-6,
          f'band is {G.BAND_X1 - G.BAND_X0:.1f} mm wide')
    btns = {r: d for r, d in fps.items() if r in ('SW61', 'SW62')}
    check(len(btns) == 2 and all(G.BAND_X0 < d['x'] < G.BAND_X1 for d in btns.values()),
          'both mouse buttons sit inside the band')
    # the trackpad mounts on standoffs, so the PCB must stay solid behind it -- i.e.
    # no Edge.Cuts inside its outline, which is what lets the nano sit behind it
    pad_r = G.TRACKPAD_D / 2
    cuts = [g for g in getall(pcb, 'gr_line')
            if get(g, 'layer') and str(get(g, 'layer')[1]) == 'Edge.Cuts']
    u1 = fps.get('U1')
    check(u1 is not None and G.BAND_X0 < u1['x'] < G.BAND_X1,
          'controller sits inside the band')

    # ---------------------------------------------------- LED offset
    print('\nLED placement')
    off = []
    for r, d in sw.items():
        led = fps.get('LED' + r[2:])
        if not led:
            off.append(f'{r} has no LED')
            continue
        dx, dy = led['x'] - d['x'], led['y'] - d['y']
        if abs(dx) > 1e-6 or abs(dy - G.LED_DY) > 1e-6:
            off.append(f'LED{r[2:]} offset ({dx},{dy}) expected (0,{G.LED_DY})')
    check(not off, f'every LED at its switch + {G.LED_DY} mm '
                   f'(the Choc LED window, not the switch centre)')
    for o in off[:4]:
        print('       ' + o)

    # ---------------------------------------------------- inside the outline
    print('\nboard outline')
    edges = [g for g in getall(pcb, 'gr_line')
             if get(g, 'layer') and str(get(g, 'layer')[1]) == 'Edge.Cuts']
    pts = []
    for g in edges:
        for k in ('start', 'end'):
            nn = get(g, k)
            pts.append((float(nn[1]), float(nn[2])))
    bx = (min(p[0] for p in pts), max(p[0] for p in pts))
    by = (min(p[1] for p in pts), max(p[1] for p in pts))
    check(abs((bx[1] - bx[0]) - (G.BX1 - G.BX0)) < 1e-6
          and abs((by[1] - by[0]) - (G.BY1 - G.BY0)) < 1e-6,
          f'outline {bx[1]-bx[0]:.1f} x {by[1]-by[0]:.1f} mm')
    outside = [r for r, d in fps.items()
               if not (bx[0] <= d['x'] <= bx[1] and by[0] <= d['y'] <= by[1])]
    check(not outside, f'every component origin inside the outline (out: {outside[:4]})')

    # ---------------------------------------------------- band vs mouse buttons
    print('\nband packing')
    # The mouse buttons are Choc hotswap, so their thru-holes punch through the board;
    # nothing on the back face may sit inside their footprint.
    btn_top = min(d['y'] for d in btns.values()) - 9.5
    intruders = [r for r, d in fps.items()
                 if d['layer'] == 'B.Cu' and d['y'] > btn_top
                 and G.BAND_X0 < d['x'] < G.BAND_X1
                 and r not in ('SW61', 'SW62', 'D61', 'D62')]
    check(not intruders,
          f'nothing on the back face runs into the mouse buttons (found {intruders})')

    # ---------------------------------------------------- legacy strip check
    print('\nsupport strip (now gone)')
    # The top row's switch pin holes reach 5.95 mm above each key centre. Anything on
    # the strip that dips past that line collides with them -- this caught a real
    # overlap between the boost passives and row 0.
    # Mounting holes legitimately live in the margin; nothing else should be up there.
    above = [r for r, d in fps.items()
             if d['y'] < G.FY0 - 0.5 and not re.fullmatch(r'H\d+', r)]
    check(not above,
          f'nothing but mounting holes above the key field - the back strip is gone '
          f'(found {above})')

    # ---------------------------------------------------- why the strip exists
    print('\nunderside space (why there is a strip at all)')
    sock_x = (-3.25 - 2.65 / 2, 8.24 + 2.65 / 2)
    occ_x = (min(sock_x[0], -G.PX / 2 + 2.65), sock_x[1])
    free_x = G.PX + occ_x[0] - occ_x[1]
    free_y = G.PY + (-1.57) - 7.45
    check(free_x < 17.78 or free_y < 33.02,
          f'largest clear area under the key field is still only '
          f'{free_x:.2f} x {free_y:.2f} mm - which is why the band exists')

    # ---------------------------------------------------- design rules
    print('\ndesign rules')
    import json
    pro = json.load(open(os.path.join(ROOT, 'pcb', 'order66-lp.kicad_pro')))
    r = pro['board']['design_settings']['rules']
    for k, v in G.DESIGN_RULES.items():
        check(abs(r.get(k, -1) - v) < 1e-9, f'{k} = {v} (got {r.get(k)})')
    worst = max(c.get('clearance', 0) for c in pro['net_settings']['classes'])
    check(worst <= G.NETCLASS_CLEARANCE,
          f'no netclass clearance above {G.NETCLASS_CLEARANCE} mm (worst {worst})')

    # ---------------------------------------------------- pad rotation
    # KiCad stores pad angles absolutely. A rotated footprint whose pads kept angle 0
    # would have axis-aligned pads in board space, which silently overlapped U1's
    # 2.54 mm-pitch interior pads.
    print('\npad angles on rotated footprints')
    bad_rot = []
    for fp in getall(pcb, 'footprint'):
        at = get(fp, 'at')
        frot = float(at[3]) if len(at) > 3 else 0.0
        if not frot:
            continue
        ref = next((str(p[2]) for p in getall(fp, 'property')
                    if str(p[1]) == 'Reference'), '?')
        for pad in getall(fp, 'pad'):
            pat = get(pad, 'at')
            prot = float(pat[3]) if len(pat) > 3 else 0.0
            if abs((prot - frot) % 90) > 1e-6:
                bad_rot.append(f'{ref}.{pad[1]} angle {prot} vs footprint {frot}')
    check(not bad_rot, f'rotated footprints carry the rotation on their pads '
                       f'({len(bad_rot)} bad)')
    for b in bad_rot[:4]:
        print('       ' + b)

    print()
    if fails:
        print(f'{len(fails)} CHECK(S) FAILED')
        return 1
    print('all checks passed')
    print('NOTE: no traces yet. DRC will report ~499 unconnected items by design.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
