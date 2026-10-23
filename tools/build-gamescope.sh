#!/bin/bash
# Build an experimental stable Gamescope artifact in a disposable SteamOS root.
set -euo pipefail
root=$(realpath "${1:?Usage: build-gamescope.sh STEAMOS_BUILD_ROOT OUTPUT_DIRECTORY}")
out=$(realpath -m "${2:?Output directory is required}")
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=build-root-guard.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/build-root-guard.sh"
[[ ! -e $out ]] || { printf 'Output directory already exists: %s\n' "$out" >&2; exit 1; }
require_stable_build_root "$root"
# Recovery images strip headers while retaining the package database entries.
# Reinstall build libraries; --needed would leave those headers missing.
chroot "$root" pacman -S --noconfirm gcc glibc linux-api-headers git meson ninja cmake \
  pkgconf python-mako glslang vulkan-headers vulkan-icd-loader wayland-protocols \
  wayland libdrm libx11 libxcb libxau libxdmcp xorgproto libxcomposite libxdamage \
  libxres xcb-util-errors xcb-util-wm xcb-util-renderutil libxfixes libxext libxi \
  libxrender libxrandr libxinerama libxmu libxt libxtst libxft libxpresent libxshmfence \
  libxxf86vm libxcursor libxfont2 libxkbfile libxkbcommon libxkbcommon-x11 libsm libice \
  freerdp pixman libinput seatd pipewire libpipewire libdecor libei luajit libavif \
  aom rav1e libdisplay-info libliftoff glm benchmark catch2 libcap hwdata libpng \
  lcms2 util-linux-libs xorg-xwayland sdl2-compat systemd-libs dbus libffi expat zlib \
  mesa
# Gamescope 3.17.0, validated with the NVIDIA integration in installer 0.2.7.
# Keep the SteamOS 3.8 build-root ABI for compatibility with existing installations.
commit=e6674a98118ca7b098b98a3874b8f195ae1bf750
work=$(chroot "$root" mktemp -d /tmp/gamescope-build.XXXXXX)
printf 'Build source directory: %s%s\n' "$root" "$work"
chroot "$root" git -C "$work" init -q
chroot "$root" git -C "$work" remote add origin https://github.com/ValveSoftware/gamescope.git
chroot "$root" git -C "$work" fetch --depth 1 origin "$commit"
chroot "$root" git -C "$work" checkout --detach "$commit"
chroot "$root" git -C "$work" submodule update --init --recursive
# wlroots 0.20 needs wayland-server >= 1.24 and wayland-protocols >= 1.47, and the SteamOS
# 3.8 root carries 1.23.1 and 1.45. Build both from pinned upstream tags as subprojects, with
# libwayland linked statically into Gamescope, so the binary does not depend on a wayland
# newer than the system it runs on. Every user of these dependencies is forced onto the
# subproject, or the main project and wlroots would disagree about which wayland-server it is.
cat > "$root$work/subprojects/wayland.wrap" <<'WRAP'
[wrap-git]
url = https://gitlab.freedesktop.org/wayland/wayland.git
revision = 736d12ac67c20c60dc406dc49bb06be878501f86
depth = 1

[provide]
dependency_names = wayland-server, wayland-client, wayland-cursor, wayland-egl, wayland-scanner
program_names = wayland-scanner
WRAP
cat > "$root$work/subprojects/wayland-protocols.wrap" <<'WRAP'
[wrap-git]
url = https://gitlab.freedesktop.org/wayland/wayland-protocols.git
revision = 88223018d1b578d0d8869866da66d9608e05f928
depth = 1

