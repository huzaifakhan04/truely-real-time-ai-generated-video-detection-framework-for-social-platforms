const SERVER_URL = "http://localhost:5001";
let ENV_VARS = {
  SUPABASE_URL: "",
  SUPABASE_KEY: ""
};

importScripts("config.js");

function loadEnvVars() {
  if (self.CONFIG) {
    Object.keys(ENV_VARS).forEach(key => {
      if (self.CONFIG[key]) {
        ENV_VARS[key] = self.CONFIG[key];
      }
    });
    console.log("Environment variables loaded from config.js");
  } else {
    console.warn("No configuration values found in config.js");
  }
}

chrome.runtime.onInstalled.addListener(function() {
  loadEnvVars();
  checkAuthentication();
});

async function checkAuthentication() {
  chrome.storage.local.get(["session"], function(result) {
    if (!result.session) {
      console.log("No authentication session found");
      return;
    }
    const expiresAt = result.session.expires_at * 1000;
    if (Date.now() > expiresAt) {
      console.log("Session expired, redirecting to login");
      chrome.storage.local.remove(["session"]);
    } else {
      console.log("User is authenticated");
    }
  });
}

chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === "checkAuth") {
    chrome.storage.local.get(["session"], function(result) {
      sendResponse({isAuthenticated: !!result.session});
    });
    return true;
  }
  if (request.action === "logout") {
    try {
      chrome.storage.local.remove(["session"], function() {
        sendResponse({success: true});
      });
    } catch(e) {
      console.error("Error during logout:", e);
      chrome.storage.local.remove(["session"], function() {
        sendResponse({success: true});
      });
    }
    return true;
  }
  if (request.action === "downloadVideo") {
    if (request.videoId) {
      downloadYoutubeVideo(request.videoId)
        .then(videoPath => sendResponse({videoPath: videoPath}))
        .catch(error => sendResponse({error: error.message}));
    } else if (request.videoUrl) {
      downloadVideoFromUrl(request.videoUrl)
        .then(videoPath => sendResponse({videoPath: videoPath}))
        .catch(error => sendResponse({error: error.message}));
    } else {
      sendResponse({error: "No video ID or URL provided"});
    }
    return true;
  }
  if (request.action === "downloadCombined") {
    if (request.videoUrl) {
      downloadCombined(request.videoUrl)
        .then(paths => sendResponse(paths))
        .catch(error => sendResponse({error: error.message}));
    } else {
      sendResponse({error: "No video URL provided"});
    }
    return true;
  }
  if (request.action === "analyzeVideo") {
    analyzeVideo(request.videoPath)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({error: error.message}));
    return true;
  }
  if (request.action === "analyzeCombined") {
    analyzeCombined(request.videoPath, request.audioPath)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({error: error.message}));
    return true;
  }
  if (request.action === "getEnvVars") {
    sendResponse({
      SUPABASE_URL: ENV_VARS.SUPABASE_URL,
      SUPABASE_KEY: ENV_VARS.SUPABASE_KEY
    });
    return true;
  }
});

