#!/usr/bin/env bash
# Instala los hooks versionados en .git/hooks/.
# Idempotente: sobreescribe si ya existe.
#
# Uso: bash tools/hooks/install.sh

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_SRC="$REPO_ROOT/tools/hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DST" ]; then
  echo "ERROR: $HOOKS_DST no existe. ¿Estas dentro de un git repo?" >&2
  exit 1
fi

for hook in pre-commit; do
  src="$HOOKS_SRC/$hook"
  dst="$HOOKS_DST/$hook"
  if [ ! -f "$src" ]; then
    echo "WARN: $src no existe, skip"
    continue
  fi
  cp "$src" "$dst"
  chmod +x "$dst"
  echo "instalado: $dst"
done

echo "OK"
