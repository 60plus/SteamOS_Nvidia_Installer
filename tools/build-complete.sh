#!/bin/bash
# Compile the project's addons and build an installer from an original recovery image.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
usage() {
  cat <<'HELP'
Usage: sudo bash tools/build-complete.sh [OPTIONS] RECOVERY.img
  --workdir DIR   New directory on a Linux filesystem (must not exist)
  --source FILE   Updater source configuration (default: config/github-stable.json)
  --driver SPEC   NVIDIA package version (default: the tested driver in
                  config/build-baselines.json; "latest" takes whatever Arch
                  ships today, which this project has not tested)
  --keep-cuda     Keep compute libraries (default removes them)
  --help         Show this help
Builds MangoApp, Gamescope, Remote Play and NVENC from pinned sources.
Takes a clean SteamOS recovery image and needs at least 50 GiB free for work.
A release outside config/build-baselines.json is a warning, not a refusal.
Output is written next to the input. Existing output is never overwritten.
HELP
}
die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
baselines="$repo/config/build-baselines.json"
baseline_field() {
  python3 -c "import json,sys;v=json.load(open(sys.argv[1]))[sys.argv[2]];print(' '.join(v) if isinstance(v,list) else v)" \
    "$baselines" "$1" 2>/dev/null
}
original=("$@")
image='' work='' driver='' source="$repo/config/github-stable.json"
trim=(--trim-cuda)
while (( $# )); do
  case "$1" in
    --help) usage; exit 0;;
    --workdir|--source|--driver)
      (( $# >= 2 )) || die "Missing value for $1"
      case "$1" in --workdir) work=$2;; --source) source=$2;; --driver) driver=$2;; esac
      shift 2;;
    --keep-cuda) trim=(); shift;;
    -*) die "Unknown option: $1";;
    *) [[ -z $image ]] || die 'Specify exactly one input image'; image=$1; shift;;
  esac
done
[[ -n $image ]] || { usage; exit 2; }
[[ $EUID == 0 ]] || die 'Run with sudo inside the Linux build environment.'
# Fall back to the tested driver only when the caller named none, so --driver
# still wins and --help still works without the repository configuration.
[[ -n $driver ]] || driver="$(baseline_field tested_driver)" \
  || die 'Cannot read the tested driver from config/build-baselines.json. Pass --driver explicitly.'
[[ $driver == latest || $driver =~ ^[0-9]+(\.[0-9]+)*(-[0-9]+)?$ ]] || die 'Invalid driver version.'
image=$(realpath -e -- "$image")
source=$(realpath -e -- "$source")
[[ -f $image && $image == *.img && $(basename "$image") != *-nvidia*.img ]] || die 'Use the original unpacked recovery .img.'
[[ -r $source && -f $source ]] || die 'Updater source configuration is missing.'
output="${image%.img}-nvidia-usbinstall.img"
partial="${output%.img}.partial.img"
[[ ! -e $output && ! -e $output.sha256 ]] || die "Output already exists: $output. Move it aside before starting."
[[ ! -e $partial ]] || die "An unfinished image from an earlier build is in the way: $partial. It is not flashable. Delete it before starting."
[[ -n $work ]] || work="$(dirname "$image")/complete-build-$(date +%Y%m%d-%H%M%S)"
work=$(realpath -m -- "$work")
[[ ! -e $work && -d $(dirname "$work") ]] || die 'Work directory must be new and its parent must exist.'
[[ $work != *[:,\\]* && $work != *$'\n'* ]] || die 'Work path cannot contain commas, colons, backslashes or newlines.'
for tool in unshare flock chroot mount umount mountpoint losetup blkid findmnt rsync python3 tee sha256sum; do
  command -v "$tool" >/dev/null || die "Missing host tool: $tool"
done
if [[ ${STEAMOS_COMPLETE_NAMESPACE:-0} != 1 ]]; then
  exec unshare --mount --pid --fork --kill-child --mount-proc --propagation private -- env STEAMOS_COMPLETE_NAMESPACE=1 bash "$0" "${original[@]}"
