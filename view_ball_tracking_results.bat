@echo off
echo ===============================================
echo Ball Tracking Results Viewer
echo ===============================================
echo.
echo Opening complete session: 2026-01-26_17-14-19
echo.
echo 1. Opening report...
start notepad "outputs\2026-01-26_17-14-19\report.md"
echo.
echo 2. Opening heatmaps folder...
start explorer "outputs\2026-01-26_17-14-19\heatmaps"
echo.
echo 3. Opening broadcast overlay video...
start "" "outputs\2026-01-26_17-14-19\overlay_broadcast.mp4"
echo.
echo ===============================================
echo All files opened!
echo ===============================================
echo.
echo Check the report for "Ball & Rally Intelligence" section
echo Look for heatmaps: court_zones.png and speed_distribution.png
echo Watch overlay_broadcast.mp4 for ball tracking visualization
echo.
pause
