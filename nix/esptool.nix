# esptool newer than the pinned nixpkgs' (nixos-25.11 ships 5.1.0). 5.1.0 can't
# talk to an ESP32-P4 v3.x: its stub stops responding on the first flash-id read,
# so flashing fails. 5.6.0 flashes it. Built by overriding nixpkgs' esptool with the
# 5.6.0 source, plus esp-pylib, a dependency since 5.x that 25.11 doesn't package.
# Drop this file for nixpkgs' esptool once the pin carries >= 5.6.
let
  pkgs = import <nixpkgs> { };
  py = pkgs.python3Packages;
  esp-pylib = py.buildPythonPackage rec {
    pname = "esp_pylib";
    version = "1.2.0";
    format = "wheel";
    src = py.fetchPypi {
      inherit pname version format;
      dist = "py3";
      python = "py3";
      hash = "sha256-WB/THrINtLgFGf6IPq6s9bPGosC3zONTp9Mmrny9T18=";
    };
    dependencies = with py; [ rich websockets pyserial rich-click click ];
  };
in
{
  esptool = pkgs.esptool.overridePythonAttrs (old: rec {
    version = "5.6.0";
    src = pkgs.fetchFromGitHub {
      owner = "espressif";
      repo = "esptool";
      tag = "v${version}";
      hash = "sha256-zVK9JoeObfl+Nii4mRC1mZbqDhEvufCFe0mqj24oRd0=";
    };
    dependencies = old.dependencies ++ [ esp-pylib ];
    # The upstream test suite needs hardware or HSM fixtures nixpkgs patches per
    # version; 5.1.0's postPatch doesn't apply to 5.6.0's tests.
    postPatch = "patchShebangs ci";
    doCheck = false;
  });
}
