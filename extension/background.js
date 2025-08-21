const SERVER_URL = "http://localhost:5001";

chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === "downloadVideo") {
    downloadYoutubeVideo(request.videoId)
      .then(videoPath => sendResponse({videoPath: videoPath}))
      .catch(error => sendResponse({error: error.message}));
    return true;
  }
  if (request.action === "analyzeVideo") {
    analyzeVideo(request.videoPath)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({error: error.message}));
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