## ADDED Requirements

#### Scenario: User requests explanation of dynamic roles
- When a user invokes `/autorole explicar`
- Then the bot sends an ephemeral embed response
- And the embed lists all dynamic roles configured in the system (e.g. Streamer, Camaleão, Voz)
- And each listing includes the role mention (if configured) and a description of how to earn it.
