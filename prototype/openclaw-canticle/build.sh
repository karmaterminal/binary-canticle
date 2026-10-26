#!/usr/bin/env bash
# Build the installable JavaScript entry from the same locked TypeScript toolchain CI uses.
set -euo pipefail

plugin_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$plugin_dir/../.." && pwd)
toolchain_dir=$(mktemp -d)
trap 'rm -rf -- "$toolchain_dir"' EXIT

cp "$repo_dir/.github/ci/openclaw-canticle/package.json" \
  "$repo_dir/.github/ci/openclaw-canticle/package-lock.json" "$toolchain_dir/"
npm ci --prefix "$toolchain_dir" --ignore-scripts --no-audit --no-fund
node "$toolchain_dir/node_modules/typescript/bin/tsc" \
  -p "$plugin_dir/tsconfig.build.json" \
  --typeRoots "$toolchain_dir/node_modules/@types"
test -f "$plugin_dir/dist/index.js"
