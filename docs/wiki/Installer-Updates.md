[Manual home](README.md)

# Update installer tools

**SteamOS NVIDIA Installer Update** updates this project's tools and fixes on an
installed system. It is separate from Steam's OS update and Change NVIDIA Driver.
The selected NVIDIA driver is retained. Changes to image building or disk layout
can still require a new installer; this tool applies the integration files
included in a compatible release package.

The shortcut is included only in builds configured with a signed release source.
If it is missing, updating SteamOS will not add it. Use an installer that includes
the updater or a bootstrap procedure supplied by the maintainer.

## Install an update

1. Finish any pending SteamOS update and reboot first.
2. Open **SteamOS NVIDIA Installer Update** in Desktop Mode.
3. Choose **Check for updates**. The window shows the source, the installed
   version, the available version, a link to the release page and the release
   notes. Long notes are shortened, and the full text is on the release page.
4. Choose **Continue** and enter your normal SteamOS password when requested.
5. Leave the PC powered while it prepares the other OS slot. Copying and checking the system
   can leave the window looking paused for several minutes.
6. After success, choose **Restart** or **Later**. The new version takes effect
   after restarting. Check a game, audio, your controller and sleep/resume.

Preparation normally needs about 17 GiB free on /home. It replaces the inactive
OS slot, including any earlier system stored there. The running slot is retained.
An update does not require writing another USB installer.

A later SteamOS update does not undo an installer tools update. The version you
installed with this tool stays installed, the pinned NVIDIA driver is kept, and
the configured release source and its verification key come through with them,
so the next check still works. You do not need to run this tool again after an
OS update.

That was measured on one PC, an Intel Core i5-10400F with a GeForce RTX 5060.
Tools 0.1.2 were installed with this tool on SteamOS 3.8.16, the PC was then
updated to 3.8.27 on the beta channel and returned to 3.8.16. At every step the
installed tools version, the release it came from, the NVIDIA driver, the
configured source and the verification key were unchanged, and a release check
still reported the installed version correctly. That single measurement does not
cover other graphics cards or later SteamOS releases. If the installed tools
version drops after an OS update, or the shortcut disappears, that is worth
reporting, with the diagnostic report described at the end of this page.

Public images use this repository's GitHub Releases and the bundled public
verification key. The updater accepts signed release packages from that
source. Stable sources reject prereleases. An unavailable server does not cause the updater
to switch to another source.

