# Building order66-lp firmware

Everything here runs **locally on your machine**. `nix build` compiles in the Nix
sandbox and caches into `/nix/store`. No GitHub Actions, no cloud builder, no
devcontainer needed.

## Why you have to build at all

ZMK has no runtime config file. The keymap *and* the hardware description are compiled
into the `.uf2`. In particular, everything about the backlight is compile-time:

- the `led_strip` devicetree node and `chain-length = <60>`
- the SPIM pin selection (`NRF_PSEL(SPIM_MOSI, 0, 6)`)
- `CONFIG_ZMK_RGB_UNDERGLOW` and the brightness cap

Change any of that and you rebuild. The one thing you *don't* need to rebuild for is
plain keymap edits — see [ZMK Studio](#zmk-studio) below.

## Prerequisites

Nix with flakes enabled. Check:

```sh
nix config show | grep experimental-features
# want: experimental-features = ... flakes nix-command ...
```

On NixOS, in your system config:

```nix
nix.settings.experimental-features = [ "nix-command" "flakes" ];
```

Otherwise add to `~/.config/nix/nix.conf`:

```
experimental-features = nix-command flakes
```

The first build downloads a few GB — the Zephyr tree is ~720 MB on its own, plus the
ARM toolchain and Zephyr's module set. It is all cached afterwards, so later builds
only recompile your changes.

## Verified

This has been built on this machine against upstream ZMK. Last green build:

```
-- Found toolchain: gnuarmemb (gcc-arm-embedded-14.3.rel1)
nice_nano_nrf52840_zmk for _nrf52840_zmk for nice_nano with version 2.0.0
-- Using keymap file: .../boards/shields/order66_lp/order66_lp.keymap
-- Snippet(s): studio-rpc-usb-uart
Memory region         Used Size  Region Size  %age Used
           FLASH:      246880 B       792 KB     30.44%
             RAM:       74218 B       256 KB     28.31%
Wrote 494080 bytes to zmk.uf2
```

Plenty of headroom with both ZMK Studio and RGB underglow enabled. The UF2 carries
family id `0xADA52840` (nRF52840), so the bootloader will accept it.

## Build

From the `order66-lp/` directory:

```sh
nix build .#firmware
```

Output lands at `./result/zmk.uf2` (a symlink into `/nix/store`).

### The one gotcha: flakes only see git-tracked files

If `order66-lp/` is not committed yet, `nix build .#firmware` fails with errors about
missing paths, because flakes copy only what git tracks. Either commit first, or use
the `path:` URL, which ignores git and copies the directory as-is:

```sh
nix build "path:$PWD#firmware"
```

Once the files are committed, prefer `nix build .#firmware` — it records the inputs in
`flake.lock`, which is what makes the build reproducible.

### Useful flags

```sh
nix build .#firmware --print-build-logs    # stream the compiler output
nix build .#firmware --rebuild             # ignore the cache and rebuild
nix log /nix/store/<hash>-order66-lp-firmware.drv   # re-read a finished build's log
```

## Flash

Double-tap the nice!nano's reset button to enter the UF2 bootloader, then:

```sh
nix run .#flash
```

That waits for the `nRF UF2` mass-storage device to appear, mounts it with `udisks`,
copies the firmware, and waits for you to unplug. Linux only.

Manual alternative, any OS: double-tap reset, the board appears as a `NICENANO` USB
drive, copy `result/zmk.uf2` onto it. It reboots itself when the copy finishes.

## Updating ZMK

```sh
nix run .#update
```

Bumps the project revisions in `zmk/config/west.yml` to current upstream and rewrites
`zephyrDepsHash` in `flake.nix` to match. Must be run inside the git repo (it uses
`git rev-parse --show-toplevel`).

To update the flake inputs themselves (nixpkgs, zmk-nix):

```sh
nix flake update
```

### If you edit `zmk/config/west.yml` by hand

**You must also invalidate `zephyrDepsHash`, and Nix will not tell you that.** A
fixed-output derivation's store path is determined by its *declared hash*, not by its
inputs — so changing `west.yml` while leaving the hash alone makes Nix reuse the
previously fetched workspace. It does not refetch and it does not warn. The build then
succeeds against stale dependencies, or fails somewhere confusing: adding the Cirque
module this way produced

```
undefined reference to `__device_dts_ord_15'
```

from `input_listener.c` — the devicetree referenced a driver that was never fetched,
let alone compiled.

The fix is to deliberately break the hash, then paste back the real one:

1. Set `zephyrDepsHash` to `"sha256-AAAA...="` (any wrong value of the right shape).
2. Build. Nix now refetches and reports the mismatch:
   ```
   error: hash mismatch in fixed-output derivation '...-west-deps.drv':
            specified: sha256-AAAA...
               got:    sha256-<the real one>
   ```
3. Paste the `got:` value in and build again.

`nix run .#update` does all of this for you, which is why it is the preferred route.

## ZMK Studio

The flake sets `enableZmkStudio = true`, which adds the `studio-rpc-usb-uart` snippet
and `CONFIG_ZMK_STUDIO=y`. With it, **keymap changes do not need a build** — connect
over USB and edit live. Studio locking is implied on, so press `&studio_unlock` first:
ADJUST layer, bottom-left area (row 4, column 0).

To build without Studio, set `enableZmkStudio = false` in `flake.nix`.

## Manual west build, without Nix doing the driving

`nix develop` gives you a shell with cmake, ninja, west, `gcc-arm-embedded`, and the
protobuf tools Studio needs, with `ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb` already set:

```sh
nix develop
```

You still need a west workspace, which `nix build` otherwise creates for you in a
temp dir.

**Build the workspace outside the repo.** `west init -l` makes the manifest's *parent*
the workspace root, so `west init -l zmk/config` would make `order66-lp/zmk` the root
and clone Zephyr straight into `order66-lp/zmk/zephyr` — on top of this module's own
`zephyr/module.yml`. Copy the manifest somewhere else instead:

```sh
REPO=$PWD                         # order66-lp
mkdir -p ~/order66-lp-west/config && cd ~/order66-lp-west
cp "$REPO/zmk/config/west.yml" config/

west init -l config
west update                       # clones ZMK + Zephyr + modules, several GB

west build -s zmk/app -b 'nice_nano//zmk' -S studio-rpc-usb-uart -- \
  -DSHIELD=order66_lp \
  -DZMK_EXTRA_MODULES="$REPO/zmk" \
  -DCONFIG_ZMK_STUDIO=y
```

The result is `build/zephyr/zmk.uf2`.

Prefer `nix build` — it pins everything via `flake.lock` and leaves no multi-GB
workspace lying around.

## Board and shield names

```
board  = nice_nano//zmk
shield = order66_lp
```

`nice_nano//zmk` is Zephyr hardware-model-v2 syntax: `<board>//<variant>` with the SoC
left empty. **It is not `nice_nano_v2`.** Upstream ZMK migrated to HWMv2, so v2 is now
a board *revision* (`default_revision: "2.0.0"`), not part of the name, and there is no
back-compat alias — `app/boards/aliases.cmake` only aliases `mikoto_520`. Upstream's
own `app/core-coverage.yml` uses `nice_nano//zmk`.

The same migration renames board-specific shield overlays. The file is
`zmk/boards/shields/order66_lp/boards/nice_nano_nrf52840_zmk.overlay` — named after
the board target, not `nice_nano_v2.overlay`. 26 upstream shields use that exact
filename.

## Two flake details that are deliberate

**The ARM toolchain comes from `nixos-25.11`, not unstable.** `gcc-arm-embedded` in
current `nixpkgs-unstable` is broken: `arm-none-eabi-gcc --version` dies with SIGSEGV
(exit 139). It fails the same way outside the Nix sandbox, so it is the toolchain
build itself, not Nix. Zephyr hits it in `find_package(Zephyr)` and reports it
unhelpfully as:

```
CMake Error at .../cmake/compiler/gcc/generic.cmake:24 (message):
  Executing the below command failed.  Are permissions set correctly?
    .../bin/arm-none-eabi-gcc --version
```

Measured on unstable @ `5adc5083` (2026-10-20):

| nixpkgs ref | `gcc-arm-embedded-14` | |
|---|---|---|
| `nixpkgs-unstable` | 14.3.rel1 | segfaults |
| `nixos-unstable` | 14.3.rel1 | segfaults |
| `nixos-25.11` | 14.3.rel1 | **works** |
| `nixos-25.05` | 14.2.rel1 | works |

`-15.3.rel2` on unstable segfaults too, so it is not a version thing. Hence the
separate `nixpkgs-arm` input, overlaid in only for `gcc-arm-embedded` while
everything else stays on unstable.

Note that `inputs.nixpkgs.follows = "nixpkgs"` — which the upstream zmk-nix template
has, and this flake omits — is *not* the fix either way: zmk-nix pins a nixpkgs from
the same week carrying the same broken toolchain. Only the overlay helps. If the
toolchain is fixed upstream later, drop the `nixpkgs-arm` input.

**`src` points at `./zmk`, and that is the whole module integration.** zmk-nix checks
for `zephyr/module.yml` at the root of `src`; if it finds one it passes
`-DZMK_EXTRA_MODULES=<src>` itself. Nothing else is needed to build an out-of-tree
shield.

## Upstream, not the fork

`zmk/config/west.yml` pins `zmkfirmware/zmk` — upstream. The v1.0 board needed a
patched fork because its 6-key top row forced an edit to ZMK's *shared*
`ortho_5x12` layout. At a true 5×12 that patch is unnecessary, and building green
against upstream is the proof.

Do **not** point this at `../zmk` (the fork in the parent repo). It is pinned to an
older ZMK and has `ortho_5x12/all1u.dtsi` patched to 71 keys.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `error: path '/nix/store/...' does not exist` or missing files | Files aren't git-tracked. Commit, or use `nix build "path:$PWD#firmware"` |
| `hash mismatch in fixed-output derivation` | `west.yml` changed. Paste the `got:` hash into `zephyrDepsHash` |
| `No board named 'nice_nano_v2' found` | Use `nice_nano//zmk` |
| `arm-none-eabi-gcc --version` fails / `Are permissions set correctly?` | Broken `gcc-arm-embedded` in unstable. Keep the `nixpkgs-arm` overlay (see above) |
| `experimental Nix feature 'nix-command' is disabled` | Enable flakes — see Prerequisites |
| Shield not found / falls back to a default keymap | Shield dir name, `Kconfig.shield` symbol, and `<shield>.overlay` basename must all agree on `order66_lp` |
