#!/bin/bash
# Prepare the SteamOS build root the artifact builders compile against.
#
# The artifact builders, build-mangoapp.sh, build-gamescope.sh and their
# siblings, all take a prepared SteamOS root as their first argument and none of
# them creates one. Until this file existed that preparation lived in the middle
# of build-complete.sh, so rebuilding a single artifact meant reproducing it by
# hand from memory. It is now in one place, used by the complete build and
# available on its own.
#
# Two ways to use it:
#
#   sourced      source tools/prepare-build-root.sh, then call
#                build_root_prepare IMAGE WORKDIR. It leaves the root at
#                WORKDIR/root and reports the image version in
#                build_root_baseline. build_root_cleanup WORKDIR undoes the
#                mounts and detaches the loop device it recorded.
#
#   executed     sudo bash tools/prepare-build-root.sh RECOVERY.img WORKDIR
#                prepares the root, leaves it mounted and prints its path, so an
#                artifact builder can be pointed at it. Tear it down afterwards
#                with --cleanup WORKDIR.
#
# Reusing a work directory that already has an upper layer is supported on
# purpose: the packages an earlier preparation installed are the expensive part,
# and keeping them turns an artifact rebuild from an hour into minutes.

build_root_die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# The loop device is recorded in the work directory rather than in a variable,
# so that a cleanup run later, or from another process, detaches the right one.
build_root_loop_file='.build-root-loop'
# Set by build_root_prepare for its caller.
# shellcheck disable=SC2034
build_root_baseline=''

# Give the build chroot a resolver that really has a nameserver. A host that
# resolves through systemd-resolved's NSS module leaves /etc/resolv.conf as the
# stock comment-only file. The chroot has no such module, so the build would
# fail much later inside pacman with "Could not resolve host". The uplink file
# is tried before the stub file, because the stub listener can be turned off.
set_chroot_resolver() {
  local root="$1" candidate
  shift
  for candidate in "$@"; do
    [[ -r "$candidate" ]] || continue
    grep -Eq '^[[:space:]]*nameserver[[:space:]]+[^[:space:]#]' "$candidate" || continue
    rm -f -- "$root/etc/resolv.conf"          # whiteout in upper only
    cp -L -- "$candidate" "$root/etc/resolv.conf" || return 1
    printf 'Build chroot resolver: %s\n' "$candidate" >&2
    return 0
  done
  return 1
}

# Stop only processes whose root is our own build root, never host services.
# pacman-key can leave gpg-agent running with devices open inside the chroot.
build_root_stop_processes() {
  local root="$1"
  python3 - "$root" <<'STOP'
import os,signal,sys,time
from pathlib import Path
root=sys.argv[1]
def owned():
    result=[]
    for p in Path('/proc').glob('[0-9]*/root'):
        try:
            if os.readlink(p)==root: result.append(int(p.parent.name))
        except OSError: pass
    return result
for sig in (signal.SIGTERM, signal.SIGKILL):
    for pid in owned():
        try: os.kill(pid,sig)
        except ProcessLookupError: pass
    for _ in range(30):
        if not owned(): break
        time.sleep(0.1)
if owned(): raise SystemExit('Build-root processes did not stop')
STOP
}

# Undo what build_root_prepare mounted, for the work directory given. Safe to
# call when nothing is mounted, which is what the complete build's exit trap
# does when it fails before preparing anything.
build_root_cleanup() {
  local work="$1" ok=0 loop=''
  local root="$work/root" lower="$work/lower"
  if [[ -r "$work/$build_root_loop_file" ]]; then
    loop=$(<"$work/$build_root_loop_file")
  else
    # A root prepared before this file existed has no record. Recover the device
    # from what is mounted, so an old work directory can still be cleaned up.
    # findmnt can append a subvolume to the source, so the device is taken
    # with an expression rather than by stripping a fixed suffix.
    loop=$(findmnt -n -o SOURCE "$lower" 2>/dev/null \
      | sed -n 's|^\(/dev/loop[0-9][0-9]*\)p[0-9][0-9]*.*|\1|p')
  fi
  build_root_stop_processes "$root"
  if mountpoint -q "$root"; then umount -R "$root" || ok=1; fi
  if mountpoint -q "$lower"; then umount "$lower" || ok=1; fi
  if [[ -n $loop && $ok == 0 ]]; then
    losetup -d "$loop" && rm -f -- "$work/$build_root_loop_file" || ok=1
    printf 'Detached %s
' "$loop"
  fi
  return "$ok"
}

