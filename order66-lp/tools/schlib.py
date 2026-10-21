"""Emit a KiCad .kicad_sch from a declarative part/net description.

Only rotation 0, unmirrored placement is supported. That is deliberate: it is the one
symbol->schematic coordinate transform that could be validated unambiguously against
the existing order66 schematic (see tools/validate_transform.py), so pin coordinates
here are exact rather than guessed.
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import dump  # noqa: E402
import libs  # noqa: E402

VERSION = '20250114'
GENERATOR = 'eeschema'
GEN_VERSION = '9.0'
PROJECT = 'order66-lp'
VISIBLE = ('Reference', 'Value')

PAPER_SIZE = {'A4': (297, 210), 'A3': (420, 297), 'A2': (594, 420),
              'A1': (841, 594), 'A0': (1189, 841)}


def uid(seed):
    """Deterministic UUID so regenerating produces no spurious git diff."""
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, 'order66-lp/' + seed))


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def n(v):
    """Format a number the way KiCad does."""
    v = round(float(v) + 0.0, 4)
    return str(int(v)) if v == int(v) else str(v)


def yn(b):
    return 'yes' if b else 'no'


class Sch:
    def __init__(self, paper='A1', root_uuid=None):
        self.paper = paper
        self.root_uuid = root_uuid or uid('root')
        self.items = []
        self.libids = {}
        self.refs = {}
        self.labels = {}   # netname -> [(x, y), ...]
        self.wires = []    # ((x1, y1), (x2, y2))

    # ------------------------------------------------------------------ parts
    def pin(self, lib_id, origin, number):
        """Schematic coordinates of one pin of a symbol placed at `origin`."""
        px, py = libs.pins(lib_id)[str(number)][:2]
        return (round(origin[0] + px, 2), round(origin[1] - py, 2))

    def symbol(self, lib_id, ref, at, value=None, footprint=None, fields=None,
               dnp=False, in_bom=True, on_board=True, ref_offset=(0, -8.89),
               val_offset=(0, 8.89), hide_value=False):
        if ref in self.refs:
            raise ValueError(f'duplicate reference designator {ref}')
        self.refs[ref] = lib_id
        if lib_id not in self.libids:
            self.libids[lib_id] = libs.resolved_symbol(lib_id)

        x, y = at
        if value is None:
            value = libs.prop(lib_id, 'Value', lib_id.split(':', 1)[1])
        if footprint is None:
            footprint = libs.prop(lib_id, 'Footprint')

        props = [('Reference', ref), ('Value', value), ('Footprint', footprint),
                 ('Datasheet', libs.prop(lib_id, 'Datasheet')),
                 ('Description', libs.prop(lib_id, 'Description'))]
        for k, v in (fields or {}).items():
            props.append((k, v))

        out = ['\t(symbol',
               f'\t\t(lib_id {q(lib_id)})',
               f'\t\t(at {n(x)} {n(y)} 0)',
               '\t\t(unit 1)',
               '\t\t(exclude_from_sim no)',
               f'\t\t(in_bom {yn(in_bom)})',
               f'\t\t(on_board {yn(on_board)})',
               f'\t\t(dnp {yn(dnp)})',
               f'\t\t(uuid {q(uid("sym/" + ref))})']

        offsets = {'Reference': ref_offset, 'Value': val_offset}
        for key, val in props:
            dx, dy = offsets.get(key, (0, 0))
            shown = key in VISIBLE and not (key == 'Value' and hide_value)
            out += [f'\t\t(property {q(key)} {q(val)}',
                    f'\t\t\t(at {n(x + dx)} {n(y + dy)} 0)',
                    '\t\t\t(effects',
                    '\t\t\t\t(font',
                    '\t\t\t\t\t(size 1.27 1.27)',
                    '\t\t\t\t)']
            if not shown:
                out.append('\t\t\t\t(hide yes)')
            out += ['\t\t\t)', '\t\t)']

        for num in sorted(libs.pins(lib_id), key=lambda s: (len(s), s)):
            out += [f'\t\t(pin {q(num)}',
                    f'\t\t\t(uuid {q(uid(f"pin/{ref}/{num}"))})',
                    '\t\t)']

        out += ['\t\t(instances',
                f'\t\t\t(project {q(PROJECT)}',
                f'\t\t\t\t(path {q("/" + self.root_uuid)}',
                f'\t\t\t\t\t(reference {q(ref)})',
                '\t\t\t\t\t(unit 1)',
                '\t\t\t\t)',
                '\t\t\t)',
                '\t\t)',
                '\t)']
        self.items.append('\n'.join(out))
        return at

    # ------------------------------------------------------------------ nets
    def wire(self, a, b):
        if a == b:
            return
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError(f'diagonal wire {a}->{b}; route it in two segments')
        self.wires.append((a, b))
        self.items.append('\n'.join([
            '\t(wire',
            '\t\t(pts',
            f'\t\t\t(xy {n(a[0])} {n(a[1])}) (xy {n(b[0])} {n(b[1])})',
            '\t\t)',
            '\t\t(stroke',
            '\t\t\t(width 0)',
            '\t\t\t(type default)',
            '\t\t)',
            f'\t\t(uuid {q(uid(f"wire/{a}/{b}"))})',
            '\t)']))

    def route(self, *points):
        """Wire through a list of points, inserting the elbow for each L-bend."""
        pts = list(points)
        for a, b in zip(pts, pts[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                mid = (b[0], a[1])
                self.wire(a, mid)
                self.junction(mid)
                self.wire(mid, b)
            else:
                self.wire(a, b)

    def junction(self, at):
        self.items.append('\n'.join([
            '\t(junction',
            f'\t\t(at {n(at[0])} {n(at[1])})',
            '\t\t(diameter 0)',
            '\t\t(color 0 0 0 0)',
            f'\t\t(uuid {q(uid(f"junc/{at}"))})',
            '\t)']))

    def label(self, name, at, angle=0, glob=True, shape='input'):
        """A (global_)label pinning `at` to net `name`. angle: 0=text right, 180=left."""
        self.labels.setdefault(name, []).append(at)
        tag = 'global_label' if glob else 'label'
        just = 'right' if int(angle) == 180 else 'left'
        out = [f'\t({tag} {q(name)}']
        if glob:
            out.append(f'\t\t(shape {shape})')
        out += [f'\t\t(at {n(at[0])} {n(at[1])} {int(angle)})',
                '\t\t(fields_autoplaced yes)',
                '\t\t(effects',
                '\t\t\t(font',
                '\t\t\t\t(size 1.27 1.27)',
                '\t\t\t)',
                f'\t\t\t(justify {just})',
                '\t\t)',
                f'\t\t(uuid {q(uid(f"lbl/{name}/{at}"))})']
        if glob:
            out += ['\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}"',
                    f'\t\t\t(at {n(at[0])} {n(at[1])} 0)',
                    '\t\t\t(effects',
                    '\t\t\t\t(font',
                    '\t\t\t\t\t(size 1.27 1.27)',
                    '\t\t\t\t)',
                    '\t\t\t\t(hide yes)',
                    '\t\t\t)',
                    '\t\t)']
        out.append('\t)')
        self.items.append('\n'.join(out))

    def stub(self, name, pin_at, length=7.62, side='left', glob=True):
        """Short wire off a pin ending in a label. side = which way the wire runs."""
        dx = -length if side == 'left' else length
        end = (round(pin_at[0] + dx, 2), pin_at[1])
        self.wire(pin_at, end)
        self.label(name, end, angle=180 if side == 'left' else 0, glob=glob)
        return end

    def vstub(self, name, pin_at, length=7.62, side='up', glob=True):
        dy = -length if side == 'up' else length
        end = (pin_at[0], round(pin_at[1] + dy, 2))
        self.wire(pin_at, end)
        self.label(name, end, angle=0, glob=glob)
        return end

    def no_connect(self, at):
        self.items.append('\n'.join([
            '\t(no_connect',
            f'\t\t(at {n(at[0])} {n(at[1])})',
            f'\t\t(uuid {q(uid(f"nc/{at}"))})',
            '\t)']))

    def text(self, body, at, size=2.54, bold=True):
        out = [f'\t(text {q(body)}',
               f'\t\t(at {n(at[0])} {n(at[1])} 0)',
               '\t\t(effects',
               '\t\t\t(font',
               f'\t\t\t\t(size {n(size)} {n(size)})']
        if bold:
            out.append('\t\t\t\t(bold yes)')
        out += ['\t\t\t)',
                '\t\t\t(justify left bottom)',
                '\t\t)',
                f'\t\t(uuid {q(uid(f"text/{at}/{body[:24]}"))})',
                '\t)']
        self.items.append('\n'.join(out))

    # ------------------------------------------------------------------ output
    def render(self):
        libsyms = ['\t(lib_symbols']
        for lib_id in sorted(self.libids):
            libsyms.append(dump(self.libids[lib_id], 2))
        libsyms.append('\t)')
        return '\n'.join([
            '(kicad_sch',
            f'\t(version {VERSION})',
            f'\t(generator {q(GENERATOR)})',
            f'\t(generator_version {q(GEN_VERSION)})',
            f'\t(uuid {q(self.root_uuid)})',
            f'\t(paper {q(self.paper)})',
            '\n'.join(libsyms),
            '\n'.join(self.items),
            '\t(sheet_instances',
            '\t\t(path "/"',
            '\t\t\t(page "1")',
            '\t\t)',
            '\t)',
            '\t(embedded_fonts no)',
            ')',
            ''])

    def write(self, path):
        with open(path, 'w') as fh:
            fh.write(self.render())
        return path

    # ------------------------------------------------------------------ checks
    def check_bounds(self, margin=10.0):
        """Every placed item must sit inside the paper."""
        w, h = PAPER_SIZE[self.paper]
        bad = []
        for pts in self.labels.values():
            bad += [p for p in pts
                    if not (margin <= p[0] <= w - margin and margin <= p[1] <= h - margin)]
        for a, b in self.wires:
            for p in (a, b):
                if not (margin <= p[0] <= w - margin and margin <= p[1] <= h - margin):
                    bad.append(p)
        return bad
