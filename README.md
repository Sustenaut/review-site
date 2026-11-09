# review-site: review.sustenaut.eu on the Sustenaut k3s server

review.sustenaut.eu runs on the Sustenaut
k3s server (shared-infra's `infra/hetzner.tf`), namespace `review`, behind the team sign-in. It is
the same shape as Sustenaut/notebooks: oauth2-proxy in front, signing in with the team realm at
auth.sustenaut.eu, and the service asking on each request whether the person still has the role
`review` (the team access page, auth.sustenaut.eu/realms/team/access, is the one list). The code is
Sustenaut/review-tooling's `review-site/`, at the release the Dockerfile pins (v0.1.4, which has the
login `team+wallet`). This repository is what deploys it.

| Part | What it is |
|---|---|
| `Dockerfile` | The service, pub and `load.py`, with no data in it, so the image (`ghcr.io/sustenaut/review`) is public |
| `load.py` | Run by the pod's load container: fetches publication 0 and the paper extracts from storage and bundles them for the app |
| `k8s/` | The app, oauth2-proxy (team realm, `--allowed-group=review`) and the ingress; `admin/` the network policy |
| `.github/workflows/deploy.yml` | On each merge, once CI passes: build, check, push and, once `DEPLOY_REVIEW` is `on`, deploy to the server |
| `pubkit.json`, `deploy` | Everything else the deployment needs, which the deploy walk checks and makes (below) |

## What it shows, and where that comes from

Publication 0's objects and the paper extracts are private: they live in storage.sustenaut.eu's
`publications` and `sources` tenants, which the pod reads as `k8s:review/app` with a token
Kubernetes mounts for that audience. When the pod starts, its load container (`load.py`) reads two
named heads, fetches what they name into one directory, and runs `pub bundle` into a volume the
app reads its names from:

| Head | What it points at |
|---|---|
| `publications/head/publication-0` | the tarball of publication 0's objects |
| `sources/head/gathered` | an index of the extract objects, each one's name and address in the sources tenant |

Sustenaut/business-plan's editors move them, from their own machines, with
`python scripts/review-heads.py` there. A moved head shows once the pod starts again:
`ssh root@sustenaut k3s kubectl -n review rollout restart deployment/app`. If storage can't be
read, the load container fails and the old pod keeps serving.

The reviews, the held keys and the account-to-key links stay where they are: the buckets
`sustenaut-reviews` and `sustenaut-review-keys` and Firestore's `review_key_links`, written as
`sustenaut-review-site` with a key. A reviewer's account is still their email, so everyone keeps
their key. The wallet sign-in (realm `sustenaut`, client `review`) is still offered inside the
team sign-in, as it is inside IAP today.

## Deploying

`.github/workflows/deploy.yml` builds the image on each merge to main, once CI has passed, and
applies `k8s/` to namespace `review` with pubkit's `k8s-deploy.yml`, once `DEPLOY_REVIEW` is `on`.

pubkit.json's `deploy` block lists everything else the deployment needs, and pubkit's deploy walk
checks each need and makes what it can. To take the site live, or bring it back in step, from a
checkout of this repository with Sustenaut/shared-infra and Sustenaut/auth checked out beside it,
on a machine on the admin tailnet, signed in to `gh` and `gcloud`:

```sh
./with-secrets ./pubdeploy walk --fulfil --server sustenaut --zones ../shared-infra/pubkit.json
```

It checks every need, prints the plan, and waits for a typed `yes`; then it makes each missing
need it can, over the admin channel (`ssh root@sustenaut`), and checks it again. Every run can run
again: what is ready is left alone. In order:

| Need | What the walk does |
|---|---|
| the namespace `review` | the server's `sustenaut-app`, which makes it and its deploy identity |
| `gcp.service-account-key` `review-site-key` | the key for `sustenaut-review-site` (Sustenaut/business-plan's `infra/review-site.tf`): made and written to Bitwarden when it is missing or not one of the account's live keys |
| `bitwarden.secret` `auth-review-client-secret`, `review-session-secret` | the wallet sign-in's client secret (realm `sustenaut`, client `review`) and the key its session cookies are signed with: checked in Bitwarden, where a person puts them |
| the Secret `review-secrets` | made from those three; the app restarted |
| `bitwarden.generated` `review-cookie-secret` | oauth2-proxy's cookie secret: a new one of its shape, written to Bitwarden, when it is missing or misshapen |
| the Secret `review-cookie` | made from it; oauth2-proxy restarted |
| `auth.sign-in-client` | sustenaut.eu's team-site client in the team realm, role `review`: the approval record written into shared-infra's `infra/auth-approvals.json` when auth.sustenaut.eu wants one, and once the client is issued, the Secret `review-oidc` made from it on the server |
| `k8s.manifests` | `k8s/admin/network-policy.yaml` applied: only oauth2-proxy's pods may reach the app |
| the deploy settings | the server's variables and secrets in pubkit.json's `"secrets"` on this repository, checked |
| `DEPLOY_REVIEW` and the rollout | the gate on, once everything before it is ready, and `deploy.yml` run and waited for |
| `service.health` | `https://review.sustenaut.eu/healthz` answers |

A new key or cookie secret wants a Bitwarden token that may write: the walk asks for it once, at a
hidden prompt, and keeps it only in its process. An approval record is a change to shared-infra:
commit it there, merge, apply, and run the walk again. A new cookie secret signs everyone out of
the site, nothing more.

Some needs it only checks, and says what a person does:

- **The wallet sign-in's secrets** in Bitwarden, from Keycloak's realm `sustenaut`, client `review`.
- **The DNS record** for `review.sustenaut.eu`, in shared-infra's hosting block.
- **Who may use the site**: the column `review` on the team access page,
  https://auth.sustenaut.eu/realms/team/access.
- **The two heads** the pod loads from (above), and storage letting `k8s:review/app` read
  `publications` and `sources` (Sustenaut/storage's `tenants.json`).

`./pubdeploy walk` without `--fulfil` (or `pubdeploy check`) changes nothing, and
`./pubdeploy walk --offline` checks only the files. `.github/workflows/deploy-check.yml` walks
the deployment every 30 minutes, read-only, with the deploy key, and writes the walk to storage's
`plane` tenant; it fails when a need is missing, drift or blocked.

### A new server

Before the walk: steps 1 to 7 of Sustenaut/auth's `README.md`, "Deploying" (the server, the
tailnet, the deploy secrets); `./with-secrets terraform -chdir=infra apply` in shared-infra (the
DNS record and the `auth_team` output) and in Sustenaut/business-plan's `infra/` (the account
`sustenaut-review-site`, the buckets and Firestore); and the team realm, with everyone who may use
the site holding the role `review`. The package `ghcr.io/sustenaut/review` is **public** and holds
no data, so the cluster pulls it without a secret; give this repository write access under *Manage
Actions access*. Branch protection is `./pubkit protect Sustenaut/review-site`.
