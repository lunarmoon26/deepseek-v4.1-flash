#!/usr/bin/env bash
set -euo pipefail
# Mounted model paths are known only at container startup. This prepares files,
# not a second server; start.sh then runs Maya with the shared lock.
bash /opt/deployment/install.sh
exec bash /opt/deployment/start.sh "$@"
