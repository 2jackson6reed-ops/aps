#!/usr/bin/env bash
set -euo pipefail

output_dir="${XFACT_BUILD_DIR:-build/xfact-live}"

python3 -m xfact os configure --output-dir "${output_dir}"
cd "${output_dir}"
sudo lb build "${@}"
