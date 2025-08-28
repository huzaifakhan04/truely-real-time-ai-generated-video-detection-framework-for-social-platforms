# Truely - Real-Time AI-Generated Video Detection Framework for Social Platforms:

A real-time browser extension that detects AI-generated or manipulated videos on social platforms and cross-verifies audio content against trusted sources using agentic AI web search.

## Overview:

This application uses computer vision, facial recognition, and audio analysis to identify potentially misleading content. The visual analysis identifies inconsistencies in facial features across video frames, which are common indicators of AI-generated or deepfake content.

Simultaneously, the audio analysis extracts speech, conducts real-time web searches using an AI agent to verify claims against credible sources, and provides fact-checking results. The system delivers comprehensive confidence scores and visual indicators to help users identify potentially fake or misleading videos.

## Features:

- **Browser Integration**: Chrome extension that works directly with YouTube, Facebook, Twitter/X, and Reddit videos.
- **Video Analysis**: Process videos from popular platforms or local uploads.
- **Facial Consistency Detection**: Tracks changes in facial features between frames.
- **Real-Time Visualization**: Highlights suspicious frames with red bounding boxes.
- **Audio Transcription and Analysis**: Extracts speech from videos for fact-checking.
- **AI-Powered Web Search**: Intelligent agent searches and analyzes information from credible online sources.
- **Real-Time Web Search Integration**: Verifies claims against credible online sources.
- **Fact-Checking**: Analyzes transcribed content for factual accuracy.
- **Confidence Score**: Provides a percentage indicating likelihood of AI manipulation.
- **Detailed Reports**: View comprehensive analysis with visual indicators and metrics.
- **User Authentication**: Secure login and registration system with email confirmation.
- **Credibility Metrics**: Analysis includes visual consistency, audio factuality, anomalies, and overall confidence metrics.
- **Cross-Platform Analysis**: Works across various social media platforms.

## How It Works:

1. **Visual Analysis**:
   - The system extracts facial features from each frame using MTCNN face detection.
   - FaceNet model generates facial encodings for comparison between consecutive frames.
   - Sudden changes in facial features beyond a threshold are flagged as suspicious.
   - Videos with multiple suspicious frames are classified as likely AI-generated.

2. **Audio Analysis**:
   - Speech is transcribed from the video's audio track.
   - Key claims and statements are extracted from the transcript.
   - An AI agent conducts real-time web searches to find credible sources related to these claims.
   - AI models compare the claims against verified information from reputable sources.
   - Factuality scores are generated based on the verification results.

3. Results from both analyses are combined and displayed with visual indicators and confidence scores.

## Installation:

### Prerequisites:

- Python 3.8+
- pip package manager
- Google Chrome browser (for extension)
- Supabase account for authentication (free tier works)
- Tavily API
- Gemini Developer API
- GroqCloud API

### Setup:

1. Clone the repository:
   ```bash
   git clone https://github.com/huzaifakhan04/truely-real-time-ai-generated-video-detection-framework-for-social-platforms.git
   cd ai-generated-video-detection-framework-for-social-platforms
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download the shape predictor model:
   - Ensure the `server/models/shape_predictor_68_face_landmarks.dat` file is present in the project directory.
   - If missing, download from [dlib's model repository](http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2).

## Server Configuration:

1. Create a `.env` file in the root directory with the following variables:
   ```
   TAVILY_API_KEY=your_tavily_api_key
   GEMINI_API_KEY=your_gemini_api_key
   GROQ_API_KEY=your_groq_api_key
   ```

   These API keys enable:
   - **Tavily:** For AI-powered real-time web search functionality.
   - **Gemini:** For AI-powered content analysis.
   - **GroqCloud:** For high-speed speech transcription.

2. Navigate to the server directory:
   ```bash
   cd server
   ```

3. Start the server:
   ```bash
   python server.py
   ```

The server will run on `http://localhost:5001` by default.

## Chrome Extension:

The primary interface for this tool is a Chrome extension for quick video analysis directly from your browser.

