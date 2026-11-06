{
  description = "order66 dev tools (serial console, etc. -- not the firmware toolchain, see docker-compose.yml for that)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
    in {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          isLinux = pkgs.lib.hasSuffix "linux" system;
        in {
          default = pkgs.mkShell {
            packages = [ pkgs.tio ] ++ pkgs.lib.optional isLinux pkgs.usbutils;
          };
        });
    };
}
