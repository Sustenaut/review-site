"""The app reaches Cloud Storage and Firestore with no key: google-auth reads the
external_account credential in k8s/google-credential.yaml, whose audience must be the projected
token's and the services pool's provider. A mismatch fails only at run time, as
Google's STS refusing the token."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pytest_bdd import scenarios, when

scenarios("google-credential.feature")

ROOT = Path(__file__).resolve().parents[2]


def mounted() -> dict:
    """What google-auth finds in the app's pod: the credential, the projected
    token it points at, and the variable that names the credential."""
    configmap = yaml.safe_load((ROOT / "k8s" / "google-credential.yaml").read_text(encoding="utf-8"))
    credential = json.loads(configmap["data"]["credential.json"])
    app = next(d for d in yaml.safe_load_all((ROOT / "k8s" / "app.yaml").read_text(encoding="utf-8"))
               if d and d["kind"] == "Deployment")
    spec = app["spec"]["template"]["spec"]
    (volume,) = [v for v in spec["volumes"] if v["name"] == "google-token"]
    (source,) = volume["projected"]["sources"]
    container = next(c for c in spec["containers"] if c["name"] == "app")
    mounts = {m["name"]: m["mountPath"] for m in container["volumeMounts"]}
    env = {e["name"]: e.get("value") for e in container["env"]}
    return {
        "credential": credential,
        "service account": spec["serviceAccountName"],
        "automount": spec["automountServiceAccountToken"],
        "token audience": source["serviceAccountToken"]["audience"],
        "token file": f"{mounts['google-token']}/{source['serviceAccountToken']['path']}",
        "credential file": f"{mounts['google-credential']}/credential.json",
        "GOOGLE_APPLICATION_CREDENTIALS": env["GOOGLE_APPLICATION_CREDENTIALS"],
    }


@when("google-auth reads the credential the app's pod mounts")
def reads_the_credential(ctx):
    ctx.attempt(mounted)
