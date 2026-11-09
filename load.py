"""Fills REVIEW_BUNDLES before the review service starts: the pod's load container runs it.

Publication 0's objects and the paper extracts live in storage.sustenaut.eu's private
`publications` and `sources` tenants, which this pod reads as `k8s:review/app`, with the
service-account token Kubernetes mounts for that audience. Two named heads say what to load,
and Sustenaut/business-plan's editors move them:

    publications/head/publication-0   the tarball of publication 0's objects
    sources/head/gathered             the sources index, whose "objects" map each extract's
                                      name to its address in the sources tenant

Each object goes into one directory, which `pub bundle` turns into the bundles the service
reads names from. Nothing is written but that directory and the bundles, and the token is
sent only to storage.sustenaut.eu.

    python load.py            # in the pod
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

STORAGE = os.environ.get("REVIEW_STORAGE", "https://storage.sustenaut.eu")
TOKEN = Path(os.environ.get("STORAGE_TOKEN_FILE", "/var/run/secrets/storage/token"))
PUBLICATION = f"{STORAGE}/publications/head/publication-0"
GATHERED = f"{STORAGE}/sources/head/gathered"
SOURCES = f"{STORAGE}/sources/"
# Named: Cloudflare refuses Python's default User-Agent (error 1010).
AGENT = "sustenaut-review-load"


class LoadError(Exception):
    pass


def get(url: str, token: str, opener=urllib.request.urlopen) -> bytes:
    if not url.startswith(f"{STORAGE}/"):
        raise LoadError(f"{url} is not on {STORAGE}: the token goes nowhere else")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": AGENT})
    try:
        with opener(request, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise LoadError(f"{url}: storage answered {e.code}") from None


def objects(tarball: bytes, into: Path) -> int:
    """Publication 0's tarball holds objects/<name>.cbor: each goes into `into`."""
    count = 0
    with tarfile.open(fileobj=io.BytesIO(tarball)) as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if not member.isfile() or not name.endswith(".cbor") or member.name != f"objects/{name}":
                continue
            (into / name).write_bytes(tar.extractfile(member).read())
            count += 1
    return count


def extracts(gathered: dict, token: str, into: Path, fetch=get) -> int:
    count = 0
    for name, url in (gathered.get("objects") or {}).items():
        if Path(name).name != name or not name:
            raise LoadError(f"the sources index names an object {name!r}, which is not a file name")
        if not url:
            raise LoadError(f"{name} is in the sources index but not uploaded")
        if not url.startswith(SOURCES):
            raise LoadError(f"{name} is at {url}, outside the sources tenant")
        (into / name).write_bytes(fetch(url, token))
        count += 1
    return count


def load(out: Path, token: str, fetch=get, bundle=None) -> tuple[int, int]:
    with tempfile.TemporaryDirectory() as work:
        into = Path(work)
        published = objects(fetch(PUBLICATION, token), into)
        if not published:
            raise LoadError("publication-0's tarball holds no objects")
        cited = extracts(json.loads(fetch(GATHERED, token)), token, into, fetch)
        (bundle or pub_bundle)(into, out)
    return published, cited


def pub_bundle(objects_dir: Path, out: Path) -> None:
    subprocess.run([os.environ.get("PUB", "pub"), "bundle", f"--dir={objects_dir}", f"--out={out}",
                    "--base=https://pub.sustenaut.eu"], check=True)


def main() -> int:
    out = Path(os.environ.get("REVIEW_BUNDLES", "/app/bundles"))
    try:
        token = TOKEN.read_text().strip()
    except OSError as e:
        print(f"load: no storage token at {TOKEN} ({e.strerror})", file=sys.stderr)
        return 1
    try:
        published, cited = load(out, token)
    except (LoadError, subprocess.CalledProcessError, ValueError, OSError) as e:
        print(f"load: {e}", file=sys.stderr)
        return 1
    print(f"load: bundled {published} object(s) of publication 0 and {cited} from the sources into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
