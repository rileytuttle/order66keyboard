#!/usr/bin/env python3
"""
Static verification of the ZMK shield against a ZMK checkout.

There is no Zephyr toolchain in this environment (no west / cmake / dtc / SDK), so
this cannot compile. What it does instead is check every externally-defined name the
shield depends on -- Kconfig symbols, devicetree bindings and compatibles, behaviour
labels, binding constants, and the shared physical layout's key count -- against the
ZMK tree. That catches typos and renames, which is most of what a build would catch
here. It is not a substitute for actually building.

Run: python3 tools/check_firmware.py [path/to/zmk]
     default: ../zmk  (upstream is the point; see the layout check below)
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHIELD = os.path.join(ROOT, 'zmk', 'boards', 'shields', 'order66_lp')
ZMK = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                      else os.path.join(ROOT, os.pardir, 'zmk'))
APP = os.path.join(ZMK, 'app')

# The upstream commit this repo's fork is based on. The fork's only reason to exist
# was patching the shared ortho_5x12 layout for the v1.0 board's 6-key top row, so
# the layout check runs against this instead of the fork's working tree.
UPSTREAM_BASE = '6b44d33d'

# Geometry, kept in step with tools/gen_schematic.py / gen_overlay.py
EL_ROWS, EL_COLS = 11, 6
N_KEYS = 5 * 12 + 2        # 60 keys + 2 dedicated mouse buttons

fails = []


def check(cond, msg):
    print(f'  {"ok  " if cond else "FAIL"} {msg}')
    if not cond:
        fails.append(msg)


def read(path):
    with open(path) as fh:
        return fh.read()


def grep_tree(pattern, *subdirs, flags=0):
    hits = []
    for sub in subdirs:
        base = os.path.join(APP, sub)
        for dirpath, _, names in os.walk(base):
            for nm in names:
                p = os.path.join(dirpath, nm)
                try:
                    if re.search(pattern, read(p), flags):
                        hits.append(p)
                except (UnicodeDecodeError, IsADirectoryError, PermissionError):
                    pass
    return hits


def main():
    if not os.path.isdir(APP):
        sys.exit(f'no ZMK app/ at {APP}')
    print(f'ZMK tree: {ZMK}\n')

    overlay = read(os.path.join(SHIELD, 'order66_lp.overlay'))
    # Upstream migrated to Zephyr hardware model v2: the board target is
    # `nice_nano//zmk` and board-specific shield overlays are named after it.
    board_ov = read(os.path.join(SHIELD, 'boards', 'nice_nano_nrf52840_zmk.overlay'))
    conf = read(os.path.join(SHIELD, 'order66_lp.conf'))
    kdef = read(os.path.join(SHIELD, 'Kconfig.defconfig'))
    kshield = read(os.path.join(SHIELD, 'Kconfig.shield'))
    keymap = read(os.path.join(SHIELD, 'order66_lp.keymap'))

    # ---------------------------------------------------------- shield plumbing
    print('shield plumbing')
    check('SHIELD_ORDER66_LP' in kshield and
          'shields_list_contains,order66_lp' in kshield,
          'Kconfig.shield guard matches the shield directory name')
    check('if SHIELD_ORDER66_LP' in kdef, 'Kconfig.defconfig is guarded by the shield symbol')
    for f in ('order66_lp.overlay', 'order66_lp.keymap', 'order66_lp.conf',
              'Kconfig.shield', 'Kconfig.defconfig', 'order66_lp.zmk.yml',
              'macros.dtsi'):
        check(os.path.exists(os.path.join(SHIELD, f)), f'{f} present')
    check(os.path.exists(os.path.join(ROOT, 'zmk', 'zephyr', 'module.yml')),
          'zephyr/module.yml present (makes this a ZMK module)')
    # The v1.0 shield shipped a .gitignore that hid macros.dtsi, so clones failed.
    gi = os.path.join(SHIELD, '.gitignore')
    check(not os.path.exists(gi) or 'macros.dtsi' not in read(gi),
          'macros.dtsi is not gitignored (the v1.0 bug)')

    # ---------------------------------------------------------- Kconfig symbols
    print('\nKconfig symbols exist in ZMK')
    kconfig_text = ''
    for dirpath, _, names in os.walk(APP):
        for nm in names:
            if nm.startswith('Kconfig'):
                try:
                    kconfig_text += read(os.path.join(dirpath, nm))
                except (UnicodeDecodeError, PermissionError):
                    pass
    used = set(re.findall(r'CONFIG_(\w+)', conf))
    used |= {m for m in re.findall(r'^config (\w+)', kdef, re.M)}
    used |= set(re.findall(r'select (\w+)', kdef))
    # Defined by Zephyr, not ZMK, so they are not in this tree to be found.
    external = {'WS2812_STRIP', 'SPI', 'I2C_NRFX', 'INPUT'}
    for sym in sorted(used - external):
        check(re.search(rf'^\s*(menu)?config {sym}\s*$', kconfig_text, re.M) is not None,
              f'CONFIG_{sym}')
    print(f'  --   skipped {sorted(external)} (Zephyr-defined, not in the ZMK tree)')

    # ---------------------------------------------------------- devicetree
    print('\ndevicetree bindings and compatibles')
    # Bindings are split between app/dts/bindings and app/module/dts/bindings, and a
    # binding declares its compatible via its *filename*, not its contents.
    def binding_exists(compat):
        for base in ('dts/bindings', 'module/dts/bindings'):
            root = os.path.join(APP, base)
            for dirpath, _, names in os.walk(root):
                if f'{compat}.yaml' in names:
                    return os.path.join(dirpath, f'{compat}.yaml')
        return None

    for compat in ('zmk,kscan-gpio-matrix', 'zmk,matrix-transform', 'zmk,physical-layout'):
        check(binding_exists(compat) is not None, f'binding for compatible "{compat}"')
    check(bool(grep_tree(r'worldsemi,ws2812-spi', 'boards')),
          'compatible "worldsemi,ws2812-spi" used by other ZMK shields')

    binding = binding_exists('zmk,kscan-gpio-matrix')
    if binding:
        b = read(binding)
        for prop in ('row-gpios', 'col-gpios', 'diode-direction'):
            check(prop in b, f'kscan property {prop}')
        dd = re.search(r'diode-direction = "(\w+)"', overlay)
        enum = re.search(r'enum:\s*((?:\s*-\s*\w+)+)', b)
        allowed = set(re.findall(r'-\s*(\w+)', enum.group(1))) if enum else set()
        check(dd and dd.group(1) in allowed,
              f'diode-direction "{dd and dd.group(1)}" is one of {sorted(allowed)}')
    else:
        fails.append('kscan-gpio-matrix binding not found')

    # wakeup-source is a generic Zephyr property (Zephyr is not vendored here), so
    # confirm it against upstream ZMK shields that put it on their kscan node.
    users = grep_tree(r'wakeup-source', 'boards/shields')
    check('wakeup-source' in overlay and len(users) >= 3,
          f'wakeup-source on the kscan node, as {len(users)} upstream shields do')

    for chosen in ('zmk,kscan', 'zmk,physical-layout', 'zmk,underglow'):
        check(bool(grep_tree(re.escape(chosen), 'src', 'boards', 'dts', 'include', 'module')),
              f'chosen node "{chosen}" is consumed by ZMK')

    # ---------------------------------------------------------- layout
    # This board defines its own physical layout rather than including ZMK's shared
    # ortho_5x12: that one has no central gap, and patching it is exactly what forced
    # the v1.0 board's fork. A layout in our own module needs no fork.
    print('\nphysical layout (ours, not ZMK\'s shared one)')
    inc = 'layouts/common/ortho_5x12/all1u.dtsi'
    check(inc not in overlay,
          'overlay does NOT include the shared ortho_5x12 (it has no gap)')
    check('compatible = "zmk,physical-layout"' in overlay,
          'overlay defines its own zmk,physical-layout')
    check('#include <physical_layouts.dtsi>' in overlay,
          'overlay includes physical_layouts.dtsi for &key_physical_attrs')
    n_attrs = len(re.findall(r'&key_physical_attrs', overlay))
    check(n_attrs == N_KEYS, f'physical layout has {N_KEYS} keys (found {n_attrs})')
    # the right half must be shifted by the gap
    xs = [int(m.group(3)) for m in re.finditer(
        r'&key_physical_attrs\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', overlay)]
    check(max(xs) > 1100,
          f'right half is offset for the central gap (max x = {max(xs)})')

    # Count keys in UPSTREAM, since the local fork has this file patched.
    upstream = None
    try:
        upstream = subprocess.run(
            ['git', '-C', ZMK, 'show', f'{UPSTREAM_BASE}:app/dts/{inc}'],
            capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    transform_keys = len(re.findall(r'RC\(\d+,\s*\d+\)', overlay))
    check(transform_keys == N_KEYS,
          f'matrix transform has {N_KEYS} RC() entries (found {transform_keys})')

    rows = re.search(r'rows = <(\d+)>', overlay)
    cols = re.search(r'columns = <(\d+)>', overlay)
    check(rows and rows.group(1) == str(EL_ROWS),
          f'transform rows = {EL_ROWS} (got {rows and rows.group(1)})')
    check(cols and cols.group(1) == str(EL_COLS),
          f'transform columns = {EL_COLS} (got {cols and cols.group(1)})')

    n_rows = len(re.findall(r'<&gpio\d+\s+\d+\s+\(GPIO_ACTIVE_HIGH\s*\|\s*GPIO_PULL_DOWN\)>', overlay))
    n_cols = len(re.findall(r'<&gpio\d+\s+\d+\s+GPIO_ACTIVE_HIGH>', overlay))
    check(n_rows == EL_ROWS, f'{EL_ROWS} row-gpios (found {n_rows})')
    check(n_cols == EL_COLS, f'{EL_COLS} col-gpios (found {n_cols})')

    print('  --   shared ortho_5x12 no longer used, so its key count is irrelevant')

    # ---------------------------------------------------------- trackpad
    print('\ntrackpad')
    check('cirque,pinnacle2' in board_ov, 'board overlay instantiates cirque,pinnacle2')
    check('reg = <0x2a>' in board_ov, 'I2C address 0x2a')
    check('data-ready-gpios' in board_ov, 'data-ready GPIO wired')
    check('zmk,input-listener' in board_ov,
          'an input-listener feeds the trackpad to the HID mouse report')
    check('nordic,nrf-twim' in board_ov, 'i2c0 overridden to the TWIM (DMA) variant')
    west = read(os.path.join(ROOT, 'zmk', 'config', 'west.yml'))
    check('cirque-input-module' in west, 'cirque-input-module is in the west manifest')
    m = re.search(r'name: cirque-input-module\s+remote: \S+\s+revision: (\S+)', west)
    check(bool(m) and re.fullmatch(r'[0-9a-f]{40}', m.group(1) or ''),
          f'cirque module pinned to a SHA, not a branch (got {m and m.group(1)})')
    for sym in ('CONFIG_I2C', 'CONFIG_I2C_NRFX', 'CONFIG_INPUT'):
        check(sym in conf, f'{sym} set in the shield .conf')

    # ---------------------------------------------------------- LED chain
    print('\nbacklight')
    chain = re.search(r'chain-length = <(\d+)>', board_ov)
    check(chain and chain.group(1) == '60',
          f'chain-length = 60 (got {chain and chain.group(1)})')
    psels = set(re.findall(r'NRF_PSEL\(SPIM_MOSI, (\d+), (\d+)\)', board_ov))
    check(psels == {('0', '6')}, f'LED data on P0.06 (got {sorted(psels)})')
    check('LED_COLOR_ID_GREEN LED_COLOR_ID_RED LED_COLOR_ID_BLUE' in board_ov,
          'colour-mapping is GRB')
    check('zmk,underglow = &led_strip' in board_ov, 'led_strip is chosen as zmk,underglow')

    # ---------------------------------------------------------- keymap
    print('\nkeymap')
    layers = re.findall(r'bindings\s*=\s*<(.*?)>\s*;', keymap, re.S)
    check(len(layers) == 9, f'9 layers (found {len(layers)})')
    for i, body in enumerate(layers):
        body = re.sub(r'//[^\n]*', '', body)
        cnt = len([p for p in body.split('&')[1:] if p.strip()])
        check(cnt == N_KEYS, f'layer {i} has {N_KEYS} bindings (found {cnt})')

    behaviours = sorted(set(re.findall(r'&(\w+)', re.sub(r'//[^\n]*', '', keymap))))
    LABEL = r'^\s*(?:/omit-if-no-ref/\s*)?(\w+):\s*[\w-]+\s*\{'
    local_macros = set(re.findall(LABEL,
                                  read(os.path.join(SHIELD, 'macros.dtsi')), re.M))
    builtin = set()
    for d in ('dts', 'module/dts'):
        for p in grep_tree(r'.', d):
            builtin |= set(re.findall(LABEL, read(p), re.M))
    missing = [b for b in behaviours
               if b not in builtin and b not in local_macros
               and not b.startswith(('macro_', 'key_physical_attrs', 'layout_'))]
    check(not missing, f'every &behaviour is defined (unresolved: {missing})')

    consts = sorted(set(re.findall(r'\b(RGB_\w+)', keymap)))
    rgb_h = os.path.join(APP, 'include', 'dt-bindings', 'zmk', 'rgb.h')
    if os.path.exists(rgb_h):
        defined = set(re.findall(r'#define (\w+)', read(rgb_h)))
        bad = [c for c in consts if c not in defined]
        check(not bad, f'all RGB_* constants defined in rgb.h (unknown: {bad})')
    check('dt-bindings/zmk/rgb.h' in keymap, 'keymap includes rgb.h for the &rgb_ug bindings')

    print()
    if fails:
        print(f'{len(fails)} CHECK(S) FAILED')
        return 1
    print('all static checks passed')
    print('NOTE: this checks names, not code -- it compiles nothing.')
    print('      To actually build (locally, against upstream ZMK):  nix build .#firmware')
    print('      See BUILDING.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
