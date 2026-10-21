#!/usr/bin/env python3
"""
Generate order66-lp.kicad_sch: a 5x12 Kailh Choc v1 ortholinear keyboard with
per-key SK6812MINI-E backlight, on a nice!nano v2.

Run:  python3 tools/gen_schematic.py
Then: python3 tools/check_schematic.py

Nets follow the same convention as the v1.0 board: everything is joined with global
labels rather than long wires, so each pin gets a short stub ending in its net name.

The key matrix, the LED array and the LED decoupling array are laid out for real and
are meant to be used as-is. The MCU and power blocks are correct but not prettified --
they are netlist-style stubs, and are expected to get a human layout pass in KiCad.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from schlib import Sch, uid  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'pcb', 'order66-lp.kicad_sch')

ROWS, COLS = 5, 12

# --- part numbers -----------------------------------------------------------------
SW = 'marbastlib-choc:choc_v1_SW_HS_CPG135001S30'
LED = 'marbastlib-choc:choc_SK6812MINI-E'
D_MATRIX = 'Diode:1N4148WS'
R, C, L = 'Device:R', 'Device:C', 'Device:L'
NANO = 'nice_nano:nice_nano'
CONN2 = 'Connector:Conn_01x02_Pin'
HOLE = 'Mechanical:MountingHole'

FP_R = 'Resistor_SMD:R_0402_1005Metric'
FP_C = 'Capacitor_SMD:C_0402_1005Metric'
FP_C_BIG = 'Capacitor_SMD:C_0805_2012Metric'
FP_C_BULK = 'Capacitor_SMD:C_1210_3225Metric'
FP_L = 'Inductor_SMD:L_Taiyo-Yuden_NR-30xx'
FP_HDR2 = 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical'
FP_HDR2H = 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal'
FP_JST = 'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical'
# B3F-10xx was split into per-variant footprints in newer KiCad libraries.
FP_RST = 'Button_Switch_THT:SW_TH_Tactile_Omron_B3F-100x'
FP_HOLE = 'MountingHole:MountingHole_2.7mm_M2.5'

# nice!nano v2 pin -> net. Columns are unchanged from the v1.0 board; rows are the old
# ROW1..ROW5 renumbered after dropping the 6-key top row.
NANO_NETS = {
    1:  'LED_DIN_3V3',   # TX0/P0.06  -- was nice!view CS; SPIM3 MOSI for the LED chain
    2:  'COL3',          # RX1/P0.08
    3:  'GND', 4: 'GND',
    5:  None,            # P0.17      -- spare (was nice!view MOSI)
    6:  None,            # P0.20      -- spare (was nice!view SCK)
    7:  'ROW4',          # P0.22
    8:  'COL4',          # P0.24
    9:  'COL5',          # P1.00
    10: 'COL6',          # P0.11
    11: 'COL9',          # P1.04
    12: 'COL10',         # P1.06
    13: 'ROW1',          # NFC1/P0.09
    14: 'ROW2',          # NFC2/P0.10
    15: 'ROW3',          # P1.11
    16: 'COL2',          # P1.13
    17: 'COL1',          # P1.15
    18: None,            # AIN0/P0.02 -- spare (was ROW0 of the old 6-row matrix)
    19: 'ROW0',          # AIN5/P0.29
    20: 'COL0',          # AIN7/P0.31
    21: 'VCC',           # switchable 3.3V rail, gated by ZMK ext_power (P0.13)
    22: 'RST',
    23: 'GND',
    24: 'VBATT+',        # BATIN/P0.04
    31: 'COL11',         # P1.01
    32: 'COL7',          # P1.02
    33: 'COL8',          # P1.07
}


def build():
    s = Sch(paper='A1', root_uuid='0d912afe-3c92-44f1-b16a-9458144618fa')

    key_matrix(s)
    led_array(s)
    led_decoupling(s)
    mcu(s)
    battery_and_switches(s)
    led_power(s)
    mounting_holes(s)
    power_flags(s)

    return s


def power_flags(s):
    """PWR_FLAG on every supply rail. Nets here are joined by global labels rather
    than power symbols, so without these ERC sees no driver for any power_in pin."""
    s.text('POWER FLAGS  --  ERC only; not parts', (520.7, 497.84))
    # VCC is omitted: the nice!nano's VCC pin is already a power output, so a flag
    # there would be a second driver on the net.
    rails = ['GND', 'BATT+', 'VBATT+', 'VBATT_LED', 'VLED']
    for i, net in enumerate(rails):
        at = (541.02 + i * 30.48, 520.7)
        s.symbol('power:PWR_FLAG', f'#FLG{i + 1:02d}', at, value='PWR_FLAG',
                 footprint='', in_bom=False, on_board=False,
                 ref_offset=(0, 5.08), val_offset=(0, 7.62), hide_value=True)
        s.vstub(net, s.pin('power:PWR_FLAG', at, 1), 7.62, 'up')


# ---------------------------------------------------------------- key matrix
def key_matrix(s):
    x0b, y0b, px, py = 30.48, 45.72, 38.1, 25.4
    s.text('KEY MATRIX  --  5 rows x 12 cols, 60 keys, col2row '
           '(COL -> switch -> diode anode, cathode -> ROW)', (30.48, 30.48))

    for r in range(ROWS):
        for c in range(COLS):
            k = r * COLS + c + 1
            x0 = x0b + c * px
            y0 = y0b + r * py

            d_at = (x0 + 11.43, y0)
            s.symbol(D_MATRIX, f'D{k}', d_at, value='1N4148WS', footprint='Diode_SMD:D_SOD-323')
            k_pin = s.pin(D_MATRIX, d_at, 1)      # cathode -> ROW
            a_pin = s.pin(D_MATRIX, d_at, 2)      # anode   -> switch

            sw_at = (x0 + 22.86, y0 + 2.54)
            s.symbol(SW, f'SW{k}', sw_at, value='CHOC_V1_HS',
                     ref_offset=(-1.27, -6.35), val_offset=(-1.27, 6.35), hide_value=True)
            p1 = s.pin(SW, sw_at, 1)              # upper-left  -> diode anode
            p2 = s.pin(SW, sw_at, 2)              # lower-right -> COL

            s.stub(f'ROW{r}', k_pin, 7.62, 'left')
            s.wire(a_pin, p1)
            s.stub(f'COL{c}', p2, 6.35, 'right')


# ---------------------------------------------------------------- backlight
def led_array(s):
    x0b, y0b, px, py = 33.02, 203.2, 20.32, 38.1
    s.text('BACKLIGHT  --  60x SK6812MINI-E, reverse mount in the Choc v1 centre window, '
           'one chain, GRB', (30.48, 185.42))

    for r in range(ROWS):
        for c in range(COLS):
            k = r * COLS + c + 1
            at = (x0b + c * px, y0b + r * py)
            s.symbol(LED, f'LED{k}', at, value='SK6812MINI-E',
                     ref_offset=(0, -17.78), val_offset=(0, 17.78), hide_value=True)

            din = s.pin(LED, at, 3)
            dout = s.pin(LED, at, 2)
            vdd = s.pin(LED, at, 1)
            vss = s.pin(LED, at, 4)

            s.vstub('VLED', vdd, 6.35, 'up')
            s.vstub('GND', vss, 6.35, 'down')

            if c == 0:
                s.stub('LED_DIN_5V' if r == 0 else f'LED_CHAIN{r}', din, 7.62, 'left')
            else:
                prev = (x0b + (c - 1) * px, y0b + r * py)
                s.wire(s.pin(LED, prev, 2), din)

            if c == COLS - 1:
                if r == ROWS - 1:
                    s.wire(dout, (dout[0] + 5.08, dout[1]))
                    s.no_connect((dout[0] + 5.08, dout[1]))
                else:
                    s.stub(f'LED_CHAIN{r + 1}', dout, 7.62, 'right')


def led_decoupling(s):
    """One 0.1uF per LED. Physical placement is a layout job; electrically they are
    all just VLED-to-GND, so they live in a tidy array here."""
    x0b, y0b, px, py = 302.26, 213.36, 15.24, 25.4
    s.text('LED DECOUPLING  --  one 0.1uF per LED, place each one at its LED on the PCB',
           (302.26, 185.42))

    for i in range(ROWS * COLS):
        r, c = divmod(i, COLS)
        at = (x0b + c * px, y0b + r * py)
        s.symbol(C, f'C{101 + i}', at, value='100n', footprint=FP_C,
                 ref_offset=(-6.35, -2.54), val_offset=(-6.35, 2.54), hide_value=(c > 0))
        s.vstub('VLED', s.pin(C, at, 1), 6.35, 'up')
        s.vstub('GND', s.pin(C, at, 2), 6.35, 'down')


# ---------------------------------------------------------------- MCU
def mcu(s):
    at = (579.12, 88.9)
    s.text('CONTROLLER  --  nice!nano v2, reverse mounted under the key field, '
           'USB at the back edge', (520.7, 30.48))
    s.symbol(NANO, 'U1', at, value='nice!nano v2',
             footprint='nice-nano-kicad:nice_nano',
             ref_offset=(0, -41.91), val_offset=(0, 41.91))

    for num, net in NANO_NETS.items():
        p = s.pin(NANO, at, num)
        if num in (31, 32, 33):
            if net is None:
                s.no_connect(p)
            else:
                s.vstub(net, p, 7.62, 'down')
            continue
        side = 'left' if p[0] < at[0] else 'right'
        if net is None:
            s.no_connect(p)
        else:
            s.stub(net, p, 7.62, side)


def battery_and_switches(s):
    s.text('BATTERY / POWER SWITCH / RESET / SWD', (520.7, 160.02))

    j1 = (541.02, 182.88)
    s.symbol(CONN2, 'J1', j1, value='Battery JST PH', footprint=FP_JST)
    s.stub('BATT+', s.pin(CONN2, j1, 1), 7.62, 'right')
    s.stub('GND', s.pin(CONN2, j1, 2), 7.62, 'right')

    # Two power-switch footprint options, both BATT+ -> VBATT+. Populate exactly one.
    sw62 = (541.02, 205.74)
    s.symbol('EG1206A:EG1206A', 'SW62', sw62, value='EG1206A',
             footprint='EG1206A:EG1206A_EWI', ref_offset=(0, -6.35), val_offset=(0, 6.35))
    s.no_connect(s.pin('EG1206A:EG1206A', sw62, 1))
    s.stub('BATT+', s.pin('EG1206A:EG1206A', sw62, 2), 7.62, 'right')
    s.stub('VBATT+', s.pin('EG1206A:EG1206A', sw62, 3), 7.62, 'right')

    sw63 = (541.02, 228.6)
    s.symbol('SSSS811101:SSSS811101', 'SW63', sw63, value='SSSS811101',
             footprint='SSSS811101:SW_SSSS811101', ref_offset=(0, -8.89), val_offset=(0, 8.89))
    s.stub('BATT+', s.pin('SSSS811101:SSSS811101', sw63, 1), 7.62, 'right')
    s.stub('VBATT+', s.pin('SSSS811101:SSSS811101', sw63, 2), 7.62, 'right')
    s.no_connect(s.pin('SSSS811101:SSSS811101', sw63, 3))

    rst = (701.04, 182.88)
    s.symbol('Switch:SW_Push', 'SW61', rst, value='RESET', footprint=FP_RST)
    s.stub('RST', s.pin('Switch:SW_Push', rst, 1), 7.62, 'left')
    s.stub('GND', s.pin('Switch:SW_Push', rst, 2), 7.62, 'right')

    # Two SWD breakout footprint options; neither is normally populated.
    for ref, pos, fp, note in (('J2', (701.04, 205.74), FP_HDR2H, 'SWD horizontal'),
                               ('J3', (701.04, 228.6), FP_HDR2, 'SWD millmax vertical')):
        s.symbol(CONN2, ref, pos, value=note, footprint=fp)
        s.stub('SWC', s.pin(CONN2, pos, 1), 7.62, 'right')
        s.stub('SWD', s.pin(CONN2, pos, 2), 7.62, 'right')


# ---------------------------------------------------------------- LED power
def led_power(s):
    """Battery -> P-FET hard cutoff -> boost to 5V -> level shifter -> LED chain.

    Q1 sits between the battery and the boost so that when the backlight is off the
    boost, the LEDs and the level shifter are all completely unpowered -- a boost's
    EN pin alone still leaks VIN to VOUT through the inductor and body diode. Q1's
    gate cannot be driven from 3.3V VCC directly (source sits at up to 4.2V, so
    Vgs would only be -0.9V), hence Q2 pulling the gate to ground.
    """
    s.text('LED POWER  --  VBATT+ -> Q1 hard cutoff -> U2 boost 5V -> U3 level shift '
           '-> LED chain.  Q1/Q2/U2.EN all gated by VCC (ZMK ext_power).', (520.7, 274.32))

    def part(lib, ref, at, value, fp, nets, **kw):
        s.symbol(lib, ref, at, value=value, footprint=fp, **kw)
        for num, net in nets.items():
            p = s.pin(lib, at, num)
            if net is None:
                s.no_connect(p)
                continue
            px, py = p
            ox, oy = at
            if abs(px - ox) >= abs(py - oy):
                s.stub(net, p, 7.62, 'left' if px < ox else 'right')
            else:
                s.vstub(net, p, 7.62, 'up' if py < oy else 'down')

    # High-side cutoff
    part('Transistor_FET:AO3401A', 'Q1', (541.02, 309.88), 'AO3401A',
         'Package_TO_SOT_SMD:SOT-23', {1: 'Q1_G', 2: 'VBATT+', 3: 'VBATT_LED'})
    part('Transistor_FET:BSS138', 'Q2', (601.98, 309.88), 'BSS138',
         'Package_TO_SOT_SMD:SOT-23', {1: 'LED_EN', 2: 'GND', 3: 'Q1_G'})
    part(R, 'R1', (541.02, 342.9), '100k', FP_R, {1: 'VBATT+', 2: 'Q1_G'})
    part(R, 'R2', (561.34, 342.9), '10k', FP_R, {1: 'VCC', 2: 'LED_EN'})
    part(R, 'R3', (581.66, 342.9), '100k', FP_R, {1: 'LED_EN', 2: 'GND'})

    # Boost
    part('Regulator_Switching:TPS61085DGK', 'U2', (662.94, 320.04), 'TPS61085DGK',
         'Package_SO:VSSOP-8_3x3mm_P0.65mm',
         {1: 'BST_COMP', 2: 'BST_FB', 3: 'VCC', 4: 'GND',
          5: 'BST_SW', 6: 'VBATT_LED', 7: 'VBATT_LED', 8: 'BST_SS'},
         ref_offset=(0, -14.0), val_offset=(0, 14.0))
    part(L, 'L1', (723.9, 309.88), '4.7uH', FP_L, {1: 'VBATT_LED', 2: 'BST_SW'})
    part('Diode:MBRA340', 'D61', (723.9, 342.9), 'MBRA340', 'Diode_SMD:D_SMA',
         {1: 'VLED', 2: 'BST_SW'})
    part(C, 'C1', (744.22, 309.88), '10u', FP_C_BIG, {1: 'VBATT_LED', 2: 'GND'})
    part(C, 'C2', (764.54, 309.88), '100n', FP_C, {1: 'VBATT_LED', 2: 'GND'})
    part(C, 'C3', (784.86, 309.88), '22u', FP_C_BIG, {1: 'VLED', 2: 'GND'})
    part(C, 'C4', (805.18, 309.88), '22u', FP_C_BIG, {1: 'VLED', 2: 'GND'})
    part(C, 'C5', (744.22, 374.65), '100u', FP_C_BULK, {1: 'VLED', 2: 'GND'})
    part(C, 'C6', (764.54, 374.65), '100u', FP_C_BULK, {1: 'VLED', 2: 'GND'})
    # 5.0V out: FB = 1.238V, so R4/R5 = (5/1.238)-1 = 3.04
    part(R, 'R4', (784.86, 374.65), '30k1', FP_R, {1: 'VLED', 2: 'BST_FB'})
    part(R, 'R5', (805.18, 374.65), '10k', FP_R, {1: 'BST_FB', 2: 'GND'})
    part(R, 'R6', (662.94, 374.65), '10k', FP_R, {1: 'BST_COMP', 2: 'BST_COMPC'})
    part(C, 'C7', (683.26, 374.65), '2n2', FP_C, {1: 'BST_COMPC', 2: 'GND'})
    part(C, 'C8', (703.58, 374.65), '10n', FP_C, {1: 'BST_SS', 2: 'GND'})

    # 3.3V -> 5V data buffer. OE is active low, tied low to keep the output enabled.
    part('74xGxx:74AHCT1G125', 'U3', (581.66, 406.4), '74AHCT1G125',
         'Package_TO_SOT_SMD:SOT-353_SC-70-5',
         {1: 'GND', 2: 'LED_DIN_BUF', 3: 'GND', 4: 'LED_DIN_PRE', 5: 'VLED'},
         ref_offset=(0, -14.0), val_offset=(0, 14.0))
    part(R, 'R7', (541.02, 406.4), '1k', FP_R, {1: 'LED_DIN_3V3', 2: 'LED_DIN_BUF'})
    part(R, 'R8', (640.08, 406.4), '330R', FP_R, {1: 'LED_DIN_PRE', 2: 'LED_DIN_5V'})


def mounting_holes(s):
    s.text('MOUNTING  --  6x M2.5', (520.7, 440.0))
    for i in range(6):
        at = (541.02 + (i % 3) * 25.4, 457.2 + (i // 3) * 20.32)
        s.symbol(HOLE, f'H{i + 1}', at, value='MountingHole', footprint=FP_HOLE,
                 ref_offset=(0, -5.08), val_offset=(0, 5.08), hide_value=True)


if __name__ == '__main__':
    sch = build()
    oob = sch.check_bounds()
    if oob:
        print(f'ERROR: {len(oob)} points outside paper {sch.paper}: {sorted(set(oob))[:8]}')
        sys.exit(1)
    sch.write(OUT)
    print(f'wrote {OUT}')
    print(f'  symbols : {len(sch.refs)}')
    print(f'  wires   : {len(sch.wires)}')
    print(f'  nets    : {len(sch.labels)}')
