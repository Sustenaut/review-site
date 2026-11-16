Feature: The app reaches Cloud Storage and Firestore with no key
  google-auth reads the external_account credential in
  k8s/google-credential.yaml, whose audience must be the projected token's and
  the services pool's provider. A mismatch fails only at run time, as Google's
  STS refusing the token.

  Scenario: The token the credential and the provider name one audience
    Then the token the credential and the provider name one audience
