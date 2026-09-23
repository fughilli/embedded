# Package for a Raspberry Pi 5 NixOS config, e.g.:
#   swd-bridge = pkgs.callPackage ./path/to/embedded/tools/swd_bridge { };
{ stdenv }:
stdenv.mkDerivation {
  pname = "swd-bridge";
  version = "0.1.0";
  src = ./.;
  installPhase = "install -Dm755 swd_bridge $out/bin/swd_bridge";
  meta.platforms = [ "aarch64-linux" ];
}
