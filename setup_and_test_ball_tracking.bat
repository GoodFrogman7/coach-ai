@echo off
echo ===============================================
echo Ball Tracking Setup and Test
echo ===============================================
echo.
echo Step 1: Installing ultralytics (YOLO)...
pip install ultralytics
echo.
echo Step 2: Downloading YOLOv8 nano model...
python -c "from ultralytics import YOLO; print('Downloading YOLOv8n model...'); model = YOLO('yolov8n.pt'); print('Saving to models/best.pt...'); import os; os.makedirs('models', exist_ok=True); model.save('models/best.pt'); print('Model ready!')"
echo.
echo Step 3: Running analysis with BALL TRACKING...
python vision/compare.py
echo.
echo ===============================================
echo Analysis Complete with Ball Tracking!
echo ===============================================
echo.
echo Check outputs folder for:
echo - report.md (enhanced with ball stats)
echo - overlay_broadcast.mp4 (with ball tracking)
echo - heatmaps/ (court zones and speed charts)
echo.
echo To view dashboard: streamlit run streamlit_app.py
pause
