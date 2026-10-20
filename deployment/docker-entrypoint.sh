#!/usr/bin/env bash
set -euo pipefail
# Mounted model paths are known only at container startup. This prepares files,
# not a second server; start.sh then delegates to the generated launcher.
bash /opt/strata/install.sh
exec bash /opt/strata/start.sh "$@"
