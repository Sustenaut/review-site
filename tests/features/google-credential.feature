Feature: The app reaches Cloud Storage and Firestore with no key
  google-auth reads the external_account credential in
  k8s/google-credential.yaml, whose audience must be the projected token's and
  the services pool's provider. A mismatch fails only at run time, as Google's
  STS refusing the token.

  Scenario: The token the credential and the provider name one audience
    When google-auth reads the credential the app's pod mounts
    Then the result's "credential.type" is "external_account"
    And the result's "credential.audience" is "//iam.googleapis.com/projects/948171295184/locations/global/workloadIdentityPools/services/providers/sustenaut-k3s"
    And the result's "credential.service_account_impersonation_url" is "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/sustenaut-review-site@sustenaut.iam.gserviceaccount.com:generateAccessToken"
    And the result's "token audience" is "//iam.googleapis.com/projects/948171295184/locations/global/workloadIdentityPools/services/providers/sustenaut-k3s"
    And the result's "service account" is "app"
    And the result's "automount" is "false"
    And the result's "token file" is "/var/run/secrets/google/token"
    And the result's "credential.credential_source.file" is "/var/run/secrets/google/token"
    And the result's "credential file" is "/etc/google/credential.json"
    And the result's "GOOGLE_APPLICATION_CREDENTIALS" is "/etc/google/credential.json"
