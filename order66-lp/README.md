# order66-lp

A ground-up redesign of order66: **60-key 5×12 ortholinear** split by a **54 mm central
band**, **Kailh Choc v1 low profile only**, **per-key RGB backlight**, a **Cirque 40 mm
trackpad** with two dedicated mouse buttons, nice!nano v2, LiPo pouch battery.

Self-contained — nothing here points outside this directory, so it can be lifted into
its own repo with a `git mv`. (The one exception is `tools/port_keymap.py`, which reads
the v1.0 keymap from `../zmk-modules/`; it only needs to run once.)

Current state: **schematic and firmware are done and verified. There is no PCB layout
yet.**

## What changed from v1.0, and why

| | v1.0 | order66-lp |
|---|---|---|
| Keys | 66 (6×12 with only 6 of 12 top-row positions) | 60 (5×12) + 2 mouse buttons |
| Matrix | 6×12, geometric | **6 cols × 11 rows, half-split** |
| Pointing | none | Cirque TM040040 trackpad on I2C |
| Switches | MX hotswap, 19.05 mm | Kailh Choc v1 hotswap, **18.0 × 17.0 mm** |
| Diodes | THT **and** SMD footprint on every key | SMD only, 1N4148WS SOD-323 |
| Display | nice!view on a 1×05 riser | none |
| Battery | 18650 holder **and** LiPo JST | LiPo JST only |
| Backlight | none | 60 × SK6812MINI-E, one chain |
| Passives | **zero** | boost converter, load switch, level shifter |
| ZMK | **patched fork required** | upstream, unmodified |
| Board | 228.6 × 123.0 mm | **280.0 × 95.0 mm** (54 mm band, no back strip) |

Kept deliberately, as redundant build options: both power-switch footprints
(`SW62` EG1206A / `SW63` SSSS811101 — populate one) and both SWD header footprints
(`J2` horizontal / `J3` millmax vertical — normally unpopulated).

### The ZMK fork is gone

v1.0's six top-row `AUX` keys meant the board was not a standard ortholinear, so
ZMK's **shared** `app/dts/layouts/common/ortho_5x12/all1u.dtsi` — the generic layout
used by Contra, Preonic, boardsource5x12 and others — was patched in a fork to grow a
sixth row (commits `90dde5dd` *"back to basics. hacking this common code to get my
keyboard to work. will do it correctly later"* and `eab02c94`). That is the only
reason the root README says you must build locally instead of using
`zmk-config` + GitHub Actions.

All five commits on the fork serve features this board removes: two are that layout
hack, three are nice!view widget rotation. At a true 5×12 with no screen, **upstream
ZMK builds this board with no patches**, and `tools/check_firmware.py` verifies that
upstream's `ortho_5x12` has exactly the 60 keys this shield expects.

It also fixes a latent bug: the fork's patched layout has **71** `key_physical_attrs`
entries against a **72**-entry `position_map` and transform.

Note the distinction: this removes the need for the **fork**, not for a *module*. A
module is just the packaging that lets a `zmk-config` find an out-of-tree shield.

### Relationship to upstream `boardsource5x12`

This board is electrically the same thing as ZMK's own `boardsource5x12` shield:
5×12, `col2row`, nice!nano-compatible. Strip the comments and the **only** difference
between the two overlays is the GPIO lines and one node label. The part that actually
holds complexity -- the physical layout -- is shared: `ortho_5x12/all1u.dtsi` is the
same file Contra, Preonic and boardsource5x12 use.

So why a shield at all? Because `boardsource5x12` hard-codes its own pinout via
`&pro_micro` aliases, which on a nice!nano v2 resolve to:

| | |
|---|---|
| ROW0-4 | `P0.08`, **`P0.06`**, `P0.17`, `P0.20`, `P0.22` |
| COL0-11 | `P0.31`, `P0.29`, `P0.02`, `P1.15`, `P1.13`, `P1.11`, `P0.10`, `P0.09`, `P1.06`, `P1.04`, `P0.11`, `P1.00` |

Using it verbatim would mean routing the PCB to that order. Only 3 of 17 positions
match the assignment here, it takes `P0.06` (the LED data pin) as ROW1, it uses both
NFC pins anyway, and it leaves only `P0.24`/`P1.01`/`P1.02`/`P1.07` spare -- one of
which would become the LED data line. It is a real option, and `nRF52840` SPIM pin
selection is flexible enough to accommodate it, but it trades free routing on a board
whose controller is bottom-mounted and shifted left for someone else's pin order.

The 17 lines of pin definitions in `order66_lp.overlay` are the price of that freedom.
If you would rather pay the routing constraint and drop the shield entirely, re-pin
before layout: the keymap would move to a `zmk-config`, and the backlight devicetree
would have to live inside the `.keymap` file, since a `zmk-config` has no per-shield
board overlay.

## Layout

```
order66-lp/
  pcb/           KiCad 10 project, schematic, exported PDF + BOM
  libraries/     vendored symbol/footprint libraries (see libraries/marbastlib/README.md)
  zmk/           ZMK shield module: boards/shields/order66_lp/
  tools/         schematic generator and verification scripts
```

## Switch and LED footprints

From [`ebastler/marbastlib`](https://github.com/ebastler/marbastlib) (CERN-OHL-P-2.0),
whose current release targets KiCad 10:

- `SW_choc_v1_HS_CPG135001S30_1u` — Choc v1 hotswap. Centre NPTH Ø3.4 at (0,0), pegs
  Ø1.7 at (±5.50, 0), switch pins Ø3.0 at (5, 3.75) and (0, 5.95), socket pads
  reaching x ≈ 9.57.
- `LED_choc_6028R` — *"Add-on for regular choc-footprints with 6028 reverse mount
  LED"*. Four SMD pads at (±2.725, ±0.75) plus a **3.4 × 3.0 mm Edge.Cuts cutout at
  the origin**.

The add-on's cutout lands exactly on the switch footprint's Ø3.4 centre hole: it is
designed to overlay the switch and turn that round hole into the routed slot the LED
drops into. Choc v1's LED window is in the switch **centre**, which is why
shine-through comes up through the middle of the stem.

**Shine-through keycaps** (Choc v1 only, which this design commits to):
[MBK Legend Glow R2](https://keycapsss.com/keyboard-parts/keycaps/181/mbk-legend-glow-r2-black-choc-low-profile-keycap-set)
is the main set — translucent ABS, opaque PU coat, laser-etched legends, described as
adapted to shine uniformly through the Choc LED window.
[MBK Dot Glow](https://www.littlekeyboards.com/products/mbk-glow-keycaps) is the
single-dot version; [icon caps](https://keycapsss.com/Choc-Low-Profile-Keycaps-with-Shine-Through-Icon-Dots/KC10162-1dot)
and translucent [Holo Crystal](https://keycapsss.com/MBK-Choc-Holo-Crystal-Keycap/KC10139-1U)
also exist. Check the kit covers a 5×12 ortho before ordering.

## Matrix: 6 columns × 11 rows, half-split

A 5×12 matrix is 17 pins for 60 positions and is **100 % full** — no room for the mouse
buttons. 6×11 is *the same 17 pins* but 66 positions, so it pays for the buttons and
still leaves 4 spare. It is a strict improvement, not a trade.

- electrical **columns 0–5** = the six physical columns of a half, shared by both halves
- electrical **rows 0–4** = left half, **rows 5–9** = right half
- electrical **row 10** = the two mouse buttons (cols 0–1); cols 2–5 spare

Row nets stay local to one half rather than spanning the board. An 8×8 matrix would have
saved one further pin but cannot be mapped onto two 6-column halves, so ~20 of the 60
keys would land on nets that don't match their physical position.

## Pin assignment — all 21 exposed GPIO used

`COL0–5` and `ROW0–4` keep the pins they had on the 5×12 board; the old `COL6–11` pins
become the right half's `ROW5–10`, so this is a minimal remap rather than a reshuffle.

| | pins |
|---|---|
| COL0–5 | `P0.31` `P1.15` `P1.13` `P0.08` `P0.24` `P1.00` |
| ROW0–4 (left half) | `P0.29` `P0.09` `P0.10` `P1.11` `P0.22` |
| ROW5–10 (right half + buttons) | `P0.11` `P1.02` `P1.07` `P1.04` `P1.06` `P1.01` |
| LED data | `P0.06` (SPIM3 MOSI) |
| trackpad I2C | `P0.17` SDA / `P0.20` SCL — the nice!nano's own `&i2c0` pins |
| trackpad data-ready | `P0.02` |

17 matrix + 1 LED + 2 I2C + 1 IRQ = **21 of 21**. No spare GPIO, but 4 spare matrix
positions.

The I2C assignment is a lucky one: the nice!nano already pins `&i2c0` to TWIM_SDA on
`P0.17` and TWIM_SCL on `P0.20`, so the firmware needs no pinctrl override at all.

## Trackpad

Cirque GlidePoint **TM040040** — 40.0 mm module, 38.0 mm active, 5.61 mm thick with
components — on I2C at `0x2a`, via a 12-way 0.5 mm FFC tail into a
`CON_FH33J-12S-0.5SH` (already vendored in marbastlib).

**It must be standoff-mounted on the front face, not flush in a cutout.** The PCB staying
solid behind it is what lets the controller sit directly on the back; with a cutout, a
40 mm pad + 33 mm nano + 17 mm of buttons needs 90 mm of a band that only has 85. On
standoffs the touch surface lands ~6 mm above the PCB, well under the ~11–12 mm MBK
keycap plane, so it reads as a shallow well.

Two things to remember: the module ships **strapped for SPI — remove its R1** for I2C,
and a bare module on our own connector means **we supply the I2C pull-ups** (R9/R10,
4k7) that the usual adapter PCBs would carry. VDD is on the nano's switchable `VCC`, so
ZMK's `ext_power` gates the trackpad along with the backlight.

Driver is [`cirque-input-module`](https://github.com/nxtkb/cirque-input-module), pinned
to a SHA in `zmk/config/west.yml` — the only sensor driver ZMK's own pointing docs name.

`ROW1`/`ROW2` sit on `P0.09`/`P0.10`, the nRF52840 NFC pins. They worked on v1.0 so
they are kept, but if you would rather not depend on `CONFIG_NFCT_PINS_AS_GPIO`
defaults, move them to the free `P0.17`/`P0.20`. Change both `NANO_NETS` in
`tools/gen_schematic.py` and `row-gpios` in the overlay — `tools/check_schematic.py`
cross-checks the two and will fail if you only change one.

## Backlight power

60 SK6812MINI-E need more than the nice!nano's `VCC` rail can give, and they draw
~1 mA each even showing black. So:

```
BATT+ --[power sw]-- VBATT+ --+-- nice!nano BATIN (pin 24)
                             |
                             +-- Q1 (AO3401A, high side) --> VBATT_LED
                                                               |
                          L1 4.7uH + U2 TPS61085 + D61 MBRA340 |
                                                               v
                                                             VLED (5V)
                                                               |
                                      +------------------------+
                                      |                        |
                               60x SK6812MINI-E          U3 74AHCT1G125
                                                                |
nice!nano P0.06 --[R7 1k]-- U3 in --> out --[R8 330R]--> LED_DIN_5V

VCC --[R2 10k]-- Q2 gate (BSS138) --> pulls Q1 gate low --> Q1 on
VCC --------------------------------> U2 EN
```

Three things here are not optional:

**Q1 cuts at the battery, not after the boost.** A non-synchronous boost still leaks
VIN to VOUT through the inductor and the Schottky when its `EN` is low, so gating only
`EN` would leave 60 LEDs drawing ~60 mA with the backlight "off" — flat pouch cell
overnight. Q1 upstream of the boost means the boost, the LEDs **and** the level
shifter all go completely dead.

**Q2 exists because Q1's gate can't be driven from 3.3 V.** Q1's source sits at up to
4.2 V, so tying its gate to `VCC` gives only −0.9 V of V<sub>GS</sub> — nowhere near
enough to turn on. Q2 pulls the gate to ground instead, with R1 (100k) holding it off
and R3 (100k) defining Q2's gate when `VCC` is unpowered.

**U3 is the part people skip.** At 5 V an SK6812 wants a logic high above ~3.5 V; the
nRF52840 drives 3.3 V. This is the usual cause of flaky WS2812 chains. R7 limits
injection into U3's ESD diodes while U3 is unpowered.

Everything is gated by `VCC`, which on nice!nano v2 is ZMK's external power rail
(`control-gpios = <&gpio0 13 GPIO_ACTIVE_HIGH>`). So `&ext_power EP_OFF` — already
bound in the `bluetooth_control` layer — physically removes LED power.

### Current budget, honestly

60 SK6812MINI-E at full white is roughly **3.4 A at 5 V, ~17 W**. That is not
happening on a pouch cell, and U2's 2 A switch is not sized for it. A solid colour at
low brightness is roughly 150–250 mA from the battery — a few hours. Full-colour
effects are a plugged-in feature.

`order66_lp.conf` therefore sets `CONFIG_ZMK_RGB_UNDERGLOW_BRT_MAX=40` and enables
`AUTO_OFF_IDLE` / `AUTO_OFF_USB`. Raise the cap only on USB, after measuring.

### What ZMK can and cannot do with it

ZMK drives addressable LEDs as a single `zmk,underglow` strip. 60 per-key LEDs work,
but effects are strip-wide (solid, breathe, spectrum, swirl) — there is no per-key
positional mapping like QMK's. For a backlight that is exactly right. Per-key
positional effects would be custom work.

Controls are on the `bluetooth_control` layer, third row:
`RGB_TOG`, `RGB_BRI`, `RGB_BRD`, `RGB_HUI`, `RGB_HUD`, `RGB_EFF`.

## ZMK Studio

The shield declares `studio` support: it has the shared physical layout and a matrix
transform, which is all Studio requires. With it enabled, **keymap changes no longer
need a firmware build** -- you edit live over USB. Hardware changes still do.

It is off by default because it needs a build snippet as well as a Kconfig symbol:

```
west build -p -b nice_nano_v2 -S studio-rpc-usb-uart -- -DSHIELD=order66_lp \
  -DZMK_EXTRA_MODULES=/workspaces/order66keyboard/order66-lp/zmk
```

plus uncommenting `CONFIG_ZMK_STUDIO=y` in `order66_lp.conf`. Studio locking is
implied on, so the keymap binds `&studio_unlock` on the ADJUST layer (row 4, far
left) -- without it Studio can connect but never commit a change.

## Firmware

**See [BUILDING.md](BUILDING.md) for the full command reference.** The short version,
run locally:

```sh
nix build .#firmware     # -> result/zmk.uf2
nix run .#flash          # double-tap reset first
```

This builds against **upstream ZMK**, pinned in `zmk/config/west.yml` — not the fork
in `../zmk`, which has `ortho_5x12` patched to 71 keys.

**Status: builds green.** FLASH 30.44% (246880 B / 792 KB), RAM 28.31%
(74218 B / 256 KB), with ZMK Studio and RGB underglow both enabled. Board resolves to
`nice_nano` revision 2.0.0; the UF2 carries family id `0xADA52840`.

Two things a real build caught that static checking could not:

- The board is **`nice_nano//zmk`**, not `nice_nano_v2`. Upstream migrated to Zephyr's
  hardware model v2, making v2 a board *revision*, with no back-compat alias. The
  board-specific overlay had to be renamed to `boards/nice_nano_nrf52840_zmk.overlay`
  to match (26 upstream shields use that filename).
- `gcc-arm-embedded` in current `nixpkgs-unstable` **segfaults**, so the flake pulls
  the ARM toolchain from `nixos-25.11` and leaves everything else on unstable.

The keymap is all 9 v1.0 layers, ported to 60 bindings each by
`tools/port_keymap.py`. `macros.dtsi` is **committed** this time with placeholder
`&work` / `&name` / `&ssh` bodies — on v1.0 it was gitignored and absent, so a fresh
clone could not build. Replace the bodies, keep the node names.

## Tools

The schematic is generated, not hand-drawn — 180 of its 280 symbols are repetitive
matrix/LED/decoupling cells, and generating them keeps them exactly uniform and the
net assignment mechanical.

| | |
|---|---|
| `tools/gen_schematic.py` | writes `pcb/order66-lp.kicad_sch`; owns the pin map and matrix mapping |
| `tools/gen_overlay.py` | writes the ZMK overlays **from that same pin map**, so firmware cannot drift from hardware |
| `tools/gen_pcb.py` | writes `pcb/order66-lp.kicad_pcb` — outline and placement, no traces |
| `tools/check_pcb.py` | placement assertions: pitch, band keyless, band packing, design rules |
| `tools/gen_nano_footprint.py` | derives the mixed THT/SMD nice!nano footprint |
| `tools/check_schematic.py` | netlist assertions — the checks ERC cannot do |
| `tools/erc.sh` | ERC against a throwaway KiCad config |
| `tools/check_firmware.py` | static verification of the shield against a ZMK tree |
| `tools/port_keymap.py` | ports the v1.0 keymap 72 → 60 bindings per layer |
| `flake.nix` | local firmware build via [zmk-nix](https://github.com/lilyinstarlight/zmk-nix) |
| `tools/smoke_symbols.py` | emits one schematic per part, to find a symbol KiCad won't load |
| `tools/validate_transform.py` | record of how the symbol→schematic pin transform was derived |

Regenerate and verify:

```sh
python3 tools/gen_schematic.py
./tools/erc.sh
python3 tools/check_schematic.py
python3 tools/check_firmware.py
```

UUIDs are derived deterministically from reference designators, so regenerating an
unchanged design produces no git diff.

### Verification status

- **ERC: 0 errors.** 6 warnings, all `pin_to_pin` type mismatches caused by
  third-party symbols declaring pins `Unspecified` (the nice!nano's GND/BATIN, the
  EG1206A). Cosmetic.
- **Netlist: all assertions pass.** 60 unique (row, col) pairs covering the full grid;
  every diode `col2row`; the LED chain one unbroken path of 60 starting at
  `LED_DIN_5V`; the whole LED power chain node by node; `VBATT_LED` reachable only
  through Q1; the MCU pin map agreeing with the ZMK overlay.
- **Firmware: static checks pass.** Kconfig symbols, devicetree compatibles and
  properties, behaviour labels, `RGB_*` constants, 60 bindings × 9 layers, and
  upstream `ortho_5x12`'s 60-key count.
- **Firmware: compiles.** Built locally via `nix build` against upstream ZMK —
  see the Firmware section above for the size report. This is the check that caught
  the HWMv2 board rename.

## Known open items

**The schematic's power and MCU blocks are correct but not prettified.** They are
netlist-style stubs — every pin gets a short labelled stub rather than a drawn
topology — and expect a human layout pass in KiCad. The key matrix, LED array and
decoupling array are laid out properly and meant to be used as-is.

**Cell density is the main PCB risk.** An 18 × 17 cell must hold a hotswap socket
whose pads reach x ≈ 9.57 (past the 9.0 half-cell, so adjacent cells interleave —
normal for choc, but it needs a routing check), a 3.4 × 3.0 LED cutout at the centre,
a SOD-323 diode, a 0402 cap, and row/column routing. The choc Corne with RGB does
exactly this, so it is proven, but it is tight.

**Confirm before committing 60 placements:** `LED_choc_6028R` pad 1 against the
SK6812MINI-E datasheet. SK6812MINI and SK6812MINI-**E** have different pinouts — see
[TweetyDaBird/Lotus-58-Classic#10](https://github.com/TweetyDaBird/Lotus-58-Classic/issues/10).

**Boost part choice.** U2 is a TPS61085 because it is a well-documented 2 A boost
present in stock KiCad libraries. Verify the compensation network (R6/C7), the
feedback divider (R4/R5 for 5.0 V from a 1.238 V reference) and the soft-start cap
(C8) against the datasheet. A boost with true load disconnect would let you drop Q1 —
but Q1 also kills the boost's own quiescent draw, so it is worth keeping either way.

**Netclasses are pre-set for the eventual layout**: `led_power` (0.8 mm) for `VLED`
and `VBATT_LED`, `power` (0.4 mm) for `GND`/`VCC`/`BATT+`/`VBATT+`. The LED rail gets
its own wider class because 0.4 mm is too thin for the current 60 LEDs can pull.

**Mounting holes** (6 × M2.5) have no positions yet; they must dodge 60 centre
cutouts and interleaved socket pads.

**No KiCad global library tables exist on this machine yet** (`~/.config/kicad/10.0/`
has none — they are created on first GUI launch). Until then KiCad cannot resolve
stock libraries like `Device` or `Diode`, and the schematic will show 150+ missing
symbol/footprint warnings. Launching the KiCad GUI once fixes it; `tools/erc.sh`
works around it for scripted checks.

**Case and `../order66-case/case.scad` are untouched.** They need a full redo: 5 rows,
18/17 mm split spacing (it currently has a single `key_spacing` scalar), new outline,
new mount grid, choc-depth keygrid, a reset access hole in the bottom, and clearance
for the underside nano and battery.

## Mechanical intent

nice!nano **reverse mounted on the bottom**, USB-C at the back (top) edge, shifted as
far left as it fits. Reset `SW61` also bottom-mounted, with an access hole in the case
bottom. Battery, power switch and SWD headers on the underside too. That puts the
outline at roughly 220 × 89 mm around the 216 × 85 key field.
