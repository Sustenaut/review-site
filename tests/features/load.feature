Feature: What the pod's load container fetches, where the token may go, and what it bundles

  Scenario: It loads both heads into one directory and bundles it
    Then it loads both heads into one directory and bundles it

  Scenario: A tarball entry outside objects is left out
    Then a tarball entry outside objects is left out

  Scenario: An empty publication stops the pod
    Then an empty publication stops the pod

  Scenario: The token goes only to storage
    Then the token goes only to storage

  Scenario: Without a token it says where it looked
    Then without a token it says where it looked

  Scenario Outline: The index may name only files in the sources tenant
    When the index names "<name>" at the URL <where>
    Then the load refuses it as "<why>"

    Examples:
      | name      | where                      | why                        |
      | ../e.cbor | in the sources tenant      | not a file name            |
      | e.cbor    | none                       | not uploaded               |
      | e.cbor    | on another host            | outside the sources tenant |
      | e.cbor    | in the publications tenant | outside the sources tenant |
