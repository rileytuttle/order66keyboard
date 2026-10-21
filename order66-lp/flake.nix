{
  description = "order66-lp: 5x12 Kailh Choc v1 ortholinear ZMK firmware";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    zmk-nix.url = "github:lilyinstarlight/zmk-nix";

    # Toolchain only -- see the comment on pkgsFor below.
    nixpkgs-arm.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs, nixpkgs-arm, zmk-nix }: let
    forAllSystems = nixpkgs.lib.genAttrs (nixpkgs.lib.attrNames zmk-nix.packages);

    # The ARM toolchain in current nixpkgs-unstable is broken: arm-none-eabi-gcc
    # dies with SIGSEGV (exit 139) on `--version`, outside the Nix sandbox as well as
    # in it, so it is the toolchain build and not something about Nix. Zephyr trips
    # over it in find_package(Zephyr) and reports it unhelpfully as
    #   "Executing the below command failed.  Are permissions set correctly?"
    #
    # Measured on unstable @ 5adc5083 (2026-10-20): both gcc-arm-embedded-14.3.rel1
    # and -15.3.rel2 segfault. The same 14.3.rel1 from nixos-25.11 is fine, so the
    # toolchain alone comes from stable while everything else stays on unstable.
    #
    # `inputs.nixpkgs.follows` is not the fix: zmk-nix pins a nixpkgs from the same
    # week with the same broken toolchain, so following or not makes no difference.
    pkgsFor = system: import nixpkgs {
      inherit system;
      overlays = [
        (final: prev: {
          gcc-arm-embedded = nixpkgs-arm.legacyPackages.${system}.gcc-arm-embedded-14;
        })
      ];
    };
  in {
    packages = forAllSystems (system: let
      pkgs = pkgsFor system;
      builders = zmk-nix.lib.buildersFor pkgs;
    in rec {
      default = firmware;

      # zmk-nix looks for zephyr/module.yml at the root of `src`; finding one, it
      # passes -DZMK_EXTRA_MODULES=<src> itself. So pointing src at ./zmk is the
      # entire out-of-tree shield integration.
      #
      # This builds against UPSTREAM zmkfirmware/zmk, pinned in zmk/config/west.yml.
      # The v1.0 board needed a patched fork for its 6-key top row; at a true 5x12
      # it does not, and a green build here is the proof.
      firmware = builders.buildKeyboard {
        name = "order66-lp-firmware";

        src = nixpkgs.lib.sourceFilesBySuffices ./zmk [
          ".board" ".cmake" ".conf" ".defconfig" ".dts" ".dtsi" ".json"
          ".keymap" ".overlay" ".shield" ".yml" "_defconfig"
        ];

        # Zephyr hardware-model-v2 syntax: <board>//<variant>, SoC left empty.
        # NOT nice_nano_v2 -- upstream made v2 a board revision, with no alias.
        board = "nice_nano//zmk";
        shield = "order66_lp";

        # Keymap edits over USB instead of a rebuild. Adds the studio-rpc-usb-uart
        # snippet and CONFIG_ZMK_STUDIO=y. The keymap binds &studio_unlock on ADJUST.
        enableZmkStudio = true;

        # Fixed-output hash of the west workspace. Changes whenever
        # zmk/config/west.yml does; `nix run .#update` rewrites both together.
        zephyrDepsHash = "sha256-UAzb4OqLBddEcrWSknfmlHKPQSsJnYJusxim/6w7pPU=";

        meta = {
          description = "ZMK firmware for order66-lp";
          license = nixpkgs.lib.licenses.mit;
          platforms = nixpkgs.lib.platforms.all;
        };
      };

      flash = zmk-nix.packages.${system}.flash.override { inherit firmware; };
      update = zmk-nix.packages.${system}.update;
    });

    devShells = forAllSystems (system: let
      pkgs = pkgsFor system;
    in {
      # Same toolchain override, so a manual `west build` in here works too.
      default = pkgs.callPackage "${zmk-nix}/nix/shell.nix" {};
    });
  };
}
