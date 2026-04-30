#!/usr/bin/env bash
set -euo pipefail

iso_path="${XFACT_ISO:-build/xfact-live/xfact-0.1.0-amd64.hybrid.iso}"
memory="${XFACT_QEMU_MEMORY:-1024}"
build_if_missing=1
force_rebuild=0
nographic=1
dry_run=0
qemu_args=()

usage() {
  cat <<'USAGE'
Usage: ./run-xfact.sh [options] [-- extra-qemu-args...]

Builds the xFact ISO if needed, then boots it in QEMU.

Options:
  --build          Build the ISO if it is missing (default).
  --no-build       Fail if the ISO is missing.
  --rebuild        Rebuild the ISO before booting.
  --gui            Open a QEMU display window instead of terminal-only mode.
  --display        Alias for --gui.
  --nographic      Run completely in this terminal (default).
  --dry-run        Print the QEMU command without running it.
  --memory MB      QEMU memory in MB (default: 1024).
  --iso PATH       Boot a specific ISO path.
  -h, --help       Show this help.

Examples:
  ./run-xfact.sh
  ./run-xfact.sh --rebuild
  ./run-xfact.sh --gui --memory 2048
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      build_if_missing=1
      shift
      ;;
    --no-build)
      build_if_missing=0
      shift
      ;;
    --rebuild)
      force_rebuild=1
      shift
      ;;
    --gui|--display)
      nographic=0
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --nographic)
      nographic=1
      shift
      ;;
    --memory)
      memory="${2:?--memory requires a value}"
      shift 2
      ;;
    --iso)
      iso_path="${2:?--iso requires a path}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      qemu_args+=("$@")
      break
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "Missing qemu-system-x86_64. Install qemu-system-x86 first." >&2
  exit 1
fi

if [[ "${force_rebuild}" -eq 1 ]]; then
  ./build-xfact.sh
elif [[ ! -f "${iso_path}" ]]; then
  if [[ "${build_if_missing}" -eq 1 ]]; then
    ./build-xfact.sh
  else
    echo "ISO not found: ${iso_path}" >&2
    echo "Run ./build-xfact.sh first or use ./run-xfact.sh --build." >&2
    exit 1
  fi
fi

if [[ ! -f "${iso_path}" ]]; then
  echo "ISO not found after build: ${iso_path}" >&2
  exit 1
fi

cmd=(
  qemu-system-x86_64
  -m "${memory}"
  -cdrom "${iso_path}"
  -boot d
  -no-reboot
)

if [[ "${nographic}" -eq 1 ]]; then
  cmd+=(-nographic -serial mon:stdio)
fi

cmd+=("${qemu_args[@]}")

echo "Booting xFact from ${iso_path}"
echo "Press Ctrl+A, then X to quit QEMU in terminal mode."
if [[ "${dry_run}" -eq 1 ]]; then
  printf 'QEMU command:'
  printf ' %q' "${cmd[@]}"
  printf '\n'
  exit 0
fi
exec "${cmd[@]}"
