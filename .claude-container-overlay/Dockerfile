# Overlay for the ESP32-C6 / RP2350 Bazel firmware repo.
# Two host-level bootstrap tools that must exist before anything else:
#   - Bazelisk: pins/launches the exact Bazel version from .bazelversion
#   - Nix: supplies the cross toolchains, picotool/esptool, and Arduino sources
# Everything else (compilers, libs, Arduino cores) comes from the repo's
# flake.nix, NOT from here.

# 2026-07-10: Bazelisk (host bootstrap for Bazel). aarch64 static binary.
RUN curl -fsSL -o /usr/local/bin/bazelisk \
        https://github.com/bazelbuild/bazelisk/releases/download/v1.25.0/bazelisk-linux-arm64 \
    && chmod +x /usr/local/bin/bazelisk \
    && ln -sf /usr/local/bin/bazelisk /usr/local/bin/bazel \
    && bazelisk version || true

# 2026-07-10: Nix (flakes) via the Determinate installer. Needs no sudo and
# --init none skips the systemd daemon that has no place in a container.
# build-users-group is cleared so builds run as the calling user (no nixbld
# group); sandbox is off because the container can't set up build-sandbox user
# namespaces unprivileged.
RUN curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix \
        -o /tmp/nix-installer.sh \
    && sh /tmp/nix-installer.sh install linux \
        --init none \
        --no-confirm \
        --extra-conf "experimental-features = nix-command flakes" \
        --extra-conf "build-users-group =" \
        --extra-conf "sandbox = false" \
    && rm /tmp/nix-installer.sh
ENV PATH=/nix/var/nix/profiles/default/bin:$PATH

# 2026-07-10: make the single-user store writable by the dynamically-created
# runtime uid. Daemon-less Nix re-chmods per-user dirs to 0755 on every call and
# EPERMs if it does not own them, so delete them here; the runtime user
# recreates and owns them on first `nix` invocation.
RUN chmod -R go+rwX /nix \
    && rm -rf /nix/var/nix/profiles/per-user /nix/var/nix/gcroots/per-user
