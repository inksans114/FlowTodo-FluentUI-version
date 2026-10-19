# Local supervision models

Models are obtained from Google's official MediaPipe model distribution using
`tools/prepare_supervision_models.py`. `manifest.json` records the exact versioned
URLs, sizes and SHA-256 checksums. No camera frames or screen captures are sent
to Google. Model files are included with the release; setup is the only download.

- Pose Landmarker Lite: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- EfficientDet Lite0 (COCO person / cell phone labels): https://developers.google.com/edge/mediapipe/solutions/vision/object_detector
- Hand Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
- Face Landmarker (eye/iris landmarks, approximate direction only): https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
- MediaPipe code: Apache-2.0, https://github.com/google-ai-edge/mediapipe
- Screen OCR: RapidOCR (Apache-2.0) with its packaged PaddleOCR ONNX models:
  https://github.com/RapidAI/RapidOCR

Retain the upstream package licenses and this notice when distributing builds.
These pretrained models detect visible objects and body landmarks; they cannot
certify that a user is studying, using a keyboard, or writing correct code.
