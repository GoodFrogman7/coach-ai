# YOLO Model Directory

This directory should contain the YOLOv8 ball detection model weights.

## Option 1: Use Pre-trained Sports Ball Model (Quickest)

Download a pre-trained YOLO model for sports ball detection:

```bash
# Download YOLOv8 nano model (lightweight)
pip install ultralytics
python -c "from ultralytics import YOLO; model = YOLO('yolov8n.pt'); model.save('models/best.pt')"
```

This will use the COCO-trained model which includes a "sports ball" class (class 32).

## Option 2: Fine-tune for Tennis Balls

1. **Download tennis ball dataset** from Roboflow Universe:
   - Search for "tennis ball detection" on https://universe.roboflow.com/
   - Export in YOLOv8 format
   
2. **Train the model**:
```bash
yolo detect train data=tennis_dataset/data.yaml model=yolov8n.pt epochs=50 imgsz=640
cp runs/detect/train/weights/best.pt models/best.pt
```

## Option 3: Use Publicly Available Tennis Ball Model

Search GitHub or Roboflow for pre-trained tennis ball detection models:
- https://github.com/search?q=tennis+ball+detection+yolo
- https://universe.roboflow.com/search?q=tennis

## Expected File

The system expects: `models/best.pt`

## Fallback Behavior

If `models/best.pt` is not found, the system will gracefully skip ball tracking and only perform pose analysis (existing functionality preserved).

## Model Performance Notes

- **YOLOv8n** (nano): Fastest, ~80-90% accuracy, good for real-time
- **YOLOv8s** (small): Balanced, ~85-92% accuracy
- **YOLOv8m** (medium): Slower, ~90-95% accuracy, best for quality

For tennis analysis, YOLOv8n is usually sufficient.