# Mount the recovery image read only and stack a writable overlay on it.
# Leaves build_root_path ready for chroot.
build_root_prepare() {
  local image="$1" work="$2" partition='' part baseline loop
  local lower="$work/lower" root="$work/root"
  build_root_path="$root"
  mkdir -p -- "$lower" "$root" "$work/upper" "$work/overlay-work"
  loop=$(losetup --read-only --find --show --partscan "$image")
  printf '%s\n' "$loop" > "$work/$build_root_loop_file"
  for part in "$loop"p*; do
    if [[ $(blkid -p -s PART_ENTRY_NAME -o value "$part" 2>/dev/null || true) == rootfs-A ]]; then
      partition=$part
      break
    fi
  done
  [[ -n $partition ]] || build_root_die 'Recovery image has no rootfs-A partition.'
  [[ $(blkid -p -s TYPE -o value "$partition") == btrfs ]] \
    || build_root_die 'Expected a Btrfs SteamOS recovery root.'
  mount -o ro,rescue=nologreplay "$partition" "$lower"
  # Read metadata, never source shell content from an external image.
  grep -Eq '^ID="?steamos"?$' "$lower/etc/os-release" \
    || build_root_die 'Not a SteamOS recovery image.'
  baseline=$(sed -n 's/^VERSION_ID="\?\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' \
    "$lower/etc/os-release" | head -n 1)
  [[ -n $baseline ]] || build_root_die 'The recovery image has no usable VERSION_ID.'
  # shellcheck disable=SC2034  # read by the caller, see the header
  build_root_baseline=$baseline
  printf 'Recovery baseline: SteamOS %s\n' "$baseline"
  mount -t overlay overlay \
    -o "index=off,lowerdir=$lower,upperdir=$work/upper,workdir=$work/overlay-work" \
    "$root"
  mount -t proc proc "$root/proc"
  mount --rbind /dev "$root/dev"
  mount --make-rslave "$root/dev"
  mount --rbind /sys "$root/sys"
  mount --make-rslave "$root/sys"
  set_chroot_resolver "$root" \
    /etc/resolv.conf /run/systemd/resolve/resolv.conf /run/systemd/resolve/stub-resolv.conf \
    || build_root_die 'No resolv.conf on this build host has a nameserver line, so the build chroot cannot resolve names. Point /etc/resolv.conf at /run/systemd/resolve/stub-resolv.conf, or write a nameserver line into it, then start the build again.'
  # Never disable package signatures. Initialize a private keyring in the overlay.
  chroot "$root" pacman-key --init
  chroot "$root" pacman-key --populate
  chroot "$root" pacman -Sy --noconfirm
}

# Executed rather than sourced: prepare a root for one artifact rebuild.
if [[ ${BASH_SOURCE[0]} == "${0}" ]]; then
  set -euo pipefail
  if [[ ${1:-} == --cleanup ]]; then
    [[ $EUID == 0 ]] || build_root_die 'Run with sudo.'
    work=$(realpath -e -- "${2:?Usage: prepare-build-root.sh --cleanup WORKDIR}")
    build_root_cleanup "$work"
    printf 'Unmounted %s. The upper layer is kept for the next rebuild.\n' "$work"
    exit 0
  fi
  [[ $# == 2 ]] || {
    printf 'Usage: sudo bash tools/prepare-build-root.sh RECOVERY.img WORKDIR\n' >&2
    printf '       sudo bash tools/prepare-build-root.sh --cleanup WORKDIR\n' >&2
    exit 2
  }
  [[ $EUID == 0 ]] || build_root_die 'Run with sudo inside the Linux build environment.'
  image=$(realpath -e -- "$1")
  work=$(realpath -m -- "$2")
  [[ $work != *[:,\\]* && $work != *$'\n'* ]] \
    || build_root_die 'Work path cannot contain commas, colons, backslashes or newlines.'
  mkdir -p -- "$work"
  if [[ -d $work/upper && -n $(ls -A "$work/upper" 2>/dev/null) ]]; then
    printf 'Reusing the existing upper layer in %s. Its installed packages are kept.\n' "$work"
  fi
  build_root_prepare "$image" "$work"
  printf 'Build root ready: %s\n' "$build_root_path"
  printf 'Point an artifact builder at it, for example:\n'
  printf '  sudo bash tools/build-gamescope.sh %s %s/artifacts/gamescope\n' "$build_root_path" "$work"
  printf 'When finished: sudo bash tools/prepare-build-root.sh --cleanup %s\n' "$work"
fi
