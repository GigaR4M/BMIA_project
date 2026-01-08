# Design: Explain Dynamic Roles

## User Interface
- **Command**: `/autorole explicar`
- **Output**: Discord Embed
  - **Title**: "🏆 Cargos Dinâmicos & Conquistas"
  - **Description**: "Estes cargos são disputados durante todo o ano e entregues aos melhores em cada categoria!"
  - **Fields**:
    - **Top 1, 2, 3**: "Maiores pontuadores gerais (Atividade + Voz + Jogo)"
    - **Streamer**: "Maior tempo transmitindo vídeo em canais de voz"
    - **Camaleão Gamer**: "Maior variedade de jogos diferentes jogados"
    - etc.
  - **Note**: Mention updates happen periodically (e.g., hourly/daily).

## Implementation Details
- The descriptions map to the keys in `RoleManager.dynamic_roles_config`.
- We can hardcode the descriptions in `RoleCommands` or move them to `RoleManager` for better cohesion.
- Decision: Hardcode in command for simplicity unless reused.
