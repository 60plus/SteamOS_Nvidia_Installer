[Manual home](README.md)

# Install and first boot

First [build the USB image](Build-the-USB-image.md#complete-build) from a current
source archive and write the resulting `.img` to USB. The source archives and
the signed updater bundle on the Releases page are not bootable images.

## Boot and install

1. Connect one monitor to the NVIDIA card and attach a wired keyboard.
2. Select the USB's UEFI entry in the motherboard boot menu. Disable Secure Boot if required.
3. Wait for the recovery desktop and open the appropriate installer shortcut.
4. The installer checks the NVIDIA GPU and running driver before showing destination disks. Each disk is listed with its size, model, connection and what it already holds: no partitions, an existing SteamOS installation, or a count of partitions of other data. Check the displayed GPU, driver and the target disk's model, capacity and contents before confirming. A disk holding your own data is listed too, and a fresh installation erases it completely.
5. When installation finishes, choose **Proceed** to shut down, or **Cancel** to stay on the recovery desktop.
6. After shutdown, remove only the installer USB and boot from the installed disk.

**Install SteamOS (NVIDIA) to Disk** erases the chosen disk.
**Upgrade SteamOS (NVIDIA) - keeps games & data** reinstalls the OS on a recognized
SteamOS layout while retaining the data partition. Back up important files first.

## Install on an external USB disk

Use two separate devices: the installer USB and the external target disk.
Connect both before opening the installer. External disks are marked
**USB (external)** in the list. Check the model, capacity and what the disk
holds, then choose the external disk. A fresh installation erases it completely.

After shutdown, remove only the installer USB. Leave the installed external disk
connected and choose its UEFI entry in the computer's boot menu. The bootloader
is placed on that disk, including the standard removable-media boot path; it
selects SteamOS from the same disk. Do not unplug the disk while SteamOS is
running or suspended. Shut down before disconnecting it.

Use a USB SSD for a full installation. The minimum layout fits on a 16 GB device,
but games need additional space. This is a USB installation, not a promise
of portability between computers. Each PC must meet the graphics and UEFI
requirements. Booting the same USB installation on multiple PCs has been reported
working, but compatibility with every computer is not established.

The installer hides only its own disk and disks it cannot use: read-only disks, disks too small
for the SteamOS layout, and disks that do not use 512-byte logical sectors. A disk the desktop has
already mounted is still offered, and the partitions of the disk you choose are unmounted for you
before anything is written. If a partition is in use as swap, or one of them cannot be unmounted,
the installer stops and tells you which partition it is and what to do about it, then closes. Deal
with that partition, open the installer again and select the disk. This installer requires a disk
with 512-byte logical sectors. A disk with any other logical sector size is not offered at all,
and unmounting its partitions will not make it appear. Reinstalling while keeping home requires
the standard eight-partition SteamOS layout and enough room in both root partitions. A changed or
incomplete layout stops installation before writes.

## Finish Steam setup

Follow the network and account setup screens. The first start may require an OS
update. Leave the machine powered while the NVIDIA driver is rebuilt; this adds
time to the update. If setup reports a download error, see
[Updates and recovery](Updates-and-recovery.md) before repeatedly retrying.

After setup, check Game Mode, Desktop Mode and a game you know. Confirm audio
output, resolution and controller input, then restart once.

The fix for the corrupted Game Mode menus on NVIDIA rides on a Gamescope
build matched to one exact SteamOS package. It is chosen automatically, and
it steps aside if SteamOS later ships a Gamescope it was not built for,
without saying so on screen. This command says which build is in use:

```bash
cat /usr/lib/steamos-nvidia/gamescope/status.txt
```

A line beginning `capture-backport` means this project's build is active. A
line beginning `stock` means SteamOS's own build is, and the corrected menus
are not. Worth checking after an OS update. See [Check the Gamescope build
after an update](Updates-and-recovery.md#check-the-gamescope-build-after-an-update).

## Display settings

Open **Steam → Settings → Display**. New display profiles start with HDR off.
You can turn HDR on manually; the choice is kept across Steam restarts. A newly
connected screen may need a Steam restart before the default is applied.

Check the monitor's own information screen for the actual resolution and refresh
rate. If Steam shows the wrong Native resolution, turn **Automatically Set
Resolution** off and select the correct mode.

Know this before you raise the output above 1920x1080: the picture is corrupted as soon as the new
mode is applied, nothing on screen clears it, and the screen cannot be used until the session
restarts. The new mode is saved, so the session comes back clean in it. If it happens, restart the
Game Mode session from another computer on your network, or switch the PC off and on with its
power button. See [The picture is corrupted after raising the resolution in Game
Mode](Troubleshooting.md#the-picture-is-corrupted-after-raising-the-resolution-in-game-mode). Lowering the resolution does
not do this, and neither does going from 1280x720 up to 1920x1080. If the list offers 4096x2160,
choose 3840x2160 instead: 4096x2160 is accepted and saved, then quietly ignored, and the output
drops to whatever mode the display reports as its preferred one, with no message. Neither of these
faults is caused by this installer.

Image scaling is a separate setting. For green output over HDMI, leave HDR off or
use DisplayPort. See
[Troubleshooting](Troubleshooting.md).

## Xbox Bluetooth controller

Pair the controller through Bluetooth settings, then open Steam's controller
settings to test buttons, sticks, triggers and rumble. Check reconnect after
turning the controller off and on. Test Share inside a game with screenshots enabled.

Built-in SteamOS controller drivers are the default. If you deliberately built
with xpadneo, `modinfo hid_xpadneo` checks whether its module is installed.
Without xpadneo, a module-not-found response to that command is expected.

## Account and diagnostics

The local account is `deck`. Set a password in a terminal with `passwd`; there is
no shared SSH password supplied by this manual. SSH access requires an enabled
SSH service and your own password or authorized key.

The installer can perform its installation task without asking for a password.
Other administrative commands require your account password. To start SSH for
the current session after setting your password:

```bash
sudo systemctl start sshd
```

To stop it when finished:

```bash
sudo systemctl stop sshd
```

To collect a report, run as the desktop user:

```bash
steamos-nvidia-diagnostics > ~/steamos-nvidia-report.txt
```