The updater only delivers components included in its signed package. From
release 0.1.9 that package can carry Gamescope, so a corrected Gamescope build
reaches an installed system without building and installing a new image. The
performance overlay has been carried the same way since the first release.
Receiver and NVENC binaries are not carried: files already on the system are
kept, but an update cannot add those two to a system that lacks them, so use a
prepared image when you need them. If the installed tools are 0.1.8 or older,
read [Updating from an older installer](#updating-from-an-older-installer)
before you update.

## Updating from an older installer

Release packages carry the complete current set of installer tools, so from 0.1.9 onwards the
update window always offers the newest release and you do not have to install the releases in
between. Older tools need extra steps; the sequence below avoids skipped files.
Two limits apply. An installed version writes only the files it was built knowing about,
so a file that was added to the list in a later
release does not arrive until a version that knows where it goes has been installed. Tools older
than 0.1.8 are stricter still: they refuse a release that carries any file name they do not know,
so on those the check stops instead of offering the newest release, and the window shows
`Installer update failed: Release has missing or unexpected files`. Nothing is written to the
other slot. That message means the age limit, not a damaged download or a bad release, and an
older release has to be asked for by name.

The signed package names the SteamOS versions the release was tested on. A
SteamOS older than the oldest version named is refused, so finish updating
SteamOS first. Any SteamOS from that version upwards is accepted, with a warning
when it is not one of the versions named, and the update then stops with an
error rather than continuing quietly if any part of the integration does not fit
that system.

Tools from 0.1.6 onwards behave that way. Older ones are stricter here too: they
accept only a SteamOS version the release names exactly and refuse every other
one, so on those an update can stop even though a newer release exists, and a
prepared image is then the way forward.

Release 0.1.9 taught the updater the Gamescope file names, and 0.2.0 is the
release that places the corrected Gamescope build on a system that is
already installed. To place that build in one subsequent update, first reach
0.1.9 using the sequence below. Tools on 0.1.8 can instead install the current
release, restart and use the repair path described below to place the files
they skipped. Tools older than 0.1.8 have to reach 0.1.8 before that, because
those versions refuse a
release that carries Gamescope at all. The update window only ever offers
the newest release, so ask for the release you need by name from a terminal
in Desktop Mode.

The commands below name 0.1.9. If your tools are older than 0.1.8, run them
once with v0.1.8 in place of v0.1.9 and restart, then run them again as they
are written. Every released version from 0.1.0 to 0.1.7 was checked against
the published 0.1.8 and 0.1.9 packages: each one accepts 0.1.8 and refuses
0.1.9, and 0.1.8 names the same SteamOS versions as 0.1.9, so the extra step
asks nothing more of the system than the release after it. Asking for a
release by name was run on a machine. The extra step itself has not been
carried out on a system that old, so please say how it went.

```bash
steamos-nvidia-installer-update check v0.1.9
```

That prints one long line of release information in braces and quotes, and it
confirms that the release is there and properly signed. Find `manifest_sha256`
in that line and copy the 64 characters in quotes right after it. If that is
hard to pick out on screen, this prints the same value on its own:

```bash
steamos-nvidia-installer-update check v0.1.9 | python3 -c "import json,sys; print(json.load(sys.stdin)['manifest_sha256'])"
```

Then install that release with it:

```bash
sudo steamos-nvidia-installer-update install v0.1.9 PASTE_THE_MANIFEST_SHA256
```

Restart, then open **SteamOS NVIDIA Installer Update** and install the current
release in the normal way.

If the skip has already happened, restart into the updated tools and choose
**Check for updates** again. The tools now know the Gamescope file names. If a
newer release is available, the normal update can place those files. If the
latest release is already installed but its files are missing or differ, tools
from 0.2.1 onwards can offer to install that same release again. Choose
**Continue**, wait for preparation to finish and restart. There is no need to
return to 0.1.9 first. See [Repair an incomplete release](#repair-an-incomplete-release).

To see which release your tools are on, rather than the release the image was
built from:

```bash
cat /usr/lib/steamos-nvidia/integration-version.json
```

That file is what the stepping rule above is about. The Installer version
line in the build information is the release the USB image was built from
and does not change when the tools are updated, so the two can differ by
several releases on a working system.

Changes to the complete image builder are available in the source archive. They
do not require rebuilding a working installation just to receive runtime fixes.

## Repair an incomplete release

From 0.2.1, **Check for updates** can offer to install the same version again
when a file the signed release carries is missing, a symlink or not a regular
file, or when a Gamescope or performance-overlay file cannot be read or has a
different checksum.
The window lists the affected files. This can happen after an older updater
skipped file names it did not know; the message describes the difference and
does not prove its cause.

Choose **Continue** to prepare the signed release in the inactive OS slot, then
restart. Repair uses the same space requirement, signature checks and rollback
mechanism as an ordinary installer update. It does not reinstall SteamOS or
replace your games and home data. It only repairs components carried by the
release, so it cannot add receiver or NVENC binaries absent from that package.
If these checks find no differences, the window reports that the tools are up
to date.

## Where updates come from after 0.2.2

Release 0.2.2 moves this project to a new repository. On your system the change is one
file, `/usr/lib/steamos-nvidia/installer-update-source.json`, which holds the address the
update tool asks for releases.

0.2.2 is planned for publication on the old repository as well, so an installation already
updating from there finds the release where it already looks. Applying it writes the new
address into the system slot being prepared, and that address is in use once you restart
into that slot.

**From 0.1.9 onwards there is nothing to do by hand**, because the update window offers the
newest release directly. Below 0.1.9 follow the older-installer guidance above, including
its repair path if files were skipped. Tools older than 0.1.8 must first install 0.1.8;
that remains the required first step before they can accept the current package.

Three things the update deliberately leaves alone:

* **The verification key.** Releases are signed with the same key before and after the
  move. An installation that never takes 0.2.2 keeps checking for updates normally.
* **Any configuration that is not this project's own public channel.** The address is
  amended only where all five fields still match the configuration this project shipped,
  the key included. An image built with `--installer-update-source` pointing at a custom
  configuration, or one where any of those five fields was changed, is left exactly as it
  is. Only formatting is ignored, so a reindented copy of the project's own configuration
  still migrates.
* **The slot you can return to.** Every system slot carries its own copy of that file, so
  returning to the previous system also returns the previous address. That slot asks the
  old repository, where 0.2.2 is planned to be published too, so it can be applied again.

The old repository stays in place and keeps serving the releases already published. No
installation loses its update channel because of the move.

This describes what the release is built to do. The move has not yet been exercised on a
machine, and this page will be corrected if a test shows it behaves otherwise.

## Return to the previous system

Open the tool and choose **Return to previous system**, then restart after it
confirms success. Driver changes and installer updates share the same A/B slots:
the previous system means the one before the most recent completed transaction.
A later OS update can replace that slot, in which case rollback is refused.

This restores the previous system slot. It does not undo changes to games, saves
or other shared home data. Recovery is manual, not automatic after a failed boot.
If Game Mode cannot be displayed, use a text console or SSH:

```bash
sudo steamos-nvidia-installer-update status
sudo steamos-nvidia-installer-update rollback
```

Returning does not close the door on the newer version. Once the previous system
is running, choose **Check for updates** again: the newer release is offered and
installs in the normal way, with no repair step in between. One exception: if the
system you returned to carries tools 0.1.8 or older, read
[Updating from an older installer](#updating-from-an-older-installer)
first, because those versions cannot be taken straight to the current release.

This was measured on one PC, an Intel Core i5-10400F with a GeForce RTX 5060
running SteamOS 3.8.28, with the installer tools updated from 0.1.6 to 0.1.7.
Each installation took between two and three minutes. Before the tool changed the
boot selection it checked the previous system's driver and installed files, and
that system then started, reported the older tools version, and kept its driver
loaded and its root read only. The newer version was then installed again from
it, and it completed. That is one PC with one card, so treat it as a path that
has been proved rather than a guarantee for every configuration.

## If preparation fails

Keep the error and read the transaction status. Do not manually mark the target
slot valid. If the terminal closes, preparation can continue as a system service:

```bash
sudo steamos-nvidia-installer-update status
sudo journalctl -u steamos-installer-update --no-pager > ~/installer-update-log.txt
```

A signature or checksum failure stops installation. Check the configured source
and contact the maintainer rather than disabling verification. An unsupported
SteamOS version requires a compatible release.

These refusals happen while the release is being checked, before the other OS
slot is touched, so the running system is unchanged and there is nothing to undo.
The same is true of a release refused because its file list does not match what
the installed tools expect, which is reported as
`Release has missing or unexpected files`, and of a SteamOS older than the oldest
version the release names. Deal with the cause and check again.

A changed release after confirmation requires a new check. A pending OS update,
selected slot or another update operation must finish before starting this one.
After an interrupted preparation, reboot into the working system and check status
before retrying. Keep the installer USB available for recovery.

The diagnostic report separates the original image build from the currently
installed integration version. Include both with an update failure report.
