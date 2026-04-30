#!/usr/bin/env bash
set -euo pipefail

output_dir="${XFACT_BUILD_DIR:-build/xfact-live}"
iso_name="xfact-0.1.0-amd64.hybrid.iso"

python3 -m xfact os configure --output-dir "${output_dir}"
cd "${output_dir}"
sudo lb build "${@}"
if [[ -f live-image-amd64.hybrid.iso && ! -f "${iso_name}" ]]; then
  mv live-image-amd64.hybrid.iso "${iso_name}"
fi
