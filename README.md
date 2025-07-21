# order66keyboard


follow instructions here to set up zmk devcontainer
https://zmk.dev/docs/development/local-toolchain/setup/container

then once in zmk container app folder do this
```
>> west build -p -b nice_nano_v2 -- -DSHIELD="order66 nice_view_adapter nice_view" -DZMK_EXTRA_MODULES="/workspaces/zmk-modules/order66-shield"
```
