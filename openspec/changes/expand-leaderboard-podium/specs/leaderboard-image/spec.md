# Spec: Leaderboard Image Expansion

## ADDED Requirements

### 1. Expanded User Fetching
The system MUST fetch the top 10 users for the monthly/yearly leaderboard generation instead of the top 3.

#### Scenario: Monthly Check
- GIVEN the current date is the 1st of the month
- WHEN `check_monthly_podium` runs
- THEN it calls `db.get_top_users_date_range` with `limit=10`

### 2. Extended Image Generation
The `PodiumBuilder` MUST generate an image that includes the top 3 users on a podium and the subsequent users (ranks 4-10) in a detailed list below.

#### Scenario: Generates Full Leaderboard
- GIVEN a list of 10 users
- WHEN `generate_podium` is called
- THEN the resulting image height is sufficient to show the podium and 7 list rows
- AND the top 3 are displayed on the podium
- AND users 4 through 10 are listed below with Rank, Avatar, Name, and Points

#### Scenario: Handles Fewer Users
- GIVEN a list of fewer than 10 users (e.g., 5)
- WHEN `generate_podium` is called
- THEN the image adapts to show only the available users in the list section (e.g., ranks 4 and 5)