async function downloadYoutubeVideo(videoId) {
  try {
    console.log("Attempting to connect to server at:", SERVER_URL);
    const response = await fetch(`${SERVER_URL}/download?videoId=${videoId}&quality=360p`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to download the video: Server responded with status ${response.status}. ${errorText}`);
    }
    const data = await response.json();
    return data.videoPath;
  } catch (error) {
    console.error("Error downloading video:", error);
    if (error.message.includes("Failed to fetch")) {
      throw new Error(`Server connection failed. Make sure the Python server is running at ${SERVER_URL}`);
    }
    throw error;
  }
}

async function downloadVideoFromUrl(videoUrl) {
  try {
    console.log("Attempting to download video from URL:", videoUrl);
    let platform = "unknown";
    if (videoUrl.includes("youtube.com") || videoUrl.includes("youtu.be")) {
      platform = "YouTube";
    } else if (videoUrl.includes("twitter.com") || videoUrl.includes("x.com")) {
      platform = "Twitter/X";
    } else if (videoUrl.includes("facebook.com") || videoUrl.includes("fb.watch")) {
      platform = "Facebook";
    } else if (videoUrl.includes("reddit.com") || videoUrl.includes("redd.it")) {
      platform = "Reddit";
    }
    console.log(`Detected platform: ${platform} - URL: ${videoUrl}`);
    const isSupported = validateVideoUrl(videoUrl);
    if (!isSupported) {
      console.warn("URL may not be a supported video page:", videoUrl);
    }
    const response = await fetch(`${SERVER_URL}/download?videoUrl=${encodeURIComponent(videoUrl)}&quality=360p`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to download the video: Server responded with status ${response.status}. ${errorText}`);
    }
    const data = await response.json();
    return data.videoPath;
  } catch (error) {
    console.error("Error downloading video:", error);
    if (error.message.includes("Failed to fetch")) {
      throw new Error(`Server connection failed. Make sure the Python server is running at ${SERVER_URL}`);
    }
    throw error;
  }
}

async function analyzeVideo(videoPath) {
  try {
    const response = await fetch(`${SERVER_URL}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({videoPath: videoPath})
    });
    if (!response.ok) {
      throw new Error("Failed to analyze the video");
    }
    const data = await response.json();
    return {
      fakeScore: data.fakeScore,
      detailedViewUrl: `${SERVER_URL}/view/${data.resultId}`
    };
  } catch (error) {
    console.error("Error analyzing video:", error);
    throw error;
  }
}

async function analyzeCombined(videoPath, audioPath = null) {
  try {
    const requestBody = audioPath 
      ? { videoPath, audioPath }
      : { videoPath };
    
    const response = await fetch(`${SERVER_URL}/analyze-combined`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      throw new Error("Failed to analyze the video and audio");
    }
    
    const data = await response.json();
    return {
      fakeScore: data.fakeScore,
      newsScore: data.newsScore || 0,
      newsSummary: data.newsSummary || "No audio analysis available",
      verdict: data.verdict || "uncertain",
      confidence: data.confidence || 0,
      evidence: data.evidence || [],
      detailedViewUrl: `${SERVER_URL}/view/${data.resultId}`
    };
  } catch (error) {
    console.error("Error analyzing video and audio:", error);
    throw error;
  }
}

async function downloadCombined(videoUrl) {
  try {
    console.log("Attempting to download video and audio from URL:", videoUrl);
    const response = await fetch(`${SERVER_URL}/download-combined?video_url=${encodeURIComponent(videoUrl)}&audio_format=mp3&quality=360p`);
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to download: Server responded with status ${response.status}. ${errorText}`);
    }
    const data = await response.json();
    return {
      videoPath: data.videoPath,
      audioPath: data.audioPath
    };
  } catch (error) {
    console.error("Error downloading combined video and audio:", error);
    if (error.message.includes("Failed to fetch")) {
      throw new Error(`Server connection failed. Make sure the Python server is running at ${SERVER_URL}`);
    }
    throw error;
  }
}

function validateVideoUrl(url) {
  if (url.includes("youtube.com/watch") && url.includes("v=")) {
    return true;
  }
  if (url.includes("youtu.be/")) {
    return true;
  }
  if ((url.includes("twitter.com/") || url.includes("x.com/")) && url.includes("/status/")) {
    return true;
  }
  if (url.includes("facebook.com/watch")) {
    return true;
  }
  if (url.includes("facebook.com/") && url.includes("/videos/")) {
    return true;
  }
  if (url.includes("fb.watch/")) {
    return true;
  }
  if (url.includes("reddit.com/r/") && url.includes("/comments/")) {
    return true;
  }
  if (url.includes("redd.it/")) {
    return true;
  }
  return false;
}