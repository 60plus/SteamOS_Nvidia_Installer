[Manual home](README.md)

# Safe Graphics

Safe Graphics is an optional recovery session for Game Mode display problems. It is off by
default, and every image this project builds includes it. If the command is missing on an older
installation, install the current release with [SteamOS NVIDIA Installer
Update](Installer-Updates.md); it
carries Safe Graphics, so you do not need to build a new image for it. If that shortcut is not in
your Desktop Mode menu either, install a current image.

Keep your working installer USB. Safe Graphics must be selected manually; it is
not an automatic rollback or a boot-menu entry.

## Enable

Connect one monitor directly to the NVIDIA card. From Desktop Mode, a text console
or SSH, run as `deck`, without sudo:

```bash
steamos-nvidia-safe-graphics check
steamos-nvidia-safe-graphics on
```

`check` reads the advertised display modes and validates the session script without
changing settings. Save your game, then reboot or restart Game Mode. The command
does not interrupt the running session. A matching Enable Safe Graphics entry is
available in Desktop Mode's application menu.

Recovery requests a supported progressive mode near 60 Hz: 1920x1080 first,
then 1280x720, 1024x768, 800x600 or 640x480. It refuses to guess if no candidate
is advertised or more than one screen is connected. The monitor's information
screen is the final check of the actual resolution and refresh rate.

The recovery session disables HDR and VRR advertising after Valve's environment
setup, pins the output to the single monitor it found instead of Valve's usual
preference, and forces composition. The actual HDR/VRR state should be checked
in the monitor's information screen. This is a troubleshooting option, not a fix
for every black or green screen.

One case does not need it. If the picture became unusable immediately after you
raised the output resolution while Game Mode was running, restart Game Mode
instead. The session keeps running and only the picture is affected, so nothing on
screen can be operated and you may need a text console or another machine to reach
the restart. The picture is correct again afterwards. This release does not fix that
problem and does not establish where it belongs; it has its own entry in
[Troubleshooting](Troubleshooting.md), with what was measured and what was not.

## Return to normal

```bash
steamos-nvidia-safe-graphics off
```

Save your work and restart Game Mode or reboot. With recovery off, the launcher
executes Valve's unchanged session. A matching Restore normal Game Mode graphics
entry is available in Desktop Mode's application menu. The helper does not
rewrite Steam preferences or remove your display profiles. Check those settings
afterward because Steam itself can save settings while using the recovery
session.

## Check status or recover from an error

```bash
steamos-nvidia-safe-graphics status
```

This reports the selection for the next Game Mode start, not the live signal.
If the recovery script rejects an unsupported session or display, use `off` from
a text console or SSH and restart. The selection is a per-user file at
`~/.config/steamos-nvidia/safe-graphics`; removing that file also selects normal
startup. It remains across reboots until turned off.

If no console or SSH is available, boot the saved USB to back up files and reach
the recovery desktop. See [Updates and recovery](Updates-and-recovery.md).
