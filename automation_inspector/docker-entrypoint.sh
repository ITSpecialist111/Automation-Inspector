#!/bin/sh
# Prepare unprivileged access to the app options, then drop privileges.
#
# Supervisor writes /data/options.json as root with mode 0600
# (supervisor/utils/json.py: write_json_file -> jsonfile.chmod(0o600)), so the
# unprivileged runtime user cannot read it. Copy it into tmpfs owned by that
# user instead of relaxing permissions on the Supervisor-managed file.
set -eu

if [ -f /data/options.json ]; then
	install -o inspector -g inspector -m 0400 /data/options.json "${AI_OPTIONS_PATH}"
fi

exec su-exec inspector:inspector "$@"
