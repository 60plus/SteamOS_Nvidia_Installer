[Manual home](README.md)

# Before you start

## Target PC

- A GeForce GTX 16xx or GeForce RTX desktop card that the selected open kernel driver supports. The project targets RTX desktops; the open modules require Turing or newer, and GTX 16xx falls within that architecture range.
- **GeForce GTX 10xx and older cards are not supported by this installer.** Choosing an older version in the driver manager does not add support for them. See [NVIDIA's GPU support documentation](https://github.com/NVIDIA/open-gpu-kernel-modules#compatible-gpus).
- UEFI boot with Secure Boot disabled.
- A USB drive of at least 16 GB and an installation disk you can erase.
- A wired keyboard and one monitor connected directly to the NVIDIA card for setup.
- Internet access for Steam setup and OS updates.

Intel and AMD desktop CPUs can be used. GPU generation alone does not guarantee compatibility: the
selected driver must support the exact GPU. The installer accepts only the GeForce models listed
above. A professional or workstation NVIDIA card is refused when the installation starts, even
where the open kernel driver supports it. On hybrid laptops, the internal screen may be connected
to the integrated GPU.

## Build machine

Use an x86_64 Linux system with root access. The complete build refuses any other architecture. You need
Git, Python 3, losetup, btrfs-progs, rsync, curl, kmod, zstd and binutils (including readelf),
plus `udevadm`, with udev running, because the build asks udev to keep desktop automounts off the loop device and a decompressor for the recovery archive. Starting with release
0.1.4, the builder uses the pacman included in the recovery image, so the host does not need
pacman; older releases require it. Arch Linux, SteamOS and Bazzite hosts have been used for
builds. Before a long build, `sudo bash tools/check-build-host.sh RECOVERY.img WORK_DIRECTORY`
reports anything that is missing, including free space. Point the check at a directory that
already exists, such as the parent the build will create its own work directory inside. The
build's own work directory must not exist yet.

The complete build needs at least 50 GiB free on the Linux work filesystem after the recovery
image is downloaded, and refuses to start with less. The host check it runs first inspects two
places, the directory holding the recovery image and the directory the work directory will be
created in, and refuses either one with less than 28,000 MiB free. The advanced base-only build
checks a lower figure, 20,000 MiB in the output location. Allow additional space for a build cache
on another filesystem and for any separately compiled artifacts. Repeated builds need more space.
On Windows, use a Linux virtual machine. WSL2 and Docker Desktop cannot run this build as
documented, because the kernel Microsoft supplies is built without `CONFIG_UNICODE`; see [Why a
virtual machine, not WSL or Docker](Build-on-Windows.md#why-a-virtual-machine-not-wsl-or-docker).

## Before erasing a disk

Back up your saves and other files. Confirm the destination by model and capacity,
not just a device name such as `/dev/sda`. Disconnect unrelated disks if practical.
Keep the USB installer after installation.

HDR starts off for new display profiles. Enable it later in Steam's display
settings if the connection supports it. HDMI and DisplayPort can behave differently
on the same screen. On a 4K screen choose 3840x2160 rather than 4096x2160. Where
this project's Gamescope build is in use the wider mode is no longer offered at all;
where the system's own build is in use it is offered and then never applied, with no
message. Raising the resolution to 3840x2160 while Game Mode is already running
used to leave the picture unusable. From 0.2.4 that is
fixed where this project's Gamescope build is in use, measured on a 4K monitor over
DisplayPort and checked on the same monitor over HDMI; where the system's own build is in use, choose the resolution before you
start playing. [Troubleshooting](Troubleshooting.md#the-picture-is-corrupted-after-raising-the-resolution-in-game-mode)
records what was measured. An optional
[Safe Graphics](Safe-Graphics.md)
session is included in every image this project builds, and must be selected
manually. Automatic recovery from a failed boot is not provided.

For a Windows host, see [Build on Windows](Build-on-Windows.md). For a Bazzite
host, see [Build on Bazzite](Build-on-Bazzite.md).
