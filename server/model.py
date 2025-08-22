import time
import os
import cv2
import numpy as np
from facenet_pytorch import (
    MTCNN,
    InceptionResnetV1
)
from torchvision.transforms import functional as F

def run(
    video_path_one: str,
    video_path_two: str
) -> int:
    start_time = time.time()
    threshold_face_similarity = 0.99
    threshold_frames_for_deepfake = 15
    mtcnn = MTCNN()
    facenet_model = InceptionResnetV1(pretrained = "vggface2").eval()
    if not os.path.exists(video_path_one) or os.path.getsize(video_path_one) == 0:
        print(f"Error: Input video file {video_path_one} doesn't exist or is empty")
        return 0
    cap = cv2.VideoCapture(video_path_one)
    if not cap.isOpened():
        print(f"Error: OpenCV couldn't open video file {video_path_one}")
        return 0
    frame_count = 0
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0 or fps <= 0:
        print(f"Error: Invalid video properties: width={width}, height={height}, fps={fps}")
        cap.release()
        return 0
    fourcc = cv2.VideoWriter_fourcc(*"H264")
    out = cv2.VideoWriter(video_path_two, fourcc, fps, (width, height))
    deepfake_count = 0
    deep_fake_frame_count = 0
    previous_face_encoding = None
    frames_between_processing = max(1, int(fps / 7))
    resize_dimensions = (80, 80)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frames_between_processing == 0:
            boxes, _ = mtcnn.detect(frame)
            if boxes is not None and len(boxes) > 0:
                box = boxes[0].astype(int)
                box[0] = max(0, box[0])
                box[1] = max(0, box[1])
                box[2] = min(width, box[2])
                box[3] = min(height, box[3])
                if box[2] > box[0] and box[3] > box[1]:
                    face = frame[box[1]:box[3], box[0]:box[2]]
                    if not face.size == 0:
                        face = cv2.resize(face, resize_dimensions)
                        face_tensor = F.to_tensor(face).unsqueeze(0)
                        current_face_encoding = facenet_model(face_tensor).detach().numpy().flatten()
                        if previous_face_encoding is not None:
                            face_similarity = np.dot(current_face_encoding, previous_face_encoding) / (np.linalg.norm(current_face_encoding) * np.linalg.norm(previous_face_encoding))
                            if face_similarity < threshold_face_similarity:
                                deepfake_count += 1
                            else:
                                deepfake_count = 0
                            if deepfake_count > threshold_frames_for_deepfake:
                                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 0, 255), 2)
                                cv2.putText(frame, f"AI Detected - Frame {frame_count}", (10, 30),
                                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                                deep_fake_frame_count +=  1
                            else:
                                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
                                cv2.putText(frame, "Real Frame", (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
                                            cv2.LINE_AA)
                        previous_face_encoding = current_face_encoding
        frame_count +=  1
        out.write(frame)
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Total Execution Time: {execution_time} seconds")
    cap.release()
    out.release()
    if frame_count == 0:
        print("Error: No frames were processed")
        return 0
    total_processed_frames = sum(1 for i in range(frame_count) if i % frames_between_processing == 0)
    if total_processed_frames == 0:
        return 0
    deepfake_percentage = (deep_fake_frame_count / total_processed_frames) * 100
    confidence_factor = min(deepfake_percentage * (deepfake_count / threshold_frames_for_deepfake), 100)
    if frame_count > fps * 30:
        weighted_score = min(deepfake_percentage + confidence_factor * 0.5, 100)
    else:
        weighted_score = min(deepfake_percentage + confidence_factor * 0.3, 100)
    return max(0, min(100, int(weighted_score)))