import os
import tempfile
import uuid
import subprocess
import threading
import time
import cv2
from model import run
from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template
)
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
analysis_results = {}

def cleanup_old_results():
    while True:
        current_time = time.time()
        to_remove = []
        for result_id, result in analysis_results.items():
            if current_time - result["timestamp"] > 3600:
                try:
                    os.unlink(result["output_path"])
                except:
                    pass
                to_remove.append(result_id)
        for result_id in to_remove:
            del analysis_results[result_id]
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_results, daemon=True)
cleanup_thread.start()

@app.route("/view/<result_id>", methods=["GET"])
def view_result(result_id):
    if result_id not in analysis_results:
        return "Result not found or has expired", 404
    return render_template("view_result.html", 
                          fake_score=analysis_results[result_id]["fake_score"],
                          video_url=f"/video/{result_id}")

@app.route("/video/<result_id>", methods=["GET"])
def get_video(result_id):
    if result_id not in analysis_results:
        return "Video not found or has expired", 404
    return send_file(analysis_results[result_id]["output_path"], mimetype="video/mp4")

@app.route("/download", methods=["GET"])
def download_video():
    video_id = request.args.get("videoId")
    _ = request.args.get("quality", "360p")
    if not video_id:
        return jsonify({"error": "No video ID provided"}), 400
    try:
        timestamp = int(time.time())
        video_path = os.path.join(tempfile.gettempdir(), f"ai_detector_video_{video_id}_{timestamp}.mp4")
        print(f"Attempting to download video {video_id} to {video_path}")
        url = f"https://www.youtube.com/watch?v={video_id}"
        cmd = [
            "yt-dlp",
            "--verbose",
            "--force-overwrites",
            "--no-cache-dir",
            "--no-continue",
            "-f", "best[height<=360]",
            "--merge-output-format", "mp4",
            "-o", video_path,
            url
        ]
        print(f'Running command: {" ".join(cmd)}')
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Download output: {result.stdout}")
        if not os.path.exists(video_path):
            print(f"Error: File {video_path} does not exist")
            return jsonify({"error": "Failed to download video: File not created"}), 500
        if os.path.getsize(video_path) == 0:
            print(f"Error: File {video_path} is empty (0 bytes)")
            return jsonify({"error": "Failed to download video: Empty file created"}), 500
        file_size = os.path.getsize(video_path)
        print(f"Downloaded file size: {file_size} bytes")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f'Error: OpenCV couldn\'t open {video_path}')
            os.unlink(video_path)
            return jsonify({"error": "Downloaded video is corrupted or in an unsupported format"}), 500
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"Video info: {width}x{height}, {fps} fps, {frame_count} frames")
        cap.release()
        return jsonify({"videoPath": video_path})
    except subprocess.CalledProcessError as e:
        print(f"Download command error: {e.stdout} {e.stderr}")
        return jsonify({"error": f"Failed to download video: {e.stderr}"}), 500
    except Exception as e:
        print(f"Download error: {str(e)}")
        return jsonify({"error": f"Failed to download video: {str(e)}"}), 500

@app.route("/analyze", methods=["POST"])
def analyze_video():
    data = request.json
    video_path = data.get("videoPath")
    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": "Invalid video path"}), 400
    try:
        output_path = video_path.replace(".mp4", "_output.mp4")
        fake_score = run(video_path, output_path)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return jsonify({"error": "Video analysis failed: No output video generated"}), 500
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "output_path": output_path,
            "fake_score": fake_score,
            "timestamp": time.time()
        }
        def delete_input_video():
            time.sleep(60)
            try:
                os.unlink(video_path)
            except:
                pass
        delete_thread = threading.Thread(target=delete_input_video)
        delete_thread.start()
        return jsonify({
            "fakeScore": fake_score,
            "resultId": result_id
        })
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return jsonify({"error": f"Failed to analyze video: {str(e)}"}), 500
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)