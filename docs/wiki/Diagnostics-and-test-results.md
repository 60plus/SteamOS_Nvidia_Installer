[Manual home](README.md)

# Diagnostics

## Save a report

Run this in Desktop Mode as the normal desktop user:

```bash
steamos-nvidia-diagnostics > ~/steamos-nvidia-report.txt
```

The command reads system information and saves it locally. It does not change
settings or upload the report. Running it as the desktop user preserves useful
session and audio information. Missing tools or inaccessible logs are listed.

For an update failure, also save:

```bash
sudo cat /var/log/steamos-nvidia-repatch.log > ~/steamos-nvidia-repatch.txt
```

Review logs before sharing them. Remove unrelated private content, but keep the
hardware, version and error details needed to understand the problem.

## Find the installer version

The diagnostic report includes `Installer version` under Original image build.
You can read it directly with:

```bash
grep '^Installer version:' /usr/lib/steamos-nvidia/build-info.txt
```

That is the release the image was built from. The release your tools are on,
which is what decides whether an update can carry Gamescope, is a different
file:

```bash
cat /usr/lib/steamos-nvidia/integration-version.json
```

The two differ on any system whose tools have been updated since it was
installed.

The Installed integration version section shows tools updated after installation,
where the desktop updater is included. Original image build remains unchanged.

This identifies the installer code used to create the image, not the current
SteamOS or NVIDIA version. An OS update does not turn it into a newer installer
release. When building from source, the repository's `VERSION` file contains
the version; a `-dev` suffix means a development build, not a published release.

Older images may not have this field. Report the image filename and Source commit
from the same file instead. Do not infer an installer version from SteamOS.

## Choose the right report

Use a bug report for a failure, a feature request for an improvement, or a
hardware compatibility report to share results from your PC. Keep separate
problems in separate reports. Mark untested features as Not tested rather than
assuming they work. A hardware report should include both successes and limits.

Open a report from the [Issues](https://github.com/60plus/SteamOS_Nvidia_Installer/issues)
page and choose one of those three forms. Blank issues are turned off, so start
from a form rather than an empty page.

## What to include with a support request

- CPU, GPU and monitor or TV model.
- HDMI or DisplayPort, adapters, resolution, refresh rate, HDR and VRR state.
- For a resolution or refresh rate problem, the saved Game Mode display mode.
- For a Game Mode display fault, the Gamescope composition policy line.
- SteamOS version and the image filename used to install it.
- Whether the problem happens from USB, after installation or after an update.
- Steps to reproduce and the exact error.
- Whether a text console works and whether restarting changes anything.
- For controllers: model, Bluetooth or USB connection and which buttons fail.

Game Mode records the resolution and refresh rate you picked for each display in
`~/.config/gamescope/modes.cfg`. It records the choice even when the picture did
not change, so it separates a choice that was never saved from a choice that was
saved and then ignored. If the file is not there, say so in the report rather
than treating it as damage.

Gamescope prints one line when Game Mode starts that says whether the correction
for the corrupted Game Mode menus is in effect on this display. Read it in
Desktop Mode or over SSH as your normal user:

```bash
journalctl --user -b -u gamescope-session.service | grep 'composition policy'
```

If that prints nothing, drop the unit and search the whole boot instead:

```bash
journalctl --user -b | grep 'composition policy'
```

The line is printed only when Game Mode starts, and both commands look at the current boot only,
so nothing will be found if this machine has not been in Game Mode since it was switched on. If
nothing is printed either way, say so in the report rather than leaving it out. A system running
the SteamOS Gamescope build does not carry the correction. The section Which Gamescope is in use,
below, says which build this machine is running, and that is what decides it rather than the
installer version.

Attach the report as a file rather than sending many photos of scrolling output.

## Useful checks

```bash
uname -r
nvidia-smi
wpctl status
bluetoothctl list
df -h / /home /tmp
```

`nvidia-smi` checks communication with the GPU; it does not prove that a game or
HDR works. `wpctl status` lists audio devices and routes. `bluetoothctl list`
lists Bluetooth adapters.

The report includes original build information and the versions installed during
update repair. It also lists saved HDR profiles; check the monitor's information
screen separately for the signal actually being displayed.


## Update and addon checks

The report includes the booted slot, root filesystem source, installed NVIDIA
package, module version on disk and loaded module version. Differences can help
identify a pending restart or an incomplete driver repair.

Addon checks compare the files this project installed with their recorded
checksums: the HDR initializer, Safe Graphics, the Bluetooth audio helper, the
diagnostics command, the installation helper, the service files, and whichever
optional components the image carries, such as the notification fix, the
performance overlay, this project's Gamescope build, Remote Play, NVENC, the
driver tools and the desktop updater. Generated status files and the
chosen session files are left out on purpose, because a system update can
change them. The checks also confirm the required command and
activation links. A failed check identifies an installation problem; passing
checks do not prove that a display or audio device works. User HDR choices and
the optional Safe Graphics setting are not overwritten.

The completion marker records a successful slot repair. Its presence alone does
not prove that the current boot or an application is healthy. Effective user
service definitions are included to help spot local overrides.


## Which Gamescope is in use

The report has a section named `Experimental Gamescope selection`. It reads
`capture-backport` when this project's own Gamescope build is in use, or `stock`
when the SteamOS build is in use, followed in brackets by the Gamescope package
the system has installed, or `unknown` when that could not be read. The
corrected Game Mode menu behaviour on NVIDIA is part of this project's build, so
a report that reads `stock` explains straight away why menus still look wrong.

You can read the same line directly:

```bash
cat /usr/lib/steamos-nvidia/gamescope/status.txt
```

The next section, `Game Mode executable search path`, shows whether the session
was pointed at this project's build. It also shows
`GAMESCOPE_NVIDIA_COMPOSITE_ALPHA` when the menu correction has been turned off
in a service override.

The choice is made when the system is installed or repaired. It returns to `stock` on purpose when
this project's build does not accept the flags the Game Mode session passes it, or when SteamOS
changes the way that session starts Gamescope, so `stock` is not by itself an installation fault.
Neither the Gamescope package the system has installed nor the SteamOS release decides it; the
package shown in brackets is recorded for the report only. On an image that carries no
Gamescope build of this project the file is absent and the section reports that it could not be
read.


## NVIDIA library compatibility

Builds and update repairs ask the target system's dynamic loaders to resolve
NVIDIA OpenGL/EGL dependencies for both 64-bit and 32-bit applications, plus the
64-bit management library. Missing libraries and unavailable symbol versions,
including glibc version requirements, stop completion with the loader's error.
The updater checks the repaired slot before marking it ready.

The last result is saved in `/usr/lib/steamos-nvidia/userspace-check.txt` and
included in diagnostics. Its timestamp describes the build or repair, not a new
live test. It does not exercise GPU rendering, Proton or game-specific libraries.
