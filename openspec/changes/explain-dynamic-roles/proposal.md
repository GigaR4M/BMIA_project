# Explain Dynamic Roles

## Goal
Add a new subcommand `/autorole explicar` (or similar) to list and explain the requirements for all dynamic roles (stat-based roles) configured in the server.

## Why
Users are currently unaware of the specific criteria required to obtain special roles like "Streamer do Servidor", "Camaleão Gamer", etc. Providing a command to explain these criteria increases transparency and engagement.

## Components
- `commands/role_commands.py`: Update to include the new subcommand.
- `utils/role_manager.py`: (Optional) Helper to get role descriptions if needed, but definitions are fairly static logic-wise.

## Validation
- [ ] User runs `/autorole explicar`.
- [ ] Bot returns an embed listing roles like "Streamer do Servidor" and their criteria (e.g., "Maior tempo de transmissão no ano").
