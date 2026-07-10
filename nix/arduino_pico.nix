# rules_nixpkgs entry point (nix_pkg.file in MODULE.bazel selects `arduino-pico`
# from this attrset). rules_nixpkgs provides <nixpkgs> via the `repo = "@nixpkgs"`
# mapping; we import it and hand it to the shared derivation function.
let
  pkgs = import <nixpkgs> { };
in
{
  arduino-pico = import ./arduino_pico_drv.nix pkgs;
}
