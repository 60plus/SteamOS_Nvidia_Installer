# Third-party components

This project is based on [28allday/steamos-nvidia-installer](https://github.com/28allday/steamos-nvidia-installer).
Its original copyright and MIT license are preserved in LICENSE.

The optional corrected performance overlay is built from
[MangoHud](https://github.com/flightlessmango/MangoHud), revision
`33c2c7ddbb72c15e19a42163d75424d5804f8ec8`. The patches in
`patches/mangohud` include upstream commit
`4e69793b9b77a394b8f7842a78de235eaf3859df`, with its authorship retained,
and local changes hiding unsupported NVIDIA sensor fields and displaying
detected hardware names in the detailed Steam overlay.

The artifact includes the upstream license as `MangoHud-LICENSE` and provenance
in `mangoapp-build.json`. Distribute those files with the binary. MangoHud and
its dependencies retain their respective licenses; the installer license does
not replace them. The build script fetches the pinned source and its submodules.

The Gamescope artifact uses [Gamescope](https://github.com/ValveSoftware/gamescope)
3.17.0, revision `e6674a98118ca7b098b98a3874b8f195ae1bf750`. Gamescope retains its
MIT license; its dependencies retain their own licenses. Distribute the artifact's
license files and source metadata with it.

The capture-color and sampled-texture fixes by Matthew Schwartz are now included
in the pinned upstream source, as commits
`ff6b924fd0634a51d0fb3755c56c01dca1daadc1` and
`9851c6064cfc783678b27942c0b125f052c6c7fd`. The corresponding downstream patches
have been removed.

`patches/gamescope` contains five patches: Wayland scanner build compatibility;
a revert of upstream commit `e383171ff1c0f7b5b37f05f2bb67f7c5282b087f`, associated
with NVIDIA Big Picture corruption; NVIDIA alpha composition; advertised-mode
filtering; and GBM scanout. Source references are retained in the patches.
The build script records upstream revisions, dependency versions and patch hashes
in `gamescope-build.json`.

The optional Remote Play receiver artifact uses
[nvidia-vaapi-driver](https://github.com/elFarto/nvidia-vaapi-driver), revision
`a03711106b5e297a64a704c876aeb776cbce957b`, under the MIT license. Its COPYING file
is distributed as `licenses/nvidia-vaapi-driver-LICENSE`. Two local patches adapt the
artifact for Steam's receiver: `0001-nv12-chroma-descriptor.patch` changes the
exported NV12 chroma layer descriptor, and `0002-release-unresolved-surfaces.patch`
releases abandoned surfaces when the resolve thread shuts down and bounds the waits
for unresolved surfaces and backing images. Both are maintained by this project and
neither has been merged upstream. `tools/build-remote-play.sh` records source and
patch hashes with the artifact. No Steam executable or SDL binary is redistributed.

The optional NVENC encoding bridge uses the MIT-licensed
[efortin/nvidia-vaapi-driver encoding branch](https://github.com/efortin/nvidia-vaapi-driver/tree/feat/nvenc-support),
revision `3a58095f1833c997fd4f0a73ce3fa0300cdc20fc`. Its COPYING license is
included in the artifact. The build adjusts only the i386 pkg-config search paths
for Arch/SteamOS and includes that cross-compilation file with the provenance.
The 32-bit encoding driver and 64-bit helper remain separate from the receiver
artifact. This upstream feature is experimental (draft pull request 427).
