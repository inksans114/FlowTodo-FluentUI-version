"""CPU vision adapters. Input frames and OCR text stay in memory on this device."""
from __future__ import annotations

from pathlib import Path

from supervision_policy import eye_direction, held_phone, upper_body

MODEL_DIR = Path(__file__).resolve().parent / "supervision-models"
MODEL_FILES = ("pose_landmarker_lite.task", "efficientdet_lite0.tflite", "hand_landmarker.task", "face_landmarker.task")


class CameraDetector:
    def __init__(self, directory=MODEL_DIR):
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        self.mp = mp
        self.pose = None
        self.objects = None
        self.hands = self.face = None
        try:
            self.pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(directory / MODEL_FILES[0])),
                running_mode=vision.RunningMode.VIDEO, num_poses=1,
                min_pose_detection_confidence=.55, min_pose_presence_confidence=.55))
            self.objects = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(directory / MODEL_FILES[1])),
                running_mode=vision.RunningMode.VIDEO, max_results=8, score_threshold=.5,
                category_allowlist=["person", "cell phone"]))
            self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(directory / MODEL_FILES[2])),
                running_mode=vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.6, min_hand_presence_confidence=.6))
            self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(directory / MODEL_FILES[3])),
                running_mode=vision.RunningMode.VIDEO, num_faces=1,
                min_face_detection_confidence=.6, min_face_presence_confidence=.6))
        except Exception:
            self.close()
            raise
        self._timestamp = -1

    def detect(self, rgb, timestamp):
        import numpy as np
        timestamp = max(self._timestamp + 1, int(timestamp))
        self._timestamp = timestamp
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        poses = self.pose.detect_for_video(image, timestamp)
        detections = self.objects.detect_for_video(image, timestamp)
        hands = self.hands.detect_for_video(image, timestamp).hand_landmarks
        faces = self.face.detect_for_video(image, timestamp).face_landmarks
        h, w = rgb.shape[:2]
        boxes = []
        for detection in detections.detections:
            category = detection.categories[0]
            b = detection.bounding_box
            boxes.append({"label": category.category_name, "score": round(category.score, 3),
                          "x": max(0, b.origin_x / w), "y": max(0, b.origin_y / h),
                          "w": b.width / w, "h": b.height / h})
        landmarks = [{"x": p.x, "y": p.y, "visibility": p.visibility or 0}
                     for p in (poses.pose_landmarks[0] if poses.pose_landmarks else [])]
        tracked, points = upper_body(landmarks)
        face = [{"x": p.x, "y": p.y} for p in (faces[0] if faces else [])]
        if face:
            points = [p for p in points if p["index"] > 10]
            points.extend({"index": 3000 + i, **face[i]} for i in (33, 133, 159, 145, 362, 263, 386, 374, 468, 473) if i < len(face))
        for number, hand in enumerate(hands):
            points.extend({"index": 100 + number * 21 + i, "x": p.x, "y": p.y} for i, p in enumerate(hand))
        wrists = list(landmarks)
        if len(wrists) < 17:
            wrists = [{"x": 0, "y": 0, "visibility": 0} for _ in range(17)]
        for i, hand in enumerate(hands[:2]):
            wrists[15 + i] = {"x": hand[0].x, "y": hand[0].y, "visibility": 1}
        present = tracked or bool(hands) or bool(face) or any(b["label"] == "person" and b["score"] >= .6 for b in boxes)
        observable = float(rgb.mean()) > 22 and float(rgb.std()) > 8
        features = {"handsVisible": float(bool(hands)), "faceVisible": float(bool(face)),
                    "phoneVisible": float(any(b["label"] == "cell phone" for b in boxes)),
                    "phoneNearHand": float(held_phone(boxes, wrists))}
        for i, name in ((0, "head"), (11, "leftShoulder"), (12, "rightShoulder"), (15, "leftWrist"), (16, "rightWrist")):
            if i < len(landmarks) and landmarks[i]["visibility"] >= .6:
                features[name + "X"] = landmarks[i]["x"]
                features[name + "Y"] = landmarks[i]["y"]
        if hands:
            features["handsCenterX"] = float(np.mean([p.x for hand in hands for p in hand]))
            features["handsCenterY"] = float(np.mean([p.y for hand in hands for p in hand]))
            features["handsSpread"] = float(np.std([p.x for hand in hands for p in hand]))
        if face:
            features["eyesX"] = (face[468]["x"] + face[473]["x"]) / 2
            features["eyesY"] = (face[468]["y"] + face[473]["y"]) / 2
            features["faceTilt"] = (face[263]["y"] - face[33]["y"]) / max(.03, abs(face[263]["x"] - face[33]["x"]))
        return {"present": present, "upperBody": tracked, "points": points, "boxes": boxes,
                "heldPhone": held_phone(boxes, wrists), "phoneVisible": any(b["label"] == "cell phone" for b in boxes),
                "handCount": len(hands), "eyeDirection": eye_direction(face),
                "observable": observable, "features": features}

    def close(self):
        for model in (self.pose, self.objects, self.hands, self.face):
            if model is not None:
                model.close()
        self.pose = self.objects = self.hands = self.face = None


class ScreenDetector:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        # Explicit local package models; never download models at runtime.
        import rapidocr_onnxruntime
        root = Path(rapidocr_onnxruntime.__file__).parent / "models"
        if not root.is_dir():
            raise RuntimeError("屏幕文字识别模型缺失，请检查安装包。")
        self.ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)

    def detect(self, rgb):
        import numpy as np
        # RapidOCR expects BGR, unlike the camera adapter.
        result, _ = self.ocr(np.ascontiguousarray(rgb[:, :, ::-1]))
        return "\n".join(str(row[1]) for row in (result or []) if float(row[2]) >= .65)[:6000]