### Extension Configuration:

1. Create a `config.js` file in the `extension` directory with your Supabase credentials:
   ```javascript
   const CONFIG = {
     SUPABASE_URL: "your_supabase_project_url",
     SUPABASE_KEY: "your_supabase_anon_key"
   };

   if (typeof self !== "undefined") {
     self.CONFIG = CONFIG;
   }

   if (typeof window !== "undefined") {
     window.CONFIG = CONFIG;
   }
   ```

2. To get these credentials:
   - Create a free Supabase account at [supabase.com](https://supabase.com).
   - Create a new project.
   - Enable email authentication in the Authentication settings.
   - Copy your project URL and anon/public key from the API settings.

### Installing the Extension:

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable "Developer mode" using the toggle in the top-right corner.
3. Click "Load unpacked" and select the `extension` folder from this project.
4. The extension icon should appear in your browser toolbar.

### Using the Extension:

1. Click the extension icon in your browser toolbar.
2. Register for an account or sign in if you already have one.
3. Navigate to a video page on YouTube, Twitter/X, Facebook, or Reddit.
4. Click "Analyze Video".
5. The extension will show a progress indicator as it:
   - Downloads the video and audio.
   - Processes video frames and extracts speech.
   - Analyzes facial features.
   - Transcribes and fact-checks audio content.
   - Uses an AI agent to search the web for verification of claims.
   - Evaluates overall content credibility.
6. View the analysis results with:
   - A confidence score percentage.
   - Visual indicators for real vs. fake content.
   - Consistency, anomaly, and confidence metrics.
   - Factual accuracy assessment of audio content.
   - References to credible sources supporting or refuting claims.
7. For detailed analysis, click "View Detailed Analysis" to see the full report.

## Authentication Features:

- **User Registration**: Create an account with email and password.
- **Email Verification**: Confirm your account through email.
- **Secure Login**: Access the extension features after authentication.
- **Session Management**: Automatic token refresh and session persistence.
- **Logout Functionality**: Securely sign out from the extension.

## Backend API:

The backend is built with FastAPI and provides the following endpoints:

- `/download-video`: Downloads videos from supported platforms with quality options.
- `/download-audio`: Downloads and extracts audio from videos in various formats.
- `/download-combined`: Downloads both video and audio in a single request.
- `/analyze-video`: Processes videos to detect AI-generated visual manipulation.
- `/analyze-audio`: Analyzes audio content for factual accuracy using AI and web search.
- `/analyze-combined`: Performs both video and audio analysis together.
- `/view/{result_id}`: Shows detailed analysis results with a user-friendly interface.
- `/video/{result_id}`: Serves processed videos with detection highlights.
- `/audio/{result_id}`: Retrieves extracted audio for a specific analysis result.

## Technical Implementation:

The detection system uses:
- **OpenCV**: For video processing and frame manipulation.
- **FaceNet PyTorch**: For facial feature extraction and encoding.
- **MTCNN**: For accurate face detection in video frames.
- **FastAPI**: For the backend server.
- **Chrome Extension APIs**: For browser integration.
- **Supabase**: For authentication and user management.
- **Tavily API**: For AI-powered real-time web search and information retrieval.
- **Gemini Developer API**: For natural language understanding and fact verification.
- **GroqCloud API**: For high-performance speech transcription.

## UI Components:

- **Progress Indicators**: Real-time feedback during video analysis.
- **Donut Charts**: Visual representation of confidence scores.
- **Color Coding**: Green for real content, red for potentially fake content.
- **Responsive Design**: Clean interface that adapts to different content types.
- **Fact Check Cards**: Display verified information with source references found by the AI agent.

## Limitations:

- Works best with videos containing clear facial features.
- May produce false positives with rapidly changing lighting conditions.
- Performance depends on video resolution and quality.
- Audio analysis requires clear speech for accurate transcription.
- AI agent fact-checking depends on availability of relevant information online.
- Processing time increases with video length.
- Requires local server setup.
- Internet connection needed for authentication and AI web search.