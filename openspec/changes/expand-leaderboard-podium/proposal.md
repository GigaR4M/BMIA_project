# Expand Leaderboard Podium

## Summary
The monthly/yearly leaderboard image currently only shows the top 3 users. The goal is to expand this image to include a list of the next 7 users (ranks 4-10) below the podium, providing recognition to more active community members.

## Motivation
Ranking among the top 10 is a significant achievement in active communities. Visualizing this achievement encourages more engagement and provides a better overview of the server's most active members.

## Proposed Changes
1.  **Modify `main.py`**: Update `check_monthly_podium` loop to fetch the top 10 users instead of just the top 3.
2.  **Modify `utils/image_generator.py`**:
    *   Increase the canvas height to accommodate the list of 7 additional users.
    *   Implement logic to draw the list rows below the podium.
    *   Each row will display: Rank (`#4` to `#10`), Avatar (circular, smaller than podium), Username, and Points.