fi
exec 8>/run/steamos-nvidia-complete.lock
flock -n 8 || die 'Another complete build is running.'
bash "$repo/tools/check-build-host.sh" "$image" "$(dirname "$work")"
free=$(df -Pm "$(dirname "$work")" | awk 'END {print $4}')
(( free >= 51200 )) || die 'Allow at least 50 GiB free for compilation, plus the input image and output filesystem space.'
# Check JSON without executing configuration content. The installer validates its schema.
python3 - "$source" <<'PY'
import json,sys
with open(sys.argv[1]) as f: value=json.load(f)
assert isinstance(value,dict) and value.get('public_key') and value.get('release_api'), 'Invalid updater source'
PY
# The installer's own preconditions, before hours of compiling. The artifact
# directories do not exist yet, so they are deliberately not passed.
printf 'Checking installer preconditions before compiling.\n'
bash "$repo/steamos-nvidia-installer.sh" --preflight \
  --driver "$driver" "${trim[@]}" \
  --installer-update-source "$source" "$image"
mkdir -- "$work"
exec > >(tee "$work/build.log") 2>&1
printf 'Work directory: %s\nInput: %s\n' "$work" "$image"
# The preparation of the build root lives in one place so that rebuilding a
# single artifact does not mean reproducing it by hand out of this script.
# shellcheck source=prepare-build-root.sh
source "$repo/tools/prepare-build-root.sh"
root="$work/root"
cleanup_mounts() { build_root_cleanup "$work"; }
finish() {
  local rc=$?
  trap - EXIT
  if ! cleanup_mounts; then echo "Mount cleanup failed. Keep $work intact for inspection." >&2; rc=1; fi
  if (( rc )); then echo "Build failed. Preserve $work/build.log; do not flash an incomplete output." >&2; fi
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -- "$work/artifacts"
build_root_prepare "$image" "$work"
# Valve replaces the recovery image without notice, so the version is recorded
# and reported, not required. The artifact builders still refuse a root that
# mixes release lines, which is the check that protects the produced image.
tested_recovery="$(baseline_field tested_recovery)" || tested_recovery=''
# shellcheck disable=SC2154  # set by build_root_prepare in the sourced library
if [[ -n $tested_recovery && " $tested_recovery " != *" $build_root_baseline "* ]]; then
  printf 'Warning: this recovery image is SteamOS %s. Validated for this project: %s.\n' "$build_root_baseline" "$tested_recovery" >&2
  printf 'The build continues. Report the result so the validated list can be updated.\n' >&2
fi
for component in mangoapp gamescope remote-play nvenc; do
  printf '\nBuilding %s. Compilation can remain quiet for several minutes.\n' "$component"
  bash "$repo/tools/build-$component.sh" "$root" "$work/artifacts/$component"
done
cleanup_mounts || die 'Cannot detach the artifact build environment; image build not started.'
# Only discard our new, now-unmounted compilation layer after all artifacts succeeded.
rm -rf -- "$work/upper" "$work/overlay-work"
printf '\nAll artifacts built. Starting installer image build.\n'
bash "$repo/steamos-nvidia-installer.sh" \
  --driver "$driver" "${trim[@]}" --workdir "$work/driver-cache" \
  --mangoapp-dir "$work/artifacts/mangoapp" \
  --gamescope-dir "$work/artifacts/gamescope" \
  --remote-play-dir "$work/artifacts/remote-play" \
  --nvenc-dir "$work/artifacts/nvenc" \
  --installer-update-source "$source" "$image"
[[ -s $output ]] || die 'Builder returned without an output image.'
(cd -- "$(dirname "$output")" && sha256sum -- "$(basename "$output")") > "$output.sha256"
printf '\nComplete: %s\nChecksum: %s.sha256\nArtifacts and log: %s\n' "$output" "$output" "$work"

