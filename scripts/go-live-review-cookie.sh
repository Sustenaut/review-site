#!/usr/bin/env bash
# Once, before the first deploy walk: keeps the cookie secret review.sustenaut.eu's oauth2-proxy
# already uses.
#
#   ./scripts/go-live-review-cookie.sh
#
# Until the walk, oauth2-proxy's cookie secret lived only in the Secret review-cookie
# (Sustenaut/business-plan's old review-site/go-live.sh made it on the server). The walk keeps it in Bitwarden as
# review-cookie-secret, and makes a new one when Bitwarden has none, which signs everyone out of
# the review site. This copies the cluster's value into Bitwarden instead, so the walk finds it
# ready and leaves review-cookie as it is.
#
# Signed in to Sustenaut's tailnet. It asks, at a hidden prompt, for a Bitwarden access token
# that may write to the project Sustenaut, and keeps it only in its process. The value travels
# in the SSH stream and in memory: never on a command line, never in a file. Run it again and it
# writes the same value. Delete this script once the walk is all ready.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(sed -n 's|.*/releases/download/v\([0-9][0-9.]*\)/pubkit-.*|\1|p' pubkit | head -n 1)
[[ -n "$version" ]] || { echo "go-live: no pubkit version in ./pubkit" >&2; exit 1; }

exec uvx --from "https://github.com/Sustenaut/pubkit/releases/download/v$version/pubkit-$version-py3-none-any.whl" \
  python -c '
import base64, subprocess, sys
from pubkit import k8s
from pubkit.deploy import BitwardenWriter
from pubkit.github_app import ask_hidden

ran = subprocess.run(["ssh", "root@sustenaut", "k3s kubectl -n review get secret review-cookie"
                      " -o jsonpath={.data.cookie-secret} --ignore-not-found"],
                     capture_output=True, text=True, check=False)
if ran.returncode != 0:
    sys.exit(f"go-live: could not read review-cookie: {ran.stderr.strip()}")
if not ran.stdout.strip():
    sys.exit("go-live: review-cookie has no cookie-secret: nothing to keep, so let the walk make one")
value = base64.b64decode(ran.stdout.strip())
if (why := k8s.cookie_secret(value)) is not None:
    sys.exit(f"go-live: the cookie-secret in review-cookie is not one oauth2-proxy takes ({why}): let the walk make one")
token = ask_hidden("Bitwarden access token with write access to Sustenaut (hidden, and not kept): ")
if not token:
    sys.exit("go-live: no token, nothing written")
BitwardenWriter(token, "Sustenaut").write("review-cookie-secret", value.decode(), "copied from review-cookie, as oauth2-proxy-cookie")
print(f"go-live: review-cookie-secret is in Bitwarden: {len(value)} bytes, the value review-cookie holds")
'
