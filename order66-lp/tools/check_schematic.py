#!/usr/bin/env python3
"""
Assert the generated schematic is electrically what we intended, by checking the
exported netlist rather than the drawing.

These are the checks ERC cannot do: that the matrix covers all 60 unique (row, col)
pairs, that every diode faces the right way, that the LED chain is one unbroken
path, and that the MCU pin assignment agrees with the ZMK shield overlay. A reversed
diode or a swapped row/col is silent in ERC and expensive in fab.

Run: python3 tools/check_schematic.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sexpr import parse, get, getall  # noqa: E402

SCH = os.path.join(ROOT, 'pcb', 'order66-lp.kicad_sch')
OVERLAY = os.path.join(ROOT, 'zmk', 'boards', 'shields', 'order66_lp', 'order66_lp.overlay')
NET = '/tmp/order66lp.net'
PHYS_ROWS, PHYS_COLS = 5, 12     # physical key grid
EL_ROWS, EL_COLS = 11, 6         # electrical matrix
N_KEYS = PHYS_ROWS * PHYS_COLS   # 60
N_BTN = 2                        # dedicated mouse buttons
N_SW = N_KEYS + N_BTN            # 62 matrix positions used

fails = []
notes = []


def check(cond, msg):
    if cond:
        print(f'  ok   {msg}')
    else:
        print(f'  FAIL {msg}')
        fails.append(msg)


def export_netlist():
    cfg = '/tmp/order66lp-kicad-cfg'
    env = dict(os.environ, KICAD_CONFIG_HOME=cfg)
    if not os.path.isdir(os.path.join(cfg, '10.0')):
        subprocess.run([os.path.join(HERE, 'erc.sh')], check=False,
                       capture_output=True, env=env)
    r = subprocess.run(['kicad-cli', 'sch', 'export', 'netlist',
                        '--format', 'kicadsexpr', '-o', NET, SCH],
                       capture_output=True, text=True, env=env)
    if not os.path.exists(NET):
        print(r.stdout, r.stderr)
        sys.exit('could not export netlist')


def load():
    root = parse(open(NET).read())[0]
    nets = {}
    for n in getall(get(root, 'nets'), 'net'):
        name = str(get(n, 'name')[1])
        nodes = []
        for nd in getall(n, 'node'):
            nodes.append((str(get(nd, 'ref')[1]), str(get(nd, 'pin')[1])))
        nets[name] = nodes
    parts = {}
    comps = get(root, 'components')
    for c in getall(comps, 'comp'):
        ref = str(get(c, 'ref')[1])
        val = get(c, 'value')
        fp = get(c, 'footprint')
        parts[ref] = (str(val[1]) if val else '', str(fp[1]) if fp else '')
    return nets, parts


def net_of(nets, ref, pin):
    """Which net a given pin sits on."""
    for name, nodes in nets.items():
        if (ref, pin) in nodes:
            return name
    return None


def main():
    export_netlist()
    nets, parts = load()
    print(f'netlist: {len(nets)} nets, {len(parts)} components\n')

    # ---------------------------------------------------------------- matrix
    print('key matrix')
    switches = sorted((r for r in parts if re.fullmatch(r'SW\d+', r)),
                      key=lambda r: int(r[2:]))
    keys = [r for r in switches if int(r[2:]) <= N_SW]
    check(len(keys) == N_SW,
          f'{N_KEYS} keys + {N_BTN} mouse buttons = {N_SW} matrix switches '
          f'(found {len(keys)})')

    pairs = {}
    bad_dir = []
    for sw in keys:
        k = int(sw[2:])
        col = net_of(nets, sw, '2')
        anode_net = net_of(nets, sw, '1')
        d = f'D{k}'
        # pin 1 of 1N4148WS is the cathode, pin 2 the anode
        d_cathode = net_of(nets, d, '1')
        d_anode = net_of(nets, d, '2')
        if d_anode != anode_net:
            bad_dir.append(f'{sw}: anode net {d_anode} != switch net {anode_net}')
        if not (d_cathode or '').startswith('ROW'):
            bad_dir.append(f'{d}: cathode on {d_cathode}, expected a ROW')
        if not (col or '').startswith('COL'):
            bad_dir.append(f'{sw}: pin 2 on {col}, expected a COL')
        pairs.setdefault((d_cathode, col), []).append(sw)

    check(not bad_dir, 'every diode is col2row (anode to switch, cathode to ROW)')
    for b in bad_dir[:5]:
        print(f'       {b}')

    dupes = {k: v for k, v in pairs.items() if len(v) > 1}
    check(not dupes, f'all {N_SW} (row, col) pairs unique ({len(dupes)} collisions)')
    for k, v in list(dupes.items())[:5]:
        print(f'       {k} used by {v}')

    grid = {(f'ROW{r}', f'COL{c}') for r in range(EL_ROWS) for c in range(EL_COLS)}
    check(set(pairs) <= grid,
          f'every pair lies inside the {EL_ROWS}x{EL_COLS} matrix')
    check(len(pairs) == N_SW, f'{N_SW} of {len(grid)} positions used')
    spare = grid - set(pairs)
    check(len(spare) == len(grid) - N_SW,
          f'{len(grid) - N_SW} spare positions for later ({sorted(spare)})')

    # The half-split mapping is the point of the 6x11 shape: rows 0-4 must belong to
    # the left half only, rows 5-9 to the right half only, row 10 to the buttons.
    left = {p for p in pairs if int(p[0][3:]) <= 4}
    right = {p for p in pairs if 5 <= int(p[0][3:]) <= 9}
    btn = {p for p in pairs if int(p[0][3:]) == EL_ROWS - 1}
    check(len(left) == 30 and len(right) == 30,
          f'half-split holds: {len(left)} keys on rows 0-4, {len(right)} on rows 5-9')
    check(len(btn) == N_BTN, f'{N_BTN} switches on the mouse-button row')

    # ---------------------------------------------------------------- backlight
    print('\nbacklight')
    leds = [r for r in parts if re.fullmatch(r'LED\d+', r)]
    check(len(leds) == N_KEYS,
          f'{N_KEYS} LEDs - one per key, none on the mouse buttons '
          f'(found {len(leds)})')

    # Walk the chain: LED n pin 2 (DOUT) must share a net with LED n+1 pin 3 (DIN).
    chain, seen, cur = [], set(), 'LED1'
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        dout = net_of(nets, cur, '2')
        nxt = None
        for ref, pin in nets.get(dout, []):
            if pin == '3' and ref != cur and ref.startswith('LED'):
                nxt = ref
                break
        cur = nxt
    check(len(chain) == N_KEYS,
          f'LED chain is one unbroken path of {N_KEYS} (walked {len(chain)})')

    first_din = net_of(nets, 'LED1', '3')
    check(first_din == 'LED_DIN_5V', f'chain starts on LED_DIN_5V (got {first_din})')

    for ref in leds:
        if net_of(nets, ref, '1') != 'VLED':
            fails.append(f'{ref} VDD not on VLED')
        if net_of(nets, ref, '4') != 'GND':
            fails.append(f'{ref} VSS not on GND')
    check(all(net_of(nets, r, '1') == 'VLED' for r in leds), 'every LED VDD on VLED')
    check(all(net_of(nets, r, '4') == 'GND' for r in leds), 'every LED VSS on GND')

    caps = [r for r in parts if re.fullmatch(r'C1\d\d', r)]
    check(len(caps) == N_KEYS, f'{N_KEYS} LED decoupling caps (found {len(caps)})')

    # ---------------------------------------------------------------- power
    print('\nLED power chain')
    expect = [
        ('Q1', '2', 'VBATT+',    'Q1 source on the battery rail'),
        ('Q1', '3', 'VBATT_LED', 'Q1 drain feeds the boost input'),
        ('Q1', '1', 'Q1_G',      'Q1 gate on its own node'),
        ('Q2', '3', 'Q1_G',      'Q2 drain pulls Q1 gate down'),
        ('Q2', '2', 'GND',       'Q2 source grounded'),
        ('Q2', '1', 'LED_EN',    'Q2 gate driven by the enable node'),
        ('R2', '1', 'VCC',       'enable node comes from VCC (ZMK ext_power)'),
        ('U2', '6', 'VBATT_LED', 'boost VIN downstream of Q1'),
        ('U2', '3', 'VCC',       'boost EN on VCC'),
        ('U2', '5', 'BST_SW',    'boost switch node'),
        ('L1', '1', 'VBATT_LED', 'inductor from the switched battery rail'),
        ('L1', '2', 'BST_SW',    'inductor into the switch node'),
        ('D63', '2', 'BST_SW',   'Schottky anode on the switch node'),
        ('D63', '1', 'VLED',     'Schottky cathode makes VLED'),
        ('U3', '5', 'VLED',      'level shifter powered from VLED'),
        ('U3', '1', 'GND',       'level shifter OE tied low (output enabled)'),
        ('U3', '4', 'LED_DIN_PRE', 'level shifter output'),
        ('R8', '2', 'LED_DIN_5V',  'series resistor into the LED chain'),
        ('R7', '1', 'LED_DIN_3V3', 'buffer input from the MCU'),
    ]
    for ref, pin, want_net, desc in expect:
        got = net_of(nets, ref, pin)
        check(got == want_net, f'{desc} ({ref}.{pin} = {got})')

    # Q1 must be the only path from the battery into the boost.
    vb = {r for r, _ in nets.get('VBATT_LED', [])}
    check(vb and 'Q1' in vb and not (vb & {'J1', 'SW62', 'SW63'}),
          f'VBATT_LED reachable only through Q1 (members: {sorted(vb)})')

    # ---------------------------------------------------------------- MCU
    print('\nMCU pin assignment')
    nano_pins = {p: n for n, nodes in nets.items() for r, p in nodes if r == 'U1'}
    used = sorted(n for n in nano_pins.values() if re.fullmatch(r'(ROW|COL)\d+', n))
    want_pins = EL_ROWS + EL_COLS
    check(len(used) == want_pins, f'{want_pins} matrix GPIO used (found {len(used)})')
    check(len(set(used)) == want_pins, 'no matrix net on two MCU pins')
    gpio = [n for n in nano_pins.values()
            if n not in ('GND', 'VCC', 'RST', 'VBATT+')]
    check(len(gpio) == len(set(gpio)) == 21,
          f'all 21 exposed GPIO assigned exactly once (found {len(gpio)})')
    check(nano_pins.get('24') == 'VBATT+', f"BATIN on VBATT+ (got {nano_pins.get('24')})")
    check(nano_pins.get('21') == 'VCC', f"VCC pin on VCC (got {nano_pins.get('21')})")
    check(nano_pins.get('1') == 'LED_DIN_3V3',
          f"P0.06 drives the LED chain (got {nano_pins.get('1')})")

    # ---------------------------------------------------------------- trackpad
    print('\ntrackpad')
    for ref, pin, want_net, desc in (
            ('J4', '9', 'TP_SCL', 'FFC pin 9 is SCL'),
            ('J4', '10', 'TP_SDA', 'FFC pin 10 is SDA'),
            ('J4', '11', 'GND', 'FFC pin 11 is GND'),
            ('J4', '12', 'VCC', 'FFC pin 12 is VDD, on the switchable rail'),
            ('J4', '4', 'TP_DR', 'FFC pin 4 is data-ready')):
        got = net_of(nets, ref, pin)
        check(got == want_net, f'{desc} ({ref}.{pin} = {got})')
    # KiCad names a no-connect pin's net 'unconnected-(J4-PadN)' rather than leaving
    # it out of the netlist, so check for that shape instead of None.
    for pin in ('1', '2', '3', '5', '6', '7', '8'):
        got = net_of(nets, 'J4', pin)
        check(got is None or got.startswith('unconnected-'),
              f'FFC pin {pin} not connected (SPI-only or a Pinnacle button)')
    for net in ('TP_SDA', 'TP_SCL'):
        members = {r for r, _ in nets.get(net, [])}
        check({'U1', 'J4'} <= members,
              f'{net} reaches both the MCU and the FFC ({sorted(members)})')
        check(any(r in ('R9', 'R10') for r in members),
              f'{net} has a pull-up (members {sorted(members)})')

    # ---------------------------------------------------------------- firmware
    print('\nschematic vs ZMK overlay')
    if not os.path.exists(OVERLAY):
        notes.append(f'overlay not found at {OVERLAY}; skipped cross-check')
        print('  --   overlay not present yet, skipped')
    else:
        txt = open(OVERLAY).read()
        pinmap = {}
        for m in re.finditer(r'<&gpio(\d) (\d+)[^>]*>\s*(?://\s*(\w+))?', txt):
            if m.group(3):
                pinmap[m.group(3).upper()] = f'P{m.group(1)}.{int(m.group(2)):02d}'

        # nice!nano module pin number -> nRF port.pin, from the symbol's own pin names
        sys.path.insert(0, HERE)
        import libs
        nano = {}
        for num, (_, _, _, name, _) in libs.pins('nice_nano:nice_nano').items():
            m = re.search(r'P(\d)\.(\d+)', name)
            if m:
                nano[num] = f'P{m.group(1)}.{int(m.group(2)):02d}'

        mismatch = []
        for pin, net in nano_pins.items():
            if not re.fullmatch(r'(ROW|COL)\d+', net):
                continue
            want_gpio = pinmap.get(net)
            got_gpio = nano.get(pin)
            if want_gpio and got_gpio and want_gpio != got_gpio:
                mismatch.append(f'{net}: schematic {got_gpio} vs overlay {want_gpio}')
        check(not mismatch,
              f'all {EL_ROWS + EL_COLS} matrix pins agree with the overlay')
        for m in mismatch[:8]:
            print(f'       {m}')
        covered = [n for n in pinmap if re.fullmatch(r'(ROW|COL)\d+', n)]
        check(len(covered) == EL_ROWS + EL_COLS,
              f'overlay declares {EL_ROWS + EL_COLS} matrix GPIO (found {len(covered)})')

    # ---------------------------------------------------------------- summary
    print()
    for n in notes:
        print(f'note: {n}')
    if fails:
        print(f'\n{len(fails)} CHECK(S) FAILED')
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
