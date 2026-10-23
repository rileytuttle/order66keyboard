#!/usr/bin/env python3
"""
Generate order66-lp.kicad_pcb: board outline + component placement, no traces.

Run:  python3 tools/gen_pcb.py
Then: python3 tools/check_pcb.py

Everything is on the BACK copper. F.Cu is the keyboard's top face and carries no
components, so KiCad's default front view is the real top view -- no left/right
mirroring to reason about, and COL0 on screen is COL0 under your left hand.

Why the back: marbastlib's choc hotswap footprint draws the Kailh CPG135001S30
socket pads on F.Cu and puts the 14x14 switch-body keepout on B.CrtYd, i.e. it is
drawn from the socket side. Placed on F.Cu you would get sockets on top and switches
inserted from underneath. Flipped to the back, the sockets land on the bottom copper
and the switch bodies protrude through to the top, which is what a keyboard wants.
The reverse-mount LEDs follow: pads on the bottom, body in the routed slot, light
emitted upward through the board into the switch's centre window.

The flip transform below is not guessed -- it was read off the 199 back-side
footprints KiCad itself wrote into the v1.0 board (order66-pcb/order66/order66.kicad_pcb).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexpr import parse, dump, get, getall, Str  # noqa: E402
from schlib import uid, q, n  # noqa: E402

OUT = os.path.join(ROOT, 'pcb', 'order66-lp.kicad_pcb')
SCH = os.path.join(ROOT, 'pcb', 'order66-lp.kicad_sch')
NET = '/tmp/order66lp-pcb.net'

# Geometry comes from gen_schematic so the board and firmware cannot disagree.
from gen_schematic import (PHYS_ROWS as ROWS, PHYS_COLS as COLS,  # noqa: E402
                           PITCH_X as PX, PITCH_Y as PY, GAP, HALF_COLS)

# Key (0,0) centre. Columns run +x, rows run +y.
KX0, KY0 = 30.0, 55.0


def key_x(c):
    """Centre x of physical column c, with the central band inserted."""
    return KX0 + c * PX + (GAP if c >= HALF_COLS else 0.0)


def key_y(r):
    return KY0 + r * PY

# Offset from a key centre to its LED. Derived from the two footprints' reference
# outlines, not guessed; +y because flipping to the back moved the switch pins to -y.
LED_DY = 4.70

# Key field edges (outermost key centres, plus half a pitch)
FX0, FX1 = key_x(0) - PX / 2, key_x(COLS - 1) + PX / 2
FY0, FY1 = key_y(0) - PY / 2, key_y(ROWS - 1) + PY / 2

# The band, between the two halves
BAND_X0, BAND_X1 = key_x(HALF_COLS - 1) + PX / 2, key_x(HALF_COLS) - PX / 2
BAND_CX = (BAND_X0 + BAND_X1) / 2

# Board outline. No back strip any more -- everything that used to live there now sits
# in the central band, which is why the board loses 31.5 mm of depth.
MARGIN = 5.0
BX0, BX1 = FX0 - MARGIN, FX1 + MARGIN
BY0, BY1 = FY0 - MARGIN, FY1 + MARGIN

# Cirque TM040040: module diameter 40.0 mm, active area 38.0 mm, 5.61 mm thick with
# components. Mounted on standoffs above the FRONT face so the PCB stays solid and the
# nano can sit directly behind it -- a flush cutout would leave no room for both.
TRACKPAD_D = 40.0
CONN12_FP = 'marbastlib-various:CON_FH33J-12S-0.5SH'
FP_R = 'Resistor_SMD:R_0402_1005Metric'
FP_C = 'Capacitor_SMD:C_0402_1005Metric'
FP_C_BIG = 'Capacitor_SMD:C_0805_2012Metric'
FP_C_BULK = 'Capacitor_SMD:C_1210_3225Metric'

FP_LIB = {
    'marbastlib-choc': os.path.join(ROOT, 'libraries/marbastlib/footprints/marbastlib-choc.pretty'),
    'nice-nano-kicad': os.path.join(ROOT, 'libraries/nice-nano-kicad'),
    'order66lp': os.path.join(ROOT, 'libraries/order66lp.pretty'),
    'marbastlib-various': os.path.join(
        ROOT, 'libraries/marbastlib/footprints/marbastlib-various.pretty'),
    'EG1206A': os.path.join(ROOT, 'libraries/EG1206A/KiCADv6/footprints.pretty'),
    'SSSS811101': os.path.join(ROOT, 'libraries/SSSS811101'),
}
STOCK_FP = '/nix/store/nd26yd9rhv3ghy2yhgsa9q35qgzm8qjp-kicad-footprints-e0779daea5/share/kicad/footprints'

LAYERS = [
    (0, 'F.Cu', 'signal'), (2, 'B.Cu', 'signal'),
    (9, 'F.Adhes', 'user', 'F.Adhesive'), (11, 'B.Adhes', 'user', 'B.Adhesive'),
    (13, 'F.Paste', 'user'), (15, 'B.Paste', 'user'),
    (5, 'F.SilkS', 'user', 'F.Silkscreen'), (7, 'B.SilkS', 'user', 'B.Silkscreen'),
    (1, 'F.Mask', 'user'), (3, 'B.Mask', 'user'),
    (17, 'Dwgs.User', 'user', 'User.Drawings'),
    (19, 'Cmts.User', 'user', 'User.Comments'),
    (21, 'Eco1.User', 'user', 'User.Eco1'), (23, 'Eco2.User', 'user', 'User.Eco2'),
    (25, 'Edge.Cuts', 'user'), (27, 'Margin', 'user'),
    (31, 'F.CrtYd', 'user', 'F.Courtyard'), (29, 'B.CrtYd', 'user', 'B.Courtyard'),
    (35, 'F.Fab', 'user'), (33, 'B.Fab', 'user'),
]


# marbastlib draws a 19.05 x 19.05 MX keycap reference square on Eco1.User in every
# switch and LED footprint. This board is on 18 x 17 Choc spacing, so that square is
# documentation for a different switch family and only causes confusion on canvas.
DROP_LAYERS = {'Eco1.User'}


def flip_layer(name):
    if name.startswith('F.'):
        return 'B.' + name[2:]
    if name.startswith('B.'):
        return 'F.' + name[2:]
    return name


def mirror_node(node):
    """Mirror a footprint child for back-side placement: negate local y, swap sides.

    Matches what KiCad wrote for the v1.0 board's B.Cu footprints.
    """
    if not isinstance(node, list):
        return node
    head = str(node[0]) if node else ''
    out = [node[0]]
    for ch in node[1:]:
        if isinstance(ch, list):
            h = str(ch[0]) if ch else ''
            if h == 'justify':
                toks = [str(x) for x in ch[1:]]
                if 'mirror' in toks:
                    toks.remove('mirror')
                else:
                    toks.append('mirror')
                out.append([ch[0]] + toks)
            elif h in ('at', 'start', 'end', 'center', 'mid', 'xy') and len(ch) >= 3:
                try:
                    y = -float(ch[2])
                except ValueError:
                    out.append(mirror_node(ch))
                    continue
                new = [ch[0], ch[1], n(y)]
                # Pad angle: KiCad stores fp_rot - lib_pad_rot. fp_rot is applied at
                # render time, so with the footprint at 0 this is just the negation.
                if h == 'at' and len(ch) >= 4 and head == 'pad':
                    try:
                        new.append(n(-float(ch[3]) % 360))
                    except ValueError:
                        new.append(ch[3])
                elif len(ch) >= 4:
                    new.append(ch[3])
                out.append(new)
            elif h == 'layer' and len(ch) >= 2:
                out.append([ch[0], Str(flip_layer(str(ch[1])))])
            elif h == 'effects' and head in ('fp_text', 'gr_text'):
                m = mirror_node(ch)
                if not any(isinstance(x, list) and str(x[0]) == 'justify' for x in m[1:]):
                    m.append(['justify', 'mirror'])
                out.append(m)
            elif h == 'layers':
                out.append([ch[0]] + [Str(flip_layer(str(x))) for x in ch[1:]])
            else:
                out.append(mirror_node(ch))
        else:
            out.append(ch)
    return out


def apply_pad_rotation(node, rot):
    """Fold the footprint's rotation into each pad's angle.

    KiCad stores a pad's angle absolutely, not relative to its footprint -- which is
    why the v1.0 board's B.Cu footprints at 180 degrees carry pad angles of
    (180 - library angle). A rectangular pad with no angle therefore stays
    axis-aligned in board space when the footprint is rotated, and adjacent pads that
    were 0.94 mm apart end up overlapping.
    """
    if not isinstance(node, list):
        return node
    out = [node[0]]
    is_pad = str(node[0]) == 'pad' if node else False
    for ch in node[1:]:
        if isinstance(ch, list) and ch and str(ch[0]) == 'at' and is_pad:
            cur = float(ch[3]) if len(ch) >= 4 else 0.0
            out.append([ch[0], ch[1], ch[2], n((cur + rot) % 360)])
        else:
            out.append(apply_pad_rotation(ch, rot))
    return out


def reuuid(node, ref, counter):
    """Replace every (uuid ...) with one unique to this placement.

    Library footprints ship fixed uuids. Placing the same footprint 60 times would
    otherwise yield 60 sets of identical uuids, and KiCad then treats items in
    different footprints as the same object -- which shows up as DRC 'shorting_items'
    between pads hundreds of mm apart.
    """
    if not isinstance(node, list):
        return node
    out = [node[0]]
    for ch in node[1:]:
        if isinstance(ch, list) and ch and str(ch[0]) == 'uuid':
            counter[0] += 1
            out.append([ch[0], Str(uid(f'pcbitem/{ref}/{counter[0]}'))])
        else:
            out.append(reuuid(ch, ref, counter))
    return out


_fpcache = {}


def load_fp(lib_id):
    if lib_id in _fpcache:
        return _fpcache[lib_id]
    lib, name = lib_id.split(':', 1)
    base = FP_LIB.get(lib) or os.path.join(STOCK_FP, lib + '.pretty')
    path = os.path.join(base, name + '.kicad_mod')
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    _fpcache[lib_id] = parse(open(path).read())[0]
    return _fpcache[lib_id]


class Pcb:
    def __init__(self):
        self.items = []
        self.nets = {'': 0}
        self.placed = {}

    def net_id(self, name):
        if name not in self.nets:
            self.nets[name] = len(self.nets)
        return self.nets[name]

    def footprint(self, lib_id, ref, at, rot=0.0, value=None, netmap=None, back=True):
        import copy
        if ref in self.placed:
            raise ValueError(f'{ref} placed twice')
        self.placed[ref] = (lib_id, at, rot, back)
        fp = copy.deepcopy(load_fp(lib_id))
        if back:
            fp = mirror_node(fp)
        fp = reuuid(fp, ref, [0])
        if rot:
            fp = apply_pad_rotation(fp, rot)

        layer = 'B.Cu' if back else 'F.Cu'
        keep = []
        body = []
        for ch in fp[1:]:
            if not isinstance(ch, list):
                continue
            h = str(ch[0])
            if h in ('version', 'generator', 'generator_version', 'layer', 'at',
                     'property', 'attr', 'uuid', 'tedit'):
                continue
            if h in ('descr', 'tags'):
                keep.append(ch)
                continue
            body.append(ch)

        attr = get(fp, 'attr')
        out = [f'\t(footprint {q(lib_id)}',
               f'\t\t(layer {q(layer)})',
               f'\t\t(uuid {q(uid("fp/" + ref))})',
               f'\t\t(at {n(at[0])} {n(at[1])}{"" if not rot else " " + n(rot)})']
        for ch in keep:
            out.append('\t\t' + dump(ch).strip())
        if attr:
            out.append('\t\t' + dump(attr).strip())

        val = value if value is not None else lib_id.split(':', 1)[1]
        for key, text, lay, hide in (('Reference', ref, flip_layer('F.SilkS') if back else 'F.SilkS', False),
                                     ('Value', val, flip_layer('F.Fab') if back else 'F.Fab', True)):
            out += [f'\t\t(property {q(key)} {q(text)}',
                    f'\t\t\t(at 0 0 0)',
                    f'\t\t\t(unlocked yes)',
                    f'\t\t\t(layer {q(lay)})']
            if hide:
                out.append('\t\t\t(hide yes)')
            out += [f'\t\t\t(uuid {q(uid(f"prop/{ref}/{key}"))})',
                    '\t\t\t(effects',
                    '\t\t\t\t(font',
                    '\t\t\t\t\t(size 1 1)',
                    '\t\t\t\t\t(thickness 0.15)',
                    '\t\t\t\t)']
            if back:
                out.append('\t\t\t\t(justify mirror)')
            out += ['\t\t\t)', '\t\t)']

        for ch in body:
            h = str(ch[0])
            lay = get(ch, 'layer')
            if lay and str(lay[1]) in DROP_LAYERS:
                continue
            txt = dump(ch, 2)
            if h == 'pad':
                name = str(ch[1])
                net = (netmap or {}).get(name)
                if net:
                    nid = self.net_id(net)
                    txt = txt.rstrip()
                    assert txt.endswith(')')
                    txt = txt[:-1].rstrip() + f'\n\t\t\t(net {nid} {q(net)})\n\t\t)'
            out.append(txt)
        out.append('\t)')
        self.items.append('\n'.join(out))

    def seg(self, a, b, layer='Edge.Cuts', width=0.1):
        self.items.append('\n'.join([
            '\t(gr_line',
            f'\t\t(start {n(a[0])} {n(a[1])})',
            f'\t\t(end {n(b[0])} {n(b[1])})',
            '\t\t(stroke',
            f'\t\t\t(width {n(width)})',
            '\t\t\t(type default)',
            '\t\t)',
            f'\t\t(layer {q(layer)})',
            f'\t\t(uuid {q(uid(f"gr/{layer}/{a}/{b}"))})',
            '\t)']))

    def rect_outline(self, x0, y0, x1, y1):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                     ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            self.seg(a, b)

    def circle(self, centre, radius, layer='Dwgs.User', width=0.12):
        self.items.append('\n'.join([
            '\t(gr_circle',
            f'\t\t(center {n(centre[0])} {n(centre[1])})',
            f'\t\t(end {n(centre[0] + radius)} {n(centre[1])})',
            '\t\t(stroke',
            f'\t\t\t(width {n(width)})',
            '\t\t\t(type default)',
            '\t\t)',
            '\t\t(fill no)',
            f'\t\t(layer {q(layer)})',
            f'\t\t(uuid {q(uid(f"circ/{centre}/{radius}"))})',
            '\t)']))

    def text(self, body, at, layer='Cmts.User', size=2.0):
        self.items.append('\n'.join([
            f'\t(gr_text {q(body)}',
            f'\t\t(at {n(at[0])} {n(at[1])} 0)',
            f'\t\t(layer {q(layer)})',
            f'\t\t(uuid {q(uid(f"txt/{at}/{body[:20]}"))})',
            '\t\t(effects',
            '\t\t\t(font',
            f'\t\t\t\t(size {n(size)} {n(size)})',
            f'\t\t\t\t(thickness {n(size * 0.15)})',
            '\t\t\t)',
            '\t\t\t(justify left bottom)',
            '\t\t)',
            '\t)']))

    def render(self):
        netdefs = '\n'.join(f'\t(net {i} {q(nm)})'
                            for nm, i in sorted(self.nets.items(), key=lambda kv: kv[1]))
        lay = '\n'.join('\t\t(' + str(l[0]) + f' {q(l[1])} {l[2]}'
                        + (f' {q(l[3])}' if len(l) > 3 else '') + ')' for l in LAYERS)
        return '\n'.join([
            '(kicad_pcb',
            '\t(version 20241229)',
            '\t(generator "pcbnew")',
            '\t(generator_version "9.0")',
            '\t(general',
            '\t\t(thickness 1.6)',
            '\t\t(legacy_teardrops no)',
            '\t)',
            '\t(paper "A2")',
            '\t(layers',
            lay,
            '\t)',
            '\t(setup',
            '\t\t(pad_to_mask_clearance 0)',
            '\t\t(allow_soldermask_bridges_in_footprints no)',
            '\t)',
            netdefs,
            '\n'.join(self.items),
            '\t(embedded_fonts no)',
            ')',
            ''])


# ------------------------------------------------------------------ netlist
def load_netmap():
    env = dict(os.environ, KICAD_CONFIG_HOME='/tmp/order66lp-kicad-cfg')
    if not os.path.isdir('/tmp/order66lp-kicad-cfg/10.0'):
        subprocess.run([os.path.join(HERE, 'erc.sh')], capture_output=True, env=env)
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', NET, SCH], capture_output=True, text=True, env=env, check=True)
    root = parse(open(NET).read())[0]
    out = {}
    for netnode in getall(get(root, 'nets'), 'net'):
        name = str(get(netnode, 'name')[1])
        for nd in getall(netnode, 'node'):
            out.setdefault(str(get(nd, 'ref')[1]), {})[str(get(nd, 'pin')[1])] = name
    return out


def build():
    nm = load_netmap()
    p = Pcb()

    def place(lib_id, ref, at, rot=0.0, value=None, back=True):
        p.footprint(lib_id, ref, at, rot, value, nm.get(ref, {}), back)

    # ---------------- key field: switch + LED + diode + decoupling cap per cell
    for r in range(ROWS):
        for c in range(COLS):
            k = r * COLS + c + 1
            cx, cy = key_x(c), key_y(r)
            place('marbastlib-choc:SW_choc_v1_HS_CPG135001S30_1u', f'SW{k}', (cx, cy),
                  value='CHOC_V1_HS')
            # The LED add-on's origin is NOT the key centre. Both footprints draw a
            # reference key-cell outline on Dwgs.User: the switch's is centred on its
            # origin, the LED's is centred 4.70 mm away from its own. Aligning the two
            # cells puts the LED 4.70 mm from the switch centre, on the side opposite
            # the switch pins -- which is where Choc v1's LED window actually is.
            # Placing it at the centre instead collides its routed slot with the
            # switch's 3.4 mm centre hole.
            place('marbastlib-choc:LED_choc_6028R', f'LED{k}', (cx, cy + LED_DY),
                  value='SK6812MINI-E')
            # Diode and cap go in the socket-free band below the switch.
            place('Diode_SMD:D_SOD-323', f'D{k}', (cx - 4.2, cy + 6.6), rot=0,
                  value='1N4148WS')
            place('Capacitor_SMD:C_0402_1005Metric', f'C{100 + k}', (cx + 4.4, cy + 6.6),
                  rot=0, value='100n')

    # ---------------- band, BACK face, top: controller, USB out the back edge
    # The nano stands on end. Its connector overhangs the board edge by design, which
    # is how the port ends up flush with the case wall rather than recessed.
    nano_y = BY0 + 1.0 + 16.51                  # occupies BY0+1 .. BY0+34
    place('order66lp:nice_nano_Hdr_TH1-12_SMD13-33', 'U1', (BAND_CX, nano_y), rot=270,
          value='nice!nano v2')

    # ---------------- band, FRONT face, bottom: mouse buttons then the trackpad
    btn_cy = BY1 - MARGIN - PY / 2
    # Choc hotswap, so these punch thru-holes: nothing on the back face may be inside
    # their footprints. BTN_TOP is the hard limit for back-face packing.
    btn_top = btn_cy - 9.5
    for i in range(2):
        place('marbastlib-choc:SW_choc_v1_HS_CPG135001S30_1u', f'SW{61 + i}',
              (BAND_CX + (i - 0.5) * PX, btn_cy), value='MOUSE_BTN')
        place('Diode_SMD:D_SOD-323', f'D{61 + i}',
              (BAND_CX + (i - 0.5) * PX - 4.2, btn_cy + 6.6), value='1N4148WS')

    # Trackpad is mechanical (standoffs + FFC tail), so only its connector is a
    # footprint. Outline drawn on Dwgs.User: module 40 mm, active area 38 mm.
    pad_cy = btn_top - 1.0 - TRACKPAD_D / 2
    p.circle((BAND_CX, pad_cy), TRACKPAD_D / 2, layer='Dwgs.User')
    p.circle((BAND_CX, pad_cy), 38.0 / 2, layer='Dwgs.User')
    p.text(f'Cirque TM040040 ({TRACKPAD_D:.0f} mm) on standoffs, FRONT face. '
           f'PCB stays solid behind it so U1 can sit on the back.',
           (BAND_X0, pad_cy - TRACKPAD_D / 2 - 2.0), size=1.4)

    # ---------------- band, BACK face: five rows
    # The band's HEIGHT is fixed by the key field, so widening the gap buys width, not
    # height. 54 mm of width is what lets these collapse into five rows that clear the
    # mouse buttons; at 45 mm they needed eight and overran by 2 mm.
    row = lambda i: nano_y + 16.51 + 3.0 + i          # noqa: E731

    # A: trackpad tail + the boost power path
    place(CONN12_FP, 'J4', (BAND_CX - 22.0, row(0)), rot=0, value='Cirque FFC')
    place('Inductor_SMD:L_Taiyo-Yuden_NR-30xx', 'L1', (BAND_CX - 8.0, row(0)),
          value='4.7uH')
    place('Package_SO:VSSOP-8_3x3mm_P0.65mm', 'U2', (BAND_CX + 4.0, row(0)),
          value='TPS61085DGK')
    place('Diode_SMD:D_SMA', 'D63', (BAND_CX + 18.0, row(0)), value='MBRA340')

    # B: the hard cutoff, the level shifter, and the boost's input/output caps
    place('Package_TO_SOT_SMD:SOT-23', 'Q1', (BAND_CX - 23.0, row(7)), value='AO3401A')
    place('Package_TO_SOT_SMD:SOT-23', 'Q2', (BAND_CX - 15.0, row(7)), value='BSS138')
    place('Package_TO_SOT_SMD:SOT-353_SC-70-5', 'U3', (BAND_CX - 7.0, row(7)),
          value='74AHCT1G125')
    for i, (ref, val, fp) in enumerate([
            ('C1', '10u', FP_C_BIG), ('C2', '100n', FP_C),
            ('C3', '22u', FP_C_BIG), ('C4', '22u', FP_C_BIG)]):
        place(fp, ref, (BAND_CX + 2.0 + i * 5.5, row(7)), value=val)

    # C: bulk caps and every resistor. 1210s are 3.2 mm wide so they need 5.5 mm pitch.
    for i, (ref, val, fp) in enumerate([
            ('C5', '100u', FP_C_BULK), ('C6', '100u', FP_C_BULK),
            ('C7', '2n2', FP_C), ('C8', '10n', FP_C)]):
        place(fp, ref, (BAND_CX - 24.0 + i * 5.5, row(13)), value=val)
    res = [('R1', '100k'), ('R2', '10k'), ('R3', '100k'), ('R4', '30k1'),
           ('R5', '10k'), ('R6', '10k'), ('R7', '1k'), ('R8', '330R'),
           ('R9', '4k7'), ('R10', '4k7')]
    for i, (ref, val) in enumerate(res):
        place(FP_R, ref, (BAND_CX - 1.0 + i * 3.4, row(13)), value=val)

    # D: the two power-switch options. EG1206A alone spans 25.4 mm.
    place('EG1206A:EG1206A_EWI', 'SW64', (BAND_CX - 24.0, row(20)), rot=0,
          value='EG1206A')
    place('SSSS811101:SW_SSSS811101', 'SW65', (BAND_CX + 8.0, row(20)), rot=0,
          value='SSSS811101')

    # E: battery, reset and the two SWD footprints
    place('Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical', 'J1',
          (BAND_CX - 22.0, row(28)), rot=0, value='Battery')
    place('Button_Switch_THT:SW_TH_Tactile_Omron_B3F-100x', 'SW63',
          (BAND_CX - 8.0, row(28)), rot=0, value='RESET')
    place('Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal', 'J2',
          (BAND_CX + 6.0, row(28)), rot=0, value='SWD')
    place('Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical', 'J3',
          (BAND_CX + 18.0, row(28)), rot=0, value='SWD millmax')

    assert row(31.0) < btn_top, (
        f'band back face overruns the mouse buttons: {row(31.0):.1f} vs {btn_top:.1f}')

    # ---------------- mounting holes
    # Only two places have room: the strip, and the ~2.1 mm channels between columns.
    # 2.1 mm cannot take an M2.5 hole, so the four field holes sit in the slightly
    # wider gaps at the row boundaries instead. See the notes in check_pcb.py.
    # Perimeter only. Inside the key field the free channels between columns are
    # 2.09 mm wide (see check_pcb.py), which cannot take a 2.7 mm hole, so there is
    # nowhere for a mid-board screw without sacrificing a key.
    hy = BY1 - MARGIN / 2
    holes = [(BX0 + MARGIN / 2, BY0 + MARGIN / 2), (BX1 - MARGIN / 2, BY0 + MARGIN / 2),
             (BX0 + MARGIN / 2, (FY0 + FY1) / 2), (BX1 - MARGIN / 2, (FY0 + FY1) / 2),
             (BX0 + MARGIN / 2, hy), (BX1 - MARGIN / 2, hy)]
    for i, hp in enumerate(holes):
        place('MountingHole:MountingHole_2.7mm_M2.5', f'H{i + 1}', hp,
              value='M2.5', back=False)

    # ---------------- outline + notes
    p.rect_outline(BX0, BY0, BX1, BY1)
    p.text(f'order66-lp  {BX1 - BX0:.1f} x {BY1 - BY0:.1f} mm  '
           f'5x12 Choc v1 @ {PX}x{PY}mm, {GAP:.0f} mm central band',
           (BX0, BY0 - 4), size=2.5)
    p.text('ALL components on B.Cu (keyboard underside). F.Cu is the top face and is '
           'intentionally empty.', (BX0, BY1 + 5), size=1.8)
    p.text('No traces yet -- placement only.', (BX0, BY1 + 9), size=1.8)
    return p


# Design rules live in the .kicad_pro, which is easy to clobber by hand. Reapply them
# on every generate so they cannot drift, and let check_pcb.py assert them.
DESIGN_RULES = {
    # Reverse-mount SK6812MINI-E pads sit ~0.35 mm from the slot their own footprint
    # routes for the LED body, so the stock 0.5 mm flags all 60 forever.
    'min_copper_edge_clearance': 0.2,
    # U2 (VSSOP-8) and U3 (SOT-353) put their own adjacent pins 0.2 mm apart, so a
    # larger minimum can never pass inside the package.
    'min_clearance': 0.15,
}
NETCLASS_CLEARANCE = 0.15


def apply_design_rules():
    import json
    p = os.path.join(ROOT, 'pcb', 'order66-lp.kicad_pro')
    d = json.load(open(p))
    d['board']['design_settings']['rules'].update(DESIGN_RULES)
    for c in d['net_settings']['classes']:
        if c.get('clearance', 0) > NETCLASS_CLEARANCE:
            c['clearance'] = NETCLASS_CLEARANCE
    json.dump(d, open(p, 'w'), indent=2)
    return d


if __name__ == '__main__':
    pcb = build()
    open(OUT, 'w').write(pcb.render())
    apply_design_rules()
    print(f'wrote {OUT}')
    print(f'  design rules reapplied: {DESIGN_RULES}')
    print(f'  board    : {BX1 - BX0:.1f} x {BY1 - BY0:.1f} mm')
    print(f'  key field: {FX1 - FX0:.1f} x {FY1 - FY0:.1f} mm')
    print(f'  footprints: {len(pcb.placed)}')
    print(f'  nets      : {len(pcb.nets) - 1}')