[provide]
dependency_names = wayland-protocols
WRAP
for patch in "$repo"/patches/gamescope/*.patch; do
  cp "$patch" "$root$work/$(basename "$patch")"
  chroot "$root" git -C "$work" apply --check "$work/$(basename "$patch")"
  chroot "$root" git -C "$work" apply "$work/$(basename "$patch")"
done
# The installed integration replaces the compositor binary only. Retain the system
# WSI layer; the 3.17 layer needs newer Vulkan headers and is outside this candidate.
chroot "$root" meson setup "$work/build" "$work" --buildtype=release --prefix=/usr \
  --force-fallback-for=libliftoff,vkroots,wayland-server,wayland-client,wayland-cursor,wayland-egl,wayland-scanner,wayland-protocols \
  -Denable_gamescope_wsi_layer=false \
  -Dwayland:default_library=static -Dwayland:tests=false -Dwayland:documentation=false \
  -Dwayland:dtd_validation=false -Dwayland-protocols:tests=false
[[ $(chroot "$root" git -C "$work/subprojects/wayland" rev-parse HEAD) == 736d12ac67c20c60dc406dc49bb06be878501f86 ]] || {
  printf 'wayland subproject is not the pinned 1.24.0 commit\n' >&2; exit 1; }
[[ $(chroot "$root" git -C "$work/subprojects/wayland-protocols" rev-parse HEAD) == 88223018d1b578d0d8869866da66d9608e05f928 ]] || {
  printf 'wayland-protocols subproject is not the pinned 1.47 commit\n' >&2; exit 1; }
# The GBM scanout path in 0005 is the 4K fix, and its dependency is declared optional
# upstream style, so a root without the GBM headers still builds, passes every test
# below and produces a binary with the path compiled out. Nothing would say so. Refuse
# that here: a build without GBM is not this project's Gamescope.
grep -q -- '-DHAVE_GBM=1' "$root$work/build/compile_commands.json" || {
  printf 'GBM support was not compiled in; the 4K scanout fix would be missing.\n' >&2
  exit 1
}
chroot "$root" ninja -C "$work/build" -j "${JOBS:-4}"
chroot "$root" meson test -C "$work/build" --print-errorlogs
cp "$repo/tools/test-gamescope-capture.py" "$root$work/test-capture.py"
chroot "$root" python3 "$work/test-capture.py" "$work"
chroot "$root" /usr/lib/ld-linux-x86-64.so.2 --list "$work/build/src/gamescope" >/dev/null
chroot "$root" "$work/build/src/gamescope" --version
chroot "$root" env DESTDIR="$work/stage" meson install -C "$work/build" --no-rebuild --skip-subprojects
mkdir -p "$out"
cp -a "$root$work/stage" "$out/root"
cp "$root$work/LICENSE" "$out/Gamescope-LICENSE"
python3 - "$out" "$commit" "$repo/patches/gamescope" "$root" "$work" <<'PY'
import hashlib,json,sys,shutil,subprocess
from pathlib import Path
out,commit,patches,root=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]),Path(sys.argv[4])
source=root/sys.argv[5].lstrip('/')
for p in source.rglob('*'):
    if p.is_file() and not p.is_symlink() and p.name.lower().startswith(('license','copying','copyright')) and '.git' not in p.parts and 'build' not in p.relative_to(source).parts:
        dest=out/'licenses'/p.relative_to(source)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,dest)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
metadata={'source':'https://github.com/ValveSoftware/gamescope','commit':commit,
'upstream_fix':'ff6b924fd0634a51d0fb3755c56c01dca1daadc1','base_version':'3.17.0',
'status':'experimental; hardware acceptance required',
'upstream_tag':'3.17.0',
'disabled_components':['gamescope_wsi_layer'],
'upstream_tag_object':'f6acb89e8d54ea3a94f590c8c249cef4a697fdc3',
'reverted_upstream':['e383171ff1c0f7b5b37f05f2bb67f7c5282b087f'],
'subprojects_pinned':{'wayland':'1.24.0 736d12ac67c20c60dc406dc49bb06be878501f86',
'wayland-protocols':'1.47 88223018d1b578d0d8869866da66d9608e05f928'},
'upstream_capture_fixes':['ff6b924fd0634a51d0fb3755c56c01dca1daadc1', '9851c6064cfc783678b27942c0b125f052c6c7fd'],
'build_packages':subprocess.check_output(['chroot',str(root),'pacman','-Q'],text=True).splitlines(),
'submodules':subprocess.check_output(['chroot',str(root),'git','-C',sys.argv[5],'submodule','status','--recursive'],text=True).splitlines(),
'build_os_release':(root/'etc/os-release').read_text(),
'patches':{p.name:sha(p) for p in sorted(patches.glob('*.patch'))},
'files':{str(p.relative_to(out/'root')):sha(p) for p in sorted((out/'root').rglob('*')) if p.is_file() and not p.is_symlink()}}
(out/'gamescope-build.json').write_text(json.dumps(metadata,indent=2)+'\n')
PY
printf 'Experimental artifact (not installed): %s\n' "$out"