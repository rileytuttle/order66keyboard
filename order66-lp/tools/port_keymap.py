#!/usr/bin/env python3
"""
Port the v1.0 order66 keymap (6x12 = 72 bindings per layer) to order66-lp (5x12 = 60).

The old matrix_transform listed row 0 first and row 0 was &none / &trans in every
layer -- those were the six AUX keys, which never did anything in firmware. So the
port is simply: drop the first 12 bindings of each layer.

Why this is a script and not sed:
  * The `gaming` layer's last row wraps, with `&tog GAMING>;` alone on its own line,
    so anything line-based corrupts it.
  * The `default_layer` has a commented-out row that itself contains & tokens, so
    comments have to be stripped before counting.

Run: python3 tools/port_keymap.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, os.pardir, 'zmk-modules', 'order66-shield',
                   'boards', 'shields', 'order66', 'order66.keymap')
DST = os.path.join(ROOT, 'zmk', 'boards', 'shields', 'order66_lp', 'order66_lp.keymap')

OLD_COLS, OLD_ROWS = 12, 6
NEW_ROWS = 5
DROP = OLD_COLS  # the dead top row

# Bindings for hardware the v1.0 keymap had no concept of. Each one lands in a slot
# that is &trans after the port, and the porter refuses to overwrite anything else.
# Indices are into the 60 post-port bindings (row * 12 + col).
ADDITIONS = {
    # ZMK Studio locking is implied on, so without an unlock binding Studio can
    # connect but never commit a change.
    'adjust_layer': {
        36: '&studio_unlock',
    },
    # Backlight: new hardware, and ON_START=n means it would be unreachable
    # otherwise. Third row of bluetooth_control, the layer already holding
    # the &ext_power bindings that gate the same rail.
    'bluetooth_control': {
        24: '&rgb_ug RGB_TOG',
        25: '&rgb_ug RGB_BRI',
        26: '&rgb_ug RGB_BRD',
        27: '&rgb_ug RGB_HUI',
        28: '&rgb_ug RGB_HUD',
        29: '&rgb_ug RGB_EFF',
    },
}

EXTRA_INCLUDE = '#include <dt-bindings/zmk/rgb.h>'


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def split_bindings(body):
    """Split a bindings body into individual '&...' bindings."""
    body = strip_comments(body)
    parts = body.split('&')
    if parts[0].strip():
        raise ValueError(f'unexpected text before first binding: {parts[0]!r}')
    return ['&' + p.strip() for p in parts[1:] if p.strip()]


def render(bindings, indent='                '):
    """Lay the bindings out 12 per row, columns padded to line up."""
    rows = [bindings[i:i + OLD_COLS] for i in range(0, len(bindings), OLD_COLS)]
    width = max(len(b) for b in bindings) + 2
    out = []
    for row in rows:
        out.append(indent + ''.join(b.ljust(width) for b in row).rstrip())
    return '\n'.join(out)


def main():
    src = os.path.normpath(SRC)
    if not os.path.exists(src):
        sys.exit(f'source keymap not found: {src}')
    text = open(src).read()

    layers = []
    errors = []

    def convert(match):
        head, body, tail = match.group(1), match.group(2), match.group(3)
        try:
            b = split_bindings(body)
        except ValueError as e:
            errors.append(str(e))
            return match.group(0)
        name = layer_name_at(text, match.start())
        if len(b) != OLD_COLS * OLD_ROWS:
            errors.append(f'{name}: expected {OLD_COLS * OLD_ROWS} bindings, got {len(b)}')
            return match.group(0)
        dropped, kept = b[:DROP], b[DROP:]
        if any(d not in ('&none', '&trans') for d in dropped):
            errors.append(f'{name}: top row is not all &none/&trans: {dropped}')
            return match.group(0)
        if len(kept) != OLD_COLS * NEW_ROWS:
            errors.append(f'{name}: kept {len(kept)}, expected {OLD_COLS * NEW_ROWS}')
            return match.group(0)
        added = 0
        for idx, binding in ADDITIONS.get(name, {}).items():
            if kept[idx] != '&trans':
                errors.append(f'{name}: slot {idx} holds {kept[idx]!r}, '
                              f'refusing to overwrite it with {binding!r}')
                return match.group(0)
            kept[idx] = binding
            added += 1
        layers.append((name, len(b), len(kept), added))
        return f'{head}\n{render(kept)}\n            {tail}'

    out = re.sub(r'(bindings\s*=\s*<)(.*?)(>\s*;)', convert, text, flags=re.S)

    # The ASCII-art legend above default_layer documents 6 rows (it repeats the ESC
    # row); every other layer's legend already showed 5. Drop the extra leading row
    # from any block that has 6, so the legend matches the bindings below it.
    def trim_legend(m):
        rows = m.group(0).rstrip('\n').split('\n')
        return ('\n'.join(rows[1:]) + '\n') if len(rows) == OLD_ROWS else m.group(0)

    out = re.sub(r'(?:^[ \t]*//[ \t]*\|.*\n){2,}', trim_legend, out, flags=re.M)

    # rgb.h is needed for the &rgb_ug bindings added above.
    if EXTRA_INCLUDE not in out:
        out = out.replace('#include <dt-bindings/zmk/outputs.h>',
                          '#include <dt-bindings/zmk/outputs.h>\n' + EXTRA_INCLUDE, 1)
    banner = (
        '/*\n'
        ' * order66-lp keymap -- 5x12, 60 keys per layer.\n'
        ' *\n'
        ' * Ported from the v1.0 order66 keymap by tools/port_keymap.py, which drops the\n'
        ' * first 12 bindings of each layer: the old board had a 6-key top row wired as\n'
        ' * matrix row 0, and every layer bound all of it to &none / &trans.\n'
        ' *\n'
        ' * SPDX-License-Identifier: MIT\n'
        ' */\n')
    out = re.sub(r'\A/\*.*?\*/\n', banner, out, count=1, flags=re.S)

    if errors:
        print('ERRORS:')
        for e in errors:
            print('  ' + e)
        return 1

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, 'w') as fh:
        fh.write(out)

    print(f'wrote {DST}')
    for name, before, after, added in layers:
        extra = f'  (+{added} added)' if added else ''
        print(f'  {name:20s} {before} -> {after}{extra}')
    print(f'{len(layers)} layers ported')
    return 0


def layer_name_at(text, pos):
    """Nearest preceding `name {` block label, for error messages."""
    head = text[:pos]
    found = re.findall(r'(\w+)\s*\{', head)
    return found[-1] if found else '?'


if __name__ == '__main__':
    sys.exit(main())
