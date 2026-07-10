# The arduino-pico source tree (earlephilhower core), fetched with submodules so
# the bundled pico-sdk headers and prebuilt libs (lib/rp2350/libpico.a,
# memmap_default.ld, ...) are present. Factored as a `pkgs -> derivation`
# function so both flake.nix and nix/arduino_pico.nix (rules_nixpkgs) can reuse
# it without duplicating the pin.
#
# TODO(post-relaunch, Nix host): verify `rev` is the intended release tag and
# replace `hash` with the value the first `nix build .#arduino-pico` prints.
pkgs:
pkgs.fetchFromGitHub {
  owner = "earlephilhower";
  repo = "arduino-pico";
  rev = "4.6.0"; # verify latest tag on a Nix host
  fetchSubmodules = true;
  hash = pkgs.lib.fakeHash; # replace with the real hash after first fetch
}
