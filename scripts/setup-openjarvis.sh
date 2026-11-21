#!/bin/zsh
# Bootstrap pinned source; network downloads and Rust compilation are required.
set -euo pipefail
cd "${0:A:h:h}"
ROOT="$PWD"
REV=570d75425d50592d931bac7a17ce6b2621561c06
UV="$ROOT/.runtime/bin/uv"
[[ -x "$UV" ]] || { print -u2 'Install uv from its official distribution into .runtime/bin/uv first.'; exit 1; }
export UV_CACHE_DIR="$ROOT/.runtime/uv-cache"
export UV_PYTHON_INSTALL_DIR="$ROOT/.runtime/python"
if [[ ! -d vendor/openjarvis ]]; then
  mkdir -p vendor
  git init vendor/openjarvis
  git -C vendor/openjarvis remote add origin https://github.com/open-jarvis/OpenJarvis.git
  git -C vendor/openjarvis fetch --depth 1 origin "$REV"
  git -C vendor/openjarvis checkout --detach FETCH_HEAD
fi
[[ "$(git -C vendor/openjarvis rev-parse HEAD)" == "$REV" ]] || { print -u2 'Upstream revision differs; preserve checkout and review before setup.'; exit 1; }
if git -C vendor/openjarvis apply --check "$ROOT/patches/openjarvis-safety.patch"; then
  git -C vendor/openjarvis apply "$ROOT/patches/openjarvis-safety.patch"
else
  git -C vendor/openjarvis apply --reverse --check "$ROOT/patches/openjarvis-safety.patch"
fi
if [[ -x "$ROOT/.runtime/cargo/bin/cargo" ]]; then
  export CARGO_HOME="$ROOT/.runtime/cargo"
  export RUSTUP_HOME="$ROOT/.runtime/rustup"
  export PATH="$CARGO_HOME/bin:$PATH"
fi
command -v cargo >/dev/null || { print -u2 'Rust toolchain required; install from rustup official distribution.'; exit 1; }
"$UV" --system-certs python install 3.13
"$UV" --system-certs sync --locked --project vendor/openjarvis --python 3.13
export VIRTUAL_ENV="$ROOT/vendor/openjarvis/.venv"
# Debug build avoids the observed macOS release-extension LINKEDIT import failure.
"$VIRTUAL_ENV/bin/maturin" develop --manifest-path vendor/openjarvis/rust/crates/openjarvis-python/Cargo.toml
./scripts/test-openjarvis.sh
