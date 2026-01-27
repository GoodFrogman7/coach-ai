@echo off
echo ===============================================
echo Starting Coach AI Analysis (Pose Only Mode)
echo ===============================================
echo.
echo Ball tracking disabled (no YOLO model found)
echo Running pose analysis...
echo.
python vision/compare.py
echo.
echo ===============================================
echo Analysis Complete!
echo ===============================================
echo.
echo To view results, run: streamlit run streamlit_app.py
pause
