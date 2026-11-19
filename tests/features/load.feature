Feature: What the pod's load container fetches, where the token may go, and what it bundles

  Scenario: It loads both heads into one directory and bundles it
    Given a scratch directory
    And publication 0's tarball holding:
      | name           | data |
      | objects/a.cbor | A    |
      | objects/b.cbor | B    |
      | README         | x    |
    And the sources index naming "e.cbor" in the sources tenant, holding "E"
    When the load bundles into "bundles"
    Then the result's "published" is "2"
    And the result's "cited" is "1"
    And the directory "bundles" holds:
      """
      a.cbor
      b.cbor
      e.cbor
      """
    And the file "bundles/a.cbor" holds "A"
    And the file "bundles/b.cbor" holds "B"
    And the file "bundles/e.cbor" holds "E"
    And storage was asked first for "publications/head/publication-0", then for "sources/head/gathered"

  Scenario: A tarball entry outside objects is left out
    Given a scratch directory
    And publication 0's tarball holding:
      | name               | data |
      | objects/a.cbor     | A    |
      | ../evil.cbor       | X    |
      | objects/sub/c.cbor | C    |
    When the load takes the tarball's objects into "objects"
    Then the result is "1"
    And the directory "objects" holds:
      """
      a.cbor
      """

  Scenario: An empty publication stops the pod
    Given a scratch directory
    And publication 0's tarball holding:
      | name | data |
    And an empty sources index
    When the load bundles into "bundles"
    Then it is refused, saying "no objects"
    And the refusal is a "load.LoadError"

  Scenario: The token goes only to storage
    When the load fetches "https://elsewhere.example/x"
    Then it is refused, saying "goes nowhere else"
    And the refusal is a "load.LoadError"

  Scenario: Without a token it says where it looked
    Given a scratch directory
    And a file "load.py" copied from "load.py"
    And the environment sets "STORAGE_TOKEN_FILE" to "missing"
    When I run "python3 load.py"
    Then the exit code is 1
    And stderr mentions "load: no storage token at missing"

  Scenario Outline: The index may name only files in the sources tenant
    Given a scratch directory
    When the index names "<name>" at the URL <where>
    Then it is refused, saying "<why>"
    And the refusal is a "load.LoadError"

    Examples:
      | name      | where                      | why                        |
      | ../e.cbor | in the sources tenant      | not a file name            |
      | e.cbor    | none                       | not uploaded               |
      | e.cbor    | on another host            | outside the sources tenant |
      | e.cbor    | in the publications tenant | outside the sources tenant |
