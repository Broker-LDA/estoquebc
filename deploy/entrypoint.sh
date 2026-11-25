#!/bin/sh
set -eu

# A preparação termina antes de os workers aceitarem tráfego. Falha interrompe o deploy.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    python -m deploy.release
fi
exec "$@"
