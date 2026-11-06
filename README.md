# order66keyboard

BUILDING THIS KEYBOARD

checkout this repo
```
git clone git@github.com:rileytuttle/order66keyboard.git
```

HARDWARE - the assumption here is that you have one of my extra pcbs from the small batch fabrication that I used.
otherwise I guess you could have your own made but I doubt that will happen.
note the version of board you have. I forgot to do this with version 1 so if there is no version then you have a v1.0

next step would be to solder the components on
* solder key hotswap sockets
* solder diodes, currently there are two options (either the smd or DO-35 through hole type). make sure to match cathode with silkscreen marking
* choose what kind of battery you want there is an option for a flat type battery using a jst connector or a 18650 battery with a socket.
* choose the battery toggle switch type
* optionally solder sockets for nice!nano
* solder riser socket for nice!view

CASE
* check out the tag corresponding to the version of pcb you have ie `git checkout v1.0` ... use `git tag` to see tags and `git show tagname` to see the annotations. then `git checkout <VERSION_TAG>`
* then open the case.scad file in openscad. there you will be able to choose features corresponding to the optional hardware you have. export the case stl
* export the keygrid stl
* print the files

[Build Photos](./build-photos/)
[![complete build](./build-photos/IMG_3964.jpg)](./build-photos/IMG_3964.jpg)

SOFTWARE
* check out the tag corresponding to the pcb version we have
* build via Docker (needs only Docker/Docker Compose installed, nothing else):
```
docker compose run --rm zmk scripts/build.sh
```
  This uses ZMK's own prebuilt dev image, so the toolchain always matches what's pinned in `config/west.yml`. First run takes a while (clones zmk + Zephyr); later runs are fast.
* or build natively, if you'd rather not use Docker: follow [ZMK's local toolchain setup](https://zmk.dev/docs/development/local-toolchain/setup) to install `west` + the Zephyr SDK, then from the repo root run `./scripts/build.sh`.
* either way, the firmware ends up at `build/zephyr/zmk.uf2` — double-tap reset on the nice!nano to mount it as a USB drive, then copy that file over.

NOTE:
`zmk/` is now a plain, unforked checkout of upstream ZMK managed by `west` (see `config/west.yml`) instead of a custom fork — it's gitignored and recreated by `west update`. The `order66-shield` directory stays a regular git submodule for now.
