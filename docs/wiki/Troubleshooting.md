[Manual home](README.md)

# Troubleshooting

Change one setting at a time and keep the original value. Capture a report before applying a workaround so the failure can be compared with the result.

This page is grouped by the part of the system the problem is in.

- [Installing and first boot](#installing-and-first-boot)
- [Display and Game Mode](#display-and-game-mode)
- [Sound](#sound)
- [Controllers](#controllers)
- [Sleep and wake](#sleep-and-wake)
- [Remote Play and streaming](#remote-play-and-streaming)
- [Performance overlay](#performance-overlay)
- [Games, Steam and storage](#games-steam-and-storage)

## Installing and first boot

### Installer stops at the GPU check

The installer checks the NVIDIA driver before offering a destination disk. All
NVIDIA graphics cards must be detected by the driver included in the image, and
the running driver must match its installed package. This check works offline.

GTX 10xx and older are outside the supported range. For a GTX 16xx or RTX card,
check `nvidia-smi` in the installer desktop. If it fails, save the boot errors
and check that the image uses a driver supporting your card. If the driver was
changed during the live session, restart before trying again. A successful check
confirms driver initialization on this PC, not every game or display feature.

### Package or signature failure

Save the exact package name, URL and error. Check the build host's time, free space and server availability. A signature error is not the same as a missing package or a network timeout.

Do not automatically add `--skip-sigcheck`. The repair path deliberately stops on signature failures. Fix the underlying trust or package availability problem before retrying.

### Pinned package download fails

Temporary network and server failures are retried a limited number of times.
The report distinguishes an HTTP 404/410 from a transport or server failure.
For the pinned NVIDIA packages and egl-wayland2, the downloader can try the
same filename on the Arch archive or its package mirror. It never selects a
different version to complete a repair. Older versions may exist only in the
archive, so a mirror fallback is not guaranteed to succeed.

Downloads are staged in a temporary file and only replace the destination after
a successful, nonempty transfer. Package installation still applies the existing
signature and dependency checks. An unavailable archive index is reported as
unknown availability, not proof that a requested driver version does not exist.

If both sources fail, retain the error and retry later. A failed update repair
does not mark the target slot ready. Do not substitute another kernel's headers
or disable signature checks to resolve a network failure.

### Kernel module build failure

Record the image checksum, target kernel and selected NVIDIA or xpadneo version. Save the compiler output, especially the first actual error. Matching headers and a driver compatible with that kernel are required.

Do not copy a module from another kernel or manually create the completion marker.

### Not enough space

Check both the build workspace and the mounted image. During OS repair, also check `/home`. Having free space on the host does not mean the image's root partition has enough room.

`--trim-cuda` can reduce the driver payload if CUDA, OpenCL and OptiX are not needed. The script does not enlarge partitions. The build checks actual free space after copying and flushing the compressed payload, with a 256 MiB reserve. A copy or space-check failure means the output image is incomplete and must not be used.

If OS repair reaches its final space check, unused Btrfs metadata allocation can
leave little room for files even on a large SSD. The repair helper can compact a
limited number of metadata block groups in the inactive slot, then checks the
same 256 MiB reserve again. It does not delete files, resize partitions or reduce
metadata redundancy. If the reserve is still unavailable, the update stays blocked.
Save the repair log rather than removing the space check or enabling the slot manually.

### First setup reports an update download error near completion

An error such as `Unable to download the required update (2)` can also mean that
the final installation step failed after the OS was downloaded and written.
Save the logs before reinstalling or retrying repeatedly:

```bash
sudo journalctl -b -u rauc -u atomupd --no-pager -n 120
sudo tail -n 80 /var/log/steamos-nvidia-repatch.log
```

If the NVIDIA repair log does not exist, the failure may have happened before
that step. Messages about a missing `/efi/SteamOS/partsets/self`, an empty booted
slot or a missing other EFI device identify a boot-partition visibility problem.
They do not indicate that another NVIDIA driver or a larger disk is needed.

That cause was found and corrected. The update hook now runs in a mount namespace that keeps
receiving the system's own automounts, so the EFI and ESP partitions stay visible to it, while the
temporary mounts the hook makes stay out of the running system. This was proved on one PC: an RTX
5060 machine installed from scratch and then updated from SteamOS 3.8.14 to 3.8.16, with the repair
finishing and the root filesystem read-only afterwards.

If your installation was made before the correction, the corrected hook arrives with this project's
tools rather than with the SteamOS update. Open **SteamOS NVIDIA Installer Update**, install the
current release, restart so the prepared slot is the one running, and only then start the SteamOS
update. If the failure returns after that, report the exact repair log, the system journal and the
installer version. The message on its own does not identify the cause.

The same message has a second proved cause. If the repair log instead ends at the final free-space
check, the inactive OS slot was below the 256 MiB it has to keep free. On the tested PC only 253 MiB
were left, and the setup message said nothing about space. Read [Not enough space](#not-enough-space)
for what the repair does in that case. A log that shows neither an EFI message nor a space message
points at neither cause, so keep it and report it.

Do not manually activate the failed slot; the repair and validation steps must finish first.


If the repair log reports `gamescope/status.txt: FAILED` followed by
`Addon validation failed`, a generated selection status was incorrectly included
in the shipped-file checksum manifest. Downloading again cannot correct this.
Use a corrected installer or have the integration helper and manifest repaired
before retrying. The Gamescope binary must remain covered by checksum validation;
do not disable addon checks or manually activate the failed slot.

## Display and Game Mode

### Black screen

First distinguish a USB boot failure from an installed-system failure. Record whether the firmware logo appears, whether a text console works and which port connects the display.

If the installer USB stops at a blinking cursor, with or without a few SteamOS boot messages first,
check the image and the way it was written before you look at the graphics card. First make sure the
image came from a build that finished: an image left behind by a build that stopped partway has been
seen to reach a SteamOS boot registration message and then stop at a blinking cursor. While a build
runs the file ends in `-nvidia-usbinstall.partial.img`, and it is renamed only when the build
succeeds, so a file ending in `-nvidia-usbinstall.img` is a finished build. Check the time on the
file as well: after a failed build, the file with the finished name next to your recovery image is
the older image, not the one you have just tried to make.

Then check that the image was written straight to the USB drive. One reported setup did not boot
through Ventoy and booted after the image was written directly with Etcher, which is one setup and
not a claim that Ventoy fails everywhere. See [Write the USB](Build-the-USB-image.md#write-the-usb).
If the image is from a finished build, was written directly, and the USB still stops there, record
the exact last lines on screen, the graphics card, the USB port used and how the monitor is
connected, then report it. Boot registration, driver, storage and session start have not been shown
to cause this.

Try one display connected directly to the NVIDIA card. Remove adapters for the first comparison. Try `Ctrl+Alt+F4` to reach a text console and log in as `deck`. If a console is available, check `nvidia-smi`, `uname -r` and the boot errors. A successful driver query does not rule out a session or display problem.

The repository describes `steamos-session-select plasma` as a way to switch to Desktop Mode from a usable console. It changes the selected session, so record that change. New builds include an optional [Safe Graphics](Safe-Graphics.md) session.

### HDR and HDMI

**Try DisplayPort if HDMI gives you display problems.** Connect the monitor
directly to the NVIDIA card, without an adapter. This is a useful first check for
a green or blank screen, flickering, or problems enabling HDR and VRR.

HDR and VRR support depends on the GPU, driver, display and connection.
Check each feature separately. A working DisplayPort connection does not mean
the same settings will work over HDMI.

If HDMI produces a green or blank image with HDR enabled, switch to a working
connection such as DisplayPort and turn HDR off in **Steam > Settings > Display**.
Before reconnecting HDMI, select a lower refresh rate on the working connection.
Start with 60 Hz and test higher rates separately. HDR may work at a lower rate
even when a higher rate works only with HDR off. No single maximum applies to
every GPU, cable and display. Reconnect HDMI and check the monitor's signal information. HDMI and DisplayPort
can behave differently on the same display.

On the tested PC, HDR ran at 2560x1440 and 165 Hz over DisplayPort on SteamOS
3.8.28 with kernel 6.18.50, where an earlier attempt at 144 Hz on an older base
had not been stable. That is one display on one machine and is recorded as an
observation, not as a supported configuration.

New display profiles start with HDR off; an existing manual ON choice is retained.
Restart Steam after connecting a new monitor if its default has not been applied.
The setting does not force a resolution, refresh rate or scaling value.

If Steam's Native label shows 1080p on a 1440p screen, turn **Automatically Set
Resolution** off and select the correct mode. If the picture is corrupted as soon as the
new mode takes effect, see [the entry on raising the resolution in Game Mode](#the-picture-is-corrupted-after-raising-the-resolution-in-game-mode):
only restarting the session clears it. Check the monitor's own information
screen to distinguish the physical output from Steam's maximum game resolution.

### Flicker, missing refresh rate or TV problems

Start with a standard refresh rate and temporarily disable VRR and HDR through the available display settings. Record whether the problem affects Desktop Mode, Game Mode or both.

Test another cable and port separately. Record HDMI versus DisplayPort, monitor or TV model, resolution, refresh rate and scaling. Do not apply several compositor environment variables at once.

If changing the resolution from inside Game Mode leaves the picture corrupted, see [the entry on raising the resolution in Game Mode](#the-picture-is-corrupted-after-raising-the-resolution-in-game-mode).

If the picture only breaks up when you open the Quick Access menu or the menu behind the Steam
button while a game is running, that was a separate NVIDIA fault and release 0.2.0 fixes it. See
[Corrupted Game Mode menus on NVIDIA](#corrupted-game-mode-menus-on-nvidia).
On the tested PC it appeared over DisplayPort and over HDMI alike, so a different cable is not the
first thing to try for that one.

### Selecting a 4096x2160 mode does nothing

**Choose 3840x2160 instead.** It works immediately. On the television tested here that is the
panel's own resolution, while 4096x2160 is the cinema format and is wider than the panel.

On a display that offers 4096x2160, choosing it in Steam's display settings does not give you that
mode. The output goes to whatever mode the display declares as its preferred one, which on the set
tested here was the mode already in use. Steam records the choice, so the setting looks as though it
took effect, and nothing on screen says otherwise. Gamescope advertises those modes to Steam and
then refuses to set them: its own list of modes to ignore rejects every 4096x2160 mode whatever the
refresh rate, and with no match it falls back to the display's preferred mode without reporting
anything. This is upstream Gamescope behaviour and is not caused by anything this project installs.

Seen on an LG television over HDMI with the Gamescope build carried by release 0.2.0, version
3.16.23.6, on SteamOS 3.8.28. The list of modes to ignore is part of the Gamescope source itself,
the same in this project's build and in the build SteamOS ships, and it does not depend on your
graphics card or driver. A later Gamescope may treat these modes differently. Nothing this project
installs changes that list.

### Corrupted Game Mode menus on NVIDIA

**This was a real fault and release 0.2.0 fixes it.** With a game running and the performance
overlay off, opening the Quick Access menu or the menu behind the Steam button used to leave large
parts of the screen corrupted. The upper part of the menu stayed readable while much of the area
around it did not: displaced and repeated fragments of the interface, black rectangles, colored
bands and speckle. In one case much of the game behind it remained legible, in another almost none
of it did.

**The cause is not in this project.** Gamescope can hand the game and Steam's interface straight to
two hardware display planes and let the graphics card blend them, instead of composing the frame
itself, and on an NVIDIA display output that blend is drawn wrongly. The Gamescope build carried by
0.2.0 refuses that route whenever a layer above the base layer needs alpha blending. The decision is
made from the display output the system actually opened, not from the card that renders, so a screen
on an AMD or Intel output behaves exactly as before. It is on by default and there is nothing to
set. `GAMESCOPE_NVIDIA_COMPOSITE_ALPHA=0` turns it off, which is only useful for a comparison.

**If your installation is 0.1.8 or older, take one step at a time.** An update writes only the
files the installed copy of the update tool already knows about, and Gamescope joined that list in
0.1.9. A system on 0.1.8 that jumps straight to a later release installs the tools, skips the
Gamescope binary without stopping, and then reports itself up to date without the fix. Tools older
than 0.1.8 are stricter and refuse such a release outright, so they have to reach 0.1.8 before
that. [Updating from an older installer](Installer-Updates.md#updating-from-an-older-installer) gives the exact
sequence. On 0.1.9 or newer, or on a system installed from a 0.1.9 image or newer, install the
current release and restart.

The corrected Gamescope is selected when the build itself accepts the flags your Game Mode session
passes it. That is asked when the system is installed and again after every repair, inside the system
being prepared and with no display opened. The Gamescope package SteamOS has installed and the
SteamOS release are not part of the decision. If the build does not accept those flags it stands
aside on the distribution's own build, the symptom can come back until a new artifact exists, and a
diagnostic report names which one is in use.

**The old workarounds are no longer needed.** Before 0.2.0, three display settings each avoided the
fault on their own, because each of them forced the frame to be composed: turning the performance
overlay on at any level, turning **HDR on**, and turning **Automatically Scale Image** off with the
slider that appears one step below its maximum. Release 0.2.0 composes the frame for you, so set all
three the way you prefer, and none of them is worth keeping for this reason. If a diagnostic report
ever shows the distribution's own Gamescope in use and the corruption returns with it, those three
settings still avoid it. Turning HDR on was never a general recommendation in any case: this
project records separate HDMI HDR problems, and new display profiles deliberately start with
HDR off.

Other things that were tried, with what they actually showed:

- **Moving the mouse** cleared it while the pointer kept moving, and it returned once the pointer
  hid. That is still worth knowing, because it tells this fault apart from a corrupted picture that
  nothing on screen clears.
- Turning **GPU accelerated rendering in web views** off removed the corruption on the tested
  machine and made the menus very slow. That setting changes several parts of rendering at once,
  so the result is a comparison rather than a diagnosis, and it was never a setting to keep.
- A **lower output resolution was never a workaround, and on the tested machine it turned out
  worse.** At 1080p60 the corruption also appeared in the main Steam interface with no game running
  at all, which never happened at 2560x1440. The likely reason is that the smaller the output, the
  more of the interface is exactly output sized, and output sized layers are the ones that qualify
  for a hardware plane. That is the model the fix is built on, rather than something measured
  inside the driver.

**What did not help, and what that does and does not prove.** Each of these was tried on its own
with the machine rebooted so every component started normally, and the corruption was unchanged:
the overlay SteamOS packages in place of this project's build, the Gamescope SteamOS packages in
place of this project's build, an older integration version, and a newer NVIDIA driver. So the
symptom reproduces with the distribution's own builds and is not created by this project's patched
ones. It does not follow that reinstalling or changing drivers can never help anyone: these were
particular substitutions on one machine, and reports elsewhere describe older drivers behaving
better.

**How it was narrowed.** The machine was read while one of those menus was corrupted and again
while the same menu was on screen and correct. The display mode, the plane's dimensions and its
format were the same in both, only the framebuffer identifier changed, which is what frames
flipping normally looks like, and no relevant errors appeared in the logs
examined. That comparison does not look at the pixels, the source surface,
synchronisation or buffer lifetime, so it narrowed where to look rather than settling
it. What settled it was a Gamescope built with extra tracing: in the state that
corrupts, the game and Steam's interface are on two hardware planes and nothing is
composed, while in every state that was clean the plane assignment failed or was never
attempted and the frame was composed. What is still not
identified is the defect inside the NVIDIA driver that makes that route fail, and whether other
reports of corrupted menus share this cause.

Two further observations from the same machine, scoped to it. At 2560x1440 the corruption behaved
the same at 60 Hz as at 165 Hz, which says that reducing the rate between those two modes did not
help here, not that timing is irrelevant. And SteamOS offers the modes a display declares, so a
resolution and refresh rate combination available in Windows can be absent here; on this display no
1080p mode above 60 Hz was offered.

An upstream report describes the same kind of corruption with unmodified Gamescope on NVIDIA,
[gamescope#1964](https://github.com/ValveSoftware/gamescope/issues/1964), including that it is
clean while the cursor is active and that older drivers behaved better.

**What this was proved on.** One PC: an RTX 5060 with NVIDIA driver 615.71.09 on SteamOS 3.8.28,
and one monitor, over both DisplayPort and HDMI, at 2560x1440 at 60, 120, 144 and 165 Hz and at
1920x1080 at 60 and 120 Hz, with HDR and the performance overlay each tried off and on, and VRR off
and on where the display offered it. The corruption was reproduced on purpose on both connections
before the change and did not come back on either afterwards, so the clean result is the change and
not a machine that stopped failing. That is one
graphics card and one screen. The change is written to the way the frame is presented rather than to
a card model, so it takes effect on any display output the kernel reports as an NVIDIA one, but no
other card has been tested here. A result from a different NVIDIA card is welcome either way: see
[Diagnostics](Diagnostics-and-test-results.md).

**If you still see this on 0.2.0 or newer**, first confirm which Gamescope your system is running.
Take a diagnostic report and find the section named `Experimental Gamescope selection`. A line
beginning `capture-backport` means this project's build is in use. A line beginning `stock` means
the distribution's own build is in use, so the fix is not present, and that happens when this
project's build did not accept the flags the session passes it rather than because an update went
wrong. The Game Mode session records the decision once at startup, in the journal of
`gamescope-session.service` in your own user session:

```bash
journalctl --user -b -u gamescope-session.service --no-pager | grep -i "composition policy"
```

The line to look for reads `NVIDIA alpha layer composition policy: enabled by default for
nvidia-drm`. If no such line is there at all, you are on an older Gamescope and the update order
above is the thing to check. If it says the policy is not applicable to another driver, or if a
warning says the driver of the display device could not be identified, the corrected Gamescope is
running but your screen is not on the NVIDIA kernel driver, so this fix does not apply to it. If it
says the policy is disabled by `GAMESCOPE_NVIDIA_COMPOSITE_ALPHA=0`, that variable has been set
somewhere and should be removed. If the policy is enabled and the menus are still
wrong, report the display, the connection, the resolution and refresh rate, whether HDR is on, the
two scaling settings, your driver and Gamescope versions, and a log with the time you reproduced it.

If moving the mouse does not clear it and only a session restart does, this is a different fault:
see [the entry below on raising the resolution in Game Mode](#the-picture-is-corrupted-after-raising-the-resolution-in-game-mode).

### The picture is corrupted after raising the resolution in Game Mode

Raising the output resolution while Game Mode is already running can corrupt the whole screen: the
picture drawn correctly and then repeated lower down at an offset, tiles that keep their shape while
filled with dense static, bands of noise. Switching HDR on while the output is at 3840x2160 can do the
same. Once it happens, the screen usually cannot be operated by hand.

**Release 0.2.4 fixes this where this project's Gamescope build is selected.** That build now hands
the display images allocated through GBM. With it, raising the resolution to 3840x2160, switching HDR
on and off at that resolution and switching VRR stayed correct through repeated changes, a game and
both overlays, and the picture was correct after a cold start with HDR already on. That was measured
on one machine: an RTX 5060 with NVIDIA driver 610.57.04, SteamOS 3.8.28 and a 4K monitor over
DisplayPort at 60 Hz. A television on HDMI was not tested again with 0.2.4, so on HDMI treat it as
untested rather than as fixed. [How it works](How-it-works.md#changing-the-output-to-4k-on-nvidia)
describes the change.

**If you still see it**, because the system runs Valve's own Gamescope or an older release, restarting
the Game Mode session is the workaround that has been verified to clear it. If you can reach the PC
from another computer on your network, restarting the session from there is enough. Otherwise restart
the machine with its power button. The resolution you chose is kept. If it was HDR you switched on,
HDR stays on too: with the Gamescope in 0.2.3 the restarted session then showed a corrupted band along
the bottom of the screen while the rest of the picture and the menus worked, so switch HDR off in the
display settings at that point.

What was measured before 0.2.4: starting a session at 3840x2160 with HDR off was clean, lowering the
resolution while the session ran was clean, and raising it from 1280x720 to 1920x1080 or from
1920x1080 to 2560x1440 was clean. The changes that corrupted the picture were 1920x1080 up to
3840x2160 on a 4K LG television over HDMI, with the Gamescope build carried by 0.2.0 and NVIDIA driver
615.71.09, and 2560x1440 up to 3840x2160 on a 4K monitor over DisplayPort with the build carried by
0.2.3, every time it was tried. Having been at a higher resolution earlier in the same session did not
protect against it.

It is not the release 0.2.0 menu fix: it happens with that fix switched off as well. Valve's packaged
Gamescope 3.16.23.6-1 corrupted the picture on the same resolution change on the same machine. The
image Gamescope composes is correct, and what goes wrong is the reading out of a finished image, which
is why allocating that image differently avoided it. Whether the underlying fault belongs to Gamescope
or to the NVIDIA driver below it has not been settled. Swapping the HDMI cable changed nothing, and on
DisplayPort the same cable carried a correct picture once the image was allocated through GBM.

Do not confuse it with the corrupted menus above. That one was cleared by moving the mouse and by a
few display settings, and 0.2.0 removes it outright. This one was cleared by restarting the session.

### Black border around Game Mode notifications

Steam notifications can have an opaque black background in Game Mode and in
Big Picture launched from Desktop Mode. Notifications in the regular desktop
Steam interface can look normal on the same system. This has been observed on
both HDMI and DisplayPort, including with HDR off. The background disappears
with the notification. Reproduction in desktop Big Picture without Gamescope
means the symptom is not limited to the Gamescope session.

Installer 0.1.2 includes a guarded workaround that selects Steam's embedded
notification renderer. It has been checked in desktop Big Picture, Game Mode,
over a running game and during Remote Play. Controller, download-complete and
message notifications displayed correctly, including game icons and avatars.
Restart, fresh installation with its first update, and the Beta to Preview to
Stable sequence passed with the supported client builds.

On an existing installation, use **SteamOS NVIDIA Installer Update** to install
the current release, then restart. Inspect its state without sudo:

```bash
python3 /usr/lib/steamos-nvidia/notification-renderer.py status
```

The command prints one line:

- `embedded renderer active on disk`: the workaround is applied.
- `original renderer on disk`: your Steam client is one of the reviewed versions, but the
  workaround is not applied at this moment. It is applied a little after Steam's own browser
  starts, so start Steam, give it a minute and check again, or use the `enable` command below.
- `legacy size-changing patch on disk`: an older form of the workaround is still on disk. The
  installed helper replaces it the next time Steam starts.
- a line beginning `unsupported`: your Steam client asset is not one this project has reviewed,
  so the helper left it alone on purpose.

A second line reading `Automatic application disabled by user` appears if you ran `disable`
earlier.

An unsupported result means the Steam client asset differs from the reviewed versions, which are
named in [How it works](How-it-works.md#embedded-steam-notifications).
The helper leaves it unchanged. A Steam client update can put you in this state and bring the black
border back. Nothing on your system switches the workaround back on at that point: the new client
asset has to be reviewed and carried by a later release. Do not manually replace code in an unknown
client version. Report the Steam client build number you are on, and whether you use the stable or
the beta client, following [Diagnostics](Diagnostics-and-test-results.md).
If you see any other line, report it with the same details.

To disable the workaround and restore the verified original, run the following
and restart Steam after closing your game:

```bash
python3 /usr/lib/steamos-nvidia/notification-renderer.py disable
```

Use `enable` instead of `disable` to apply it again. See
[How it works](How-it-works.md#embedded-steam-notifications) for the checks and
startup limitations. Safe Graphics has not removed this symptom.

### KDE reports that gamescope crashed when you leave Game Mode

Not caused by this project, and it does not interrupt what you were doing. Leaving
Game Mode for the desktop ends the Gamescope session, and on the way out Gamescope
faults while destroying its Vulkan device from a static destructor: it calls
`vkFreeCommandBuffers` through its own dispatch table, and by then the address in
that table is not mapped to anything, so the process dies on the instruction fetch
instead of exiting cleanly. The desktop starts normally a few seconds later.

What is measured, and what is not. The faulting address, the signal code and the
dispatch table entry were read out of core files on 3 October 2026 for two different
builds of the compositor, and both agree. **Why** that address stopped being mapped is
not established, so this page does not name a library as responsible. How often it
happens has not been measured either. Each occurrence writes a core file, which costs
disk space and a little time.

**No crash dialog appears**, despite the heading above, and that was checked rather than
assumed on 3 October 2026. KDE's handler does start, but it looks for KCrash metadata
that Gamescope never writes, logs `Nothing handled the dump`, and stops. Two crashes on
the test machine produced no window, which was checked on the screen rather than assumed.
So on a
SteamOS desktop the only trace you are likely to notice is the disk the dumps use: two
of them came to 20 MB. They are kept on the shared offload area under
`/var/lib/systemd/coredump`, so they survive a reboot and an A/B switch.

Confirmed on 2026-09-26 against Valve's own `gamescope 3.16.23.6-1` with this
project's artifact switched off for one session, which crashed the same way, so it
is not the capture correction. It is reported upstream as
[ValveSoftware/gamescope#1526](https://github.com/ValveSoftware/gamescope/issues/1526),
open since September 2024, where the first report carries the same backtrace with
line numbers and names the global Vulkan device that is destroyed too late. The backtrace ends in `exit`, with
`CVulkanDevice::~CVulkanDevice` and `CVulkanCmdBuffer::~CVulkanCmdBuffer` above it.
Core files are kept separately from the journal, so `journalctl --vacuum-time` does
not clear them: it removes archived journal files only. The dumps themselves live in
`/var/lib/systemd/coredump`, `coredumpctl list` shows what is there, and how long they
are kept is decided by `systemd-tmpfiles` together with the limits in
`/etc/systemd/coredump.conf`. `sudo systemd-tmpfiles --clean` applies that policy, and
a single file can be removed from that directory directly.

## Sound

### No HDMI or DisplayPort audio

Check the selected output and mute state in the desktop audio settings. Run `wpctl status` as the desktop user and record whether the display audio device appears. Test before and after sleep and after reconnecting the cable.

A display working does not prove its audio output is selected.

### Bluetooth headphones stay disconnected after wake

The installer includes an audio reconnect helper. It remembers paired, trusted
Bluetooth headphones or speakers connected just before sleep. After wake it waits
for the adapter and makes up to three connection attempts within 45 seconds.
Devices disconnected before sleep and game controllers are not included.
It does not change pairing, restart Bluetooth or connect devices at login.

Keep the headphones powered on and allow a few seconds after wake. If audio does
not return, check the output selected in SteamOS and try connecting manually.
Read the helper log from a terminal in your user session:

```bash
journalctl --user -b -u steamos-nvidia-bluetooth-resume.service --no-pager -n 40
```

To disable the helper for your account:

```bash
systemctl --user mask --now steamos-nvidia-bluetooth-resume.service
```

To restore it:

```bash
systemctl --user unmask steamos-nvidia-bluetooth-resume.service
systemctl --user start steamos-nvidia-bluetooth-resume.service
```

## Controllers

### Controller pairs but input fails

Start with the built-in SteamOS driver. Check buttons, Share and rumble in Steam and in a game before adding another driver. If you explicitly included xpadneo, check
`modinfo hid_xpadneo`. Record the Bluetooth adapter and compare with USB.

Record the controller model and firmware. If firmware is old, check for an update through Xbox Accessories on Windows, then pair again. Old firmware is one possible cause, not a diagnosis based on pairing alone.

The xpadneo build includes the original wrapper's global Bluetooth profile:
ControllerMode=dual, JustWorksRepairing=confirm, LE intervals 7/9 with latency 0,
UserspaceHID=true, ClassicBondedOnly=false and LEAutoSecurity=false.
Existing files are backed up as /etc/bluetooth/main.conf.before-xpadneo and
/etc/bluetooth/input.conf.before-xpadneo before modification. Review these
alongside the current files when comparing Bluetooth behavior. Update repairs
apply the same profile in the new slot. A --no-xpadneo build leaves Bluetooth
configuration alone.

## Sleep and wake

### Sleep or wake fails

Save a report before sleep and another after wake if the machine remains usable. Record whether the failure concerns video, audio, network or controller reconnect. Note whether the NVIDIA power services are enabled; that alone does not prove suspend support.

If a hard restart was necessary, previous-boot logs may help where persistent journaling is available. Sleep behavior depends on the hardware and driver.

### USB keyboard or controller cannot wake the PC

Check the motherboard's BIOS/UEFI settings before changing Linux configuration. USB wake may be disabled even when sleep and the case power button work normally.

On MSI boards, look under **Settings > Advanced > Wake Up Event Setup > Resume By USB Device** and set it to **Enabled**. Menu names vary by board and firmware. See [MSI's USB power and wake guide](https://us.msi.com/support/technical_details/MB_BIOS_Sleep_Hibernate).

Save the setting, boot SteamOS, suspend and test a wired USB keyboard first. Test pressing a button on an already connected controller separately from connecting a USB device during sleep. These actions may have different hardware support.

Bluetooth controller wake is a separate check. Working USB keyboard wake does not establish Bluetooth wake support; the adapter, controller and their wake settings also matter. The headphone reconnect helper runs after resume and does not wake the PC.

## Remote Play and streaming

### Red and blue are swapped in Remote Play or screenshots

Compare the local game image with the receiving device or saved image. If the
local image is correct but red and blue are swapped in the capture, record the
Gamescope and NVIDIA driver versions, the capture method, and the screenshot
format. Use a scene containing distinct red, green and blue areas.

An image built with all components in the [build guide](Build-the-USB-image.md#complete-build) includes both Remote Play color corrections. There is
nothing extra to enable: Gamescope corrects capture when SteamOS sends video,
and the private NVIDIA decoder corrects colors when SteamOS receives video.
Both directions have passed hardware tests. This does not establish correct
colors for every screenshot format; report screenshot failures separately.

When building an image yourself, include the artifacts with `--gamescope-dir`
and `--remote-play-dir`. These are build options, not switches that users of the
resulting image need to set. The SteamOS update repair hook preserves the included
artifacts. Since 0.1.9 the updater knows how to place a Gamescope build, and release 0.2.0 is the one that carries the corrected build, so Installer Update can deliver the Gamescope binary to an
installed system, which is how the corrected menus reach a machine without
building a new image. It still does not add the Remote Play receiver binaries to
a system that lacks them, because those files are not in the list a release may
carry. See [How it works](How-it-works.md#capture-color-correction).
A green HDMI display or a frozen session is a different symptom.

### Remote Play client codec setting

On the receiving device, open Steam's **Settings > Remote Play > Advanced Client
Options**, enable **HEVC Video**, then disconnect and reconnect the stream. For
the reverse direction, check the same option on the other receiving device.

The complete installer image has passed a tester's Remote Play check in both
directions with HEVC enabled manually. This setting is not enabled automatically
by the installer. The result does not establish that HEVC is required for every
client or that H.264 cannot work. If HEVC does not resolve the problem, collect
the streaming logs and follow the display and encoder checks below.

### Remote Play connects but shows black video

Check the host's `~/.local/share/Steam/logs/streaming_log.txt` and Game Mode
journal. Record the capture method and encoder. A working local game does not
prove that capture works. Black video can occur with stock Gamescope as well.
An image built with all components in the [build guide](Build-the-USB-image.md#complete-build) includes sampled-image usage for the RGB-to-NV12
conversion alongside the color-layout correction. Outgoing Remote Play has passed
hardware testing with these fixes. If black video returns, collect the logs above.

`NVENC - No CUDA support` alone does not prove that libcuda is missing. Verify
library loading and initialization before adding packages. Steam can fall back
to software encoding while a separate capture problem still produces black video.

### Streamed colors are wrong but the receiver menu is correct

Include the direction of the stream in your report. When another PC sends video
to SteamOS, correct local menu colors with incorrect video colors can indicate a
decoded-frame format problem. Record the codec, hardware-decoding setting and
whether red and blue are reversed. Check the receiving client's
`/tmp/streaming_client.log` and the sending PC's `streaming_log.txt`.

A Gamescope capture patch addresses the sending side; it is not a general fix for
this receiving-side symptom. An image built with all components in the [build guide](Build-the-USB-image.md#complete-build) includes the NVIDIA
decoder correction for the NV12 chroma descriptor. For custom builds, include it
with `--remote-play-dir`; Installer Update does not add it to older systems.
Do not change monitor color calibration to compensate.

### Remote Play uses x264 instead of NVENC on RTX 50

Check whether the host log already says `hardware_enabled=true`. If it then reports
`NVENC - No CUDA support`, turning hardware encoding on again will not resolve the
initialization failure. The Linux Steam host can run its encoder in a 32-bit process.
NVIDIA does not support 32-bit CUDA applications on RTX 50 and newer architectures:
[32-bit CUDA support policy](https://nvidia.custhelp.com/app/answers/detail/a_id/5615).

On the tested RTX 5060, both CUDA libraries load, but 32-bit `cuInit` returns
`CUDA_ERROR_NO_DEVICE` while 64-bit initialization succeeds and detects one GPU.
Installing more copies of the same library does not fix this architecture limit.
This does not mean the GPU lacks NVENC. The Steam host needs a compatible encoding
path; software x264 remains the working fallback in this configuration.

This limitation is separate from capture colors and the 64-bit Remote Play receiver.
Correct receiving colors do not establish hardware encoding on the sending side.

An experimental [VAAPI encoding bridge](https://github.com/elFarto/nvidia-vaapi-driver/pull/427)
can pass frames from a 32-bit Steam host to a 64-bit NVENC helper. In this path,
Steam reports VAAPI HEVC even though the GPU performs NVENC encoding. Confirm both
the helper's encoding log and GPU encoder activity rather than relying on the
Steam label alone. An image built with all components in the [build guide](Build-the-USB-image.md#complete-build) includes the bridge; custom builds
include it with `--nvenc-dir`. Installer Update does not add it to older installations.
Fresh installation followed by the SteamOS 3.8.14 to 3.8.16 update has preserved
its files and automatic startup. HEVC SDR encoding at 1440p has worked on RTX 5060,
including after reboot and after suspend/resume. These results do not establish
compatibility with every GPU or future OS update. The receiver decoder remains separate.

For builds containing the bridge, check the user service with:

```sh
systemctl --user status steamos-nvidia-nvenc.service
journalctl --user -u steamos-nvidia-nvenc.service -b
```

A successful stream should name VAAPI HEVC or H264 in Steam's streaming log, while
the helper reports encoded frames. Early `NVENC - No CUDA support` messages can
still appear before Steam selects the working VAAPI bridge. Do not diagnose the
whole session from those earlier attempts alone.

To temporarily disable the helper for diagnosis, disconnect Remote Play, then run:

```sh
systemctl --user mask --runtime --now steamos-nvidia-nvenc.service
```

Reconnect and check which fallback Steam selects. Restore it with:

```sh
systemctl --user unmask --runtime steamos-nvidia-nvenc.service
systemctl --user start steamos-nvidia-nvenc.service
```

The runtime mask disappears at reboot. These commands apply to the integrated
service, not to earlier manual experiments. The receiver decoder is separate.

### The screen stays black after leaving a streamed game

This is a receiver defect that was measured and fixed on 2026-09-26. On an image
built before that fix, leaving a game that was being streamed to this machine can
leave Steam's `streaming_client` alive but unable to exit. Gamescope keeps that
window on screen, so its last frame stays visible and the machine looks hung
while it is in fact working.

Check whether the client is still running. The process name is truncated by the
kernel, so match the short form:

```sh
ps -eo pid,etime,comm | grep streaming_clien
```

If it is there at no CPU after the game has ended, that is this defect. Ending it
returns the screen without a reboot:

```sh
kill -9 "$(ps -eo pid,comm | awk '$2=="streaming_clien"{print $1; exit}')"
```

SIGTERM does not work, because the thread that would handle it is the one that is
stuck. An image built with all components in the [build guide](Build-the-USB-image.md#complete-build) contains the fix.
Installer Update cannot deliver it, because those files are not in the list a
release may carry, so an affected system needs a new image.

### The streamed desktop has black bars, or looks soft and washed out

Both are host and client behaviour in Steam, measured on 2026-09-26 and not
caused by anything this project installs. Record which one you have before
changing settings.

**Black bars above and below.** Steam's host applies the client's resolution as a
temporary display mode when a session starts, then takes its capture size from
whatever the desktop currently measures. When a game exits, Windows restores the
saved desktop mode, and if that mode has a different aspect ratio than the
receiving screen the picture is letterboxed from then on. An ultrawide 3440x1440
desktop sent to a 16:9 receiver arrives as 2560x1072 inside 2560x1440, which is
184 pixels of black at the top and the bottom.

Toggling any capture option in the host's Remote Play settings makes Steam rebuild
the capture path and reapply the matched mode, which restores the geometry without
reconnecting. To avoid it entirely, make the saved desktop mode match the
receiver's aspect ratio, or select a display that already does as the streaming
display in the host's advanced settings.

**A flat, washed out picture.** On the tested pair the stream arrived at 63.5
percent of the amplitude it left with: black stayed at 0, mid grey 128 arrived as
81, white 255 arrived as 162, stable across repeated screenshots. That is a linear
gain, not a limited against full range mismatch, which would lift black to 16, and
not a color matrix error, which leaves neutrals alone.

Measurement excluded the source on the sending PC, Gamescope's compositing, HDR,
hardware decoding and hardware encoding. Software decoding and disabling hardware
encoding on both sides changed nothing. Streaming the other way, with the game on
SteamOS and the PC receiving, was measured as correct on the same pair of machines:
white arrives as 255 there, against 162 in the failing direction. That rules out the
network, the codec and the machines as well. What remains is Steam's own conversion
to YUV and back. Do not compensate with monitor calibration, and do not expect a
different image build to change it. If you report it, include both directions,
the capture method and encoder from the host's `streaming_log.txt`, and the
levels you measure rather than a description.

### Remote Play shows no picture in Desktop Mode but works in Game Mode

Receiving a stream with hardware decoding fails on the KDE desktop and is correct
in Game Mode. Measured on 2026-09-26. The fault is in Steam's client, not in
anything this project installs.

The client records which decoder it chose, in the host's `streaming_log.txt`:

| | reported decoder |
| --- | --- |
| Game Mode | `CLIENT: VAAPI Vulkan hardware decoding` |
| Desktop Mode | `CLIENT: VAAPI DRM hardware decoding` |

In Game Mode the client runs under Gamescope, loads `libvulkan.so` and the
Gamescope Vulkan WSI layer, and takes its Vulkan path: no dropped frames, 249
Mbit/s negotiated. On the desktop there is no Gamescope, no WSI layer and no
Vulkan loaded in the client at all, and the DRM path it falls back to costs 153 ms
per frame for 6.1 frames per second. Instead of decoding, the client builds and
destroys its whole decoder three to four times a second, which the host reports as
a decode time of 58 to 74 ms, and the sender throttles to 2.5 Mbit/s. A reported
packet loss of over 90 percent is a consequence of that throttling, not its cause:
the network step measures under 1.2 ms throughout and the kernel drops nothing.

**Switch hardware decoding off** in the client's streaming settings, or receive in
Game Mode. With software decoding the same machine measures 1.66 ms per frame and
43.4 frames per second, which is enough for a 1440p stream.

The receiver driver is not the cause. Its own trace is identical line for line in
both modes up to and including decoder creation, and a different client on the
same desktop, Moonlight, decodes in hardware without trouble. That rules out the
GPU, the kernel driver, the compositor and the network.

### Streaming from Desktop Mode runs at about 25 frames per second

Steam's outgoing capture on the desktop is limited by capture, not by encoding.
The host's own report names the step:

```
capture 39.96  convert 0.00  encode 5.37  network 0.52  decode 0.26  display 0.29  (capture)
```

Forty milliseconds is 25 frames per second, and it is how Steam drives KDE's
screencast portal rather than a limit of the portal. Another application using the
same portal on the same machine logged `Compositor negotiated frame rate: max
164/1` and paced itself at 60 frames per second. There is nothing to set here.
Game Mode does not have this limit.

## Performance overlay

### GPU readings are zero in the performance overlay

The GPU load percentage can work while temperature, clock speed, power and VRAM
remain at zero. Some MangoApp versions keep the sensor selection from startup
when you change the overlay detail level. This does not by itself indicate a
faulty driver. Compare the readings with `nvidia-smi`.

An image built with all components in the [build guide](Build-the-USB-image.md#complete-build) includes the corrected MangoApp. Custom builds include
it with `--mangoapp-dir`. It refreshes the NVIDIA sensor selection
continuously. Voltage and junction temperature are hidden for NVIDIA because
this backend does not provide those readings. Ordinary GPU temperature remains
available. Levels 3 and 4 show each detected model above its GPU or CPU readings,
from release 0.1.8; levels 1 and 2 have no such rows, so they show no names. The
GPU name is shown when one card is in use. On 0.1.0 to 0.1.7 the same overlay
worked both names out at startup but printed them only in some sessions, so they
could appear one day and not the next with nothing changed on your PC. The
readings themselves were never affected by this, only the names.
The GPU capacity is rounded to whole GB for a compact product label; live VRAM
usage is shown separately. Other unsupported sensors, such as CPU power or RAM temperature, may
still be unavailable on a particular computer.

On a build without the correction, select the detailed overlay first, then run
this command from a terminal in your own user session:

```bash
systemctl --user restart gamescope-mangoapp.service
```

This restarts only the performance overlay. Changing its detail level can trigger
the problem again on an uncorrected build. To check which executable is running:

```bash
systemctl --user show gamescope-mangoapp.service -p ExecStart
```

The corrected build uses `/usr/lib/steamos-nvidia/mangoapp`. The original
`/usr/bin/mangoapp` remains installed. Report the executable path, SteamOS and
NVIDIA versions when submitting an overlay issue.

## Games, Steam and storage

### Steam login or library disappears

Record whether this happened after a reboot, OS update or USB reinstallation. Check that the intended disk booted. Preserve logs before reinstalling.

Use an image built from the current script if an older installer repeatedly clears Steam data. Updating the installer cannot recover already deleted files. Restore those from a backup.

If the games are on a second drive or a network share rather than on the system disk, check that
the drive is still mounted before you preserve logs or reinstall. See the next entry.

### An extra drive or a network share is no longer mounted

After a SteamOS update, or after changing the NVIDIA driver, a second drive or a network share is
not mounted any more, and Steam cannot find a library kept on it.

If you had added the drive to `/etc/fstab`, that line is gone. SteamOS replaces `/etc` on every
update and keeps only a short list of exceptions, and `/etc/fstab` is not on it. A driver change
ends in the same step, so it has the same effect. Nothing in this project changes that, and
reinstalling does not prevent it. Nothing on the drive itself is altered, so your files are still
there once it is mounted again.

Your old lines are set aside before they are removed, and you can read them back:

```bash
cat /etc/previous/fstab
```

Copy the lines you need into a systemd mount unit, which does survive an update. The template, the
mount point rule, the pitfalls and the same advice for a network share are in [Keeping extra drives mounted across updates](Updates-and-recovery.md#keeping-extra-drives-mounted-across-updates).
This was measured on SteamOS, through a driver change and through an OS update from 3.8.16 to
3.8.28.

### A game fails but the desktop works

Test a second game and record the Proton version. Compare a 64-bit game with one using a 32-bit component. If available, `vulkaninfo --summary` provides another graphics check; it is not included in the diagnostic script and may not be installed.

Temporarily test without overlays and record whether MangoHud changes the result.

### A game with any 32-bit component crashes a minute or two after launch

Not caused by anything this project installs, and not present on images it
builds, but worth naming because nothing in the symptom points at the cause.

SteamOS's performance overlay is injected into every title by the Gamescope
session rather than enabled per game, and its 32-bit capsule carries a hard link
dependency on `libxkbcommon.so.0` that Valve's `lib32-mangohud` package does not
declare. On a system missing `lib32-libxkbcommon`, any game with a 32-bit part, a
native 32-bit binary or a 32-bit anti-cheat helper, dies with a SIGSEGV shortly
after it starts. There is no GPU driver error and no memory pressure to find.

Images built by this project install the package, and the repair path reinstalls
it after every SteamOS update, so this should not reach you. If a game behaves
this way, confirm it is there:

```sh
pacman -Q lib32-libxkbcommon
```

Diagnosed by the community on the upstream project, which carries a fuller
write-up at
[docs/mangohud-32bit-crash-fix.md](https://github.com/28allday/steamos-nvidia-installer/blob/main/docs/mangohud-32bit-crash-fix.md).
