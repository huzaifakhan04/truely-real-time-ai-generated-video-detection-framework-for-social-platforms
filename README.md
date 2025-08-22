# AI-Generated Video Detection Tool:

An advanced tool that analyzes videos to detect AI-generated or manipulated content by tracking facial consistency between frames.

## Overview

This application uses computer vision and facial recognition to identify inconsistencies in facial features across video frames, which are common indicators of AI-generated or deepfake content. The system provides a confidence score and visual indicators to help users identify potentially fake videos.

## Features

- **Video Analysis**: Upload and process videos in multiple formats (MP4, AVI, MOV, MKV).
- **Facial Consistency Detection**: Tracks changes in facial features between frames.
- **Real-time Visualization**: Highlights suspicious frames with red bounding boxes.
- **Confidence Score**: Provides a percentage indicating likelihood of AI manipulation.
- **User-friendly Interface**: Built with Streamlit for easy interaction.

## How It Works

1. The system extracts facial features from each frame using MTCNN face detection.
2. FaceNet model generates facial encodings for comparison between consecutive frames.
3. Sudden changes in facial features beyond a threshold are flagged as suspicious.
4. Videos with multiple suspicious frames are classified as likely AI-generated.
5. Results are displayed with visual indicators and confidence scores.

## Installation

### Prerequisites

- Python 3.8+
- pip package manager

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/unesco-youth-hackathon-2025/ai-generated-video-detection-tool.git
   cd ai-generated-video-detection-tool
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download the shape predictor model:
   - Ensure the `models/shape_predictor_68_face_landmarks.dat` file is present in the project directory.
   - If missing, download from [dlib's model repository](http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2).

## Usage

1. Run the application:
   ```bash
   streamlit run app.py
   ```

2. Access the web interface (typically at http://localhost:8501).

3. Upload a video file for analysis.

4. Review the detection results:
   - Green boxes indicate consistent facial features (likely real).
   - Red boxes highlight inconsistent facial features (possibly AI-generated).
   - Check the confidence score for overall assessment.

## Chrome Extension

The project includes a Chrome extension for quick video analysis directly from your browser.

### Installing the Extension

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable "Developer mode" using the toggle in the top-right corner.
3. Click "Load unpacked" and select the `extension` folder from this project.
4. The extension icon should appear in your browser toolbar.

### Running the Extension Server

The extension requires a local server to process videos:

1. Navigate to the extension server directory:
   ```bash
   cd extension/server
   ```

2. Install server-specific dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:
   ```bash
   python server.py
   ```

### Using the Extension

1. Click the extension icon in your browser toolbar.
2. Select a video to analyze (supports YouTube, Twitter, Facebook, and Reddit).
3. Click "Analyze Video".
4. View the analysis results directly in the extension popup.
5. For detailed analysis, you can view the full report in a new tab.

## Technical Implementation

The detection system uses:
- **OpenCV**: For video processing and frame manipulation.
- **FaceNet PyTorch**: For facial feature extraction and encoding.
- **MTCNN**: For accurate face detection in video frames.
- **Streamlit**: For the user interface.

## Limitations

- Works best with videos containing clear facial features.
- May produce false positives with rapidly changing lighting conditions.
- Performance depends on video resolution and quality.
- Processing time increases with video length.