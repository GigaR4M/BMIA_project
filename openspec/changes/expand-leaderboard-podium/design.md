# Design

## Visual Layout
- **Top Section (Podium)**: Remains largely unchanged. Top 3 users on podium blocks.
- **Bottom Section (List)**:
    - Located below the podium floor.
    - Background extended vertically.
    - List items arranged vertically.
    - **Row Format**: `[Rank #] [Avatar] [Username] ................. [Points]`
    - **Styling**:
        - Rank: White/Grey text.
        - Avatar: Small circle (approx 40-50px).
        - Username: White text.
        - Points: Gold text.
        - Alternating row background colors (optional, for readability).

## Data Flow
1.  `main.py` calls `db.get_top_users_date_range(..., limit=10)`.
2.  Passes list of 10 dicts to `PodiumBuilder.generate_podium`.
3.  `generate_podium` splits list: `top3 = users[:3]`, `others = users[3:]`.
4.  Draws podium using `top3` (existing logic).
5.  Calculates new height based on `len(others)`.
6.  Draws list using `others`.
