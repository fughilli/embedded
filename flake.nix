{
  description = "Bazel firmware toolchains for ESP32-C6 + RP2350 (Nix-provided)";

  # Keep this in sync with the nix_repo.github tag in MODULE.bazel.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      # aarch64 dev container today; extend as needed.
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # `nix develop` gives an interactive shell with every host tool the build
      # driver needs. Bazel itself pulls the compiler/picotool through
      # rules_nixpkgs (MODULE.bazel), so this shell is mainly for humans /
      # running picotool + esptool by hand.
      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.gcc-arm-embedded   # arm-none-eabi-gcc 13.3 (RP2350)
            pkgs.picotool           # elf -> uf2
            pkgs.bazelisk           # in case the overlay binary is unavailable
            # Milestone 2 (ESP32-C6) tools get added here / via nixpkgs-esp-dev:
            # pkgs.esptool
          ];
        };
      });

      # Expose the arduino-pico source derivation so `nix build .#arduino-pico`
      # can print/refresh its fixed-output hash without going through Bazel.
      packages = forAll (pkgs: {
        arduino-pico = import ./nix/arduino_pico_drv.nix pkgs;
      });
    };
}
