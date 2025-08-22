document.addEventListener("DOMContentLoaded", function() {
  
  const analyzeBtn = document.getElementById("analyze-btn");
  const analyzeAgainBtn = document.getElementById("analyze-again-btn");
  const notVideoPageDiv = document.getElementById("not-youtube");
  const videoContentDiv = document.getElementById("youtube-content");
  const initialStateDiv = document.getElementById("initial-state");
  const loadingStateDiv = document.getElementById("loading-state");
  const resultStateDiv = document.getElementById("result-state");
  const realResultDiv = document.getElementById("real-result");
  const fakeResultDiv = document.getElementById("fake-result");
  const realScoreDiv = document.getElementById("real-score");
  const fakeScoreDiv = document.getElementById("fake-score");
  const fakeExplanationP = document.getElementById("fake-explanation");
  const detailedViewLink = document.getElementById("detailed-view-link");
  const progressIndicator = document.getElementById("progress-indicator");
  const progressStep = document.getElementById("progress-step");

  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    const currentUrl = tabs[0].url;
    let detectedPlatform = null;
    if (currentUrl.includes("youtube.com/watch") || currentUrl.includes("youtu.be/")) {
      detectedPlatform = "youtube";
    } else if ((currentUrl.includes("twitter.com/") || currentUrl.includes("x.com/")) && currentUrl.includes("/status/")) {
      detectedPlatform = "twitter";
    } else if ((currentUrl.includes("facebook.com/") && (currentUrl.includes("/videos/") || currentUrl.includes("/watch"))) || currentUrl.includes("fb.watch")) {
      detectedPlatform = "facebook";
    } else if (currentUrl.includes("reddit.com/r/") && currentUrl.includes("/comments/")) {
      detectedPlatform = "reddit";
    }
    chrome.tabs.sendMessage(tabs[0].id, {action: "checkVideoPage"}, function(response) {
      if (chrome.runtime.lastError) {
        console.log('Content script error:', chrome.runtime.lastError.message);
        if (detectedPlatform) {
          notVideoPageDiv.classList.add("hidden");
          videoContentDiv.classList.remove("hidden");
          const platformName = getPlatformDisplayName(detectedPlatform);
          document.getElementById("platform-name").textContent = platformName;
        } else {
          notVideoPageDiv.classList.remove("hidden");
          videoContentDiv.classList.add("hidden");
          document.getElementById("unsupported-message").textContent = 
            "This extension works on YouTube, Facebook, Twitter, and Reddit video pages.";
        }
        return;
      }
      if (response && response.platform) {
        notVideoPageDiv.classList.add("hidden");
        videoContentDiv.classList.remove("hidden");
        const platformName = getPlatformDisplayName(response.platform);
        document.getElementById("platform-name").textContent = platformName;
      } else if (detectedPlatform) {
        notVideoPageDiv.classList.add("hidden");
        videoContentDiv.classList.remove("hidden");
        const platformName = getPlatformDisplayName(detectedPlatform);
        document.getElementById("platform-name").textContent = platformName;
      } else {
        notVideoPageDiv.classList.remove("hidden");
        videoContentDiv.classList.add("hidden");
        document.getElementById("unsupported-message").textContent = 
          "This extension works on YouTube, Facebook, Twitter, and Reddit video pages.";
      }
    });
  });

  analyzeBtn.addEventListener("click", function() {
    initialStateDiv.classList.add("hidden");
    loadingStateDiv.classList.remove("hidden");
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      const videoUrl = tabs[0].url;
      let urlDetectedPlatform = "Unknown";
      if (videoUrl.includes("youtube.com/watch") || videoUrl.includes("youtu.be/")) {
        urlDetectedPlatform = "YouTube";
      } else if ((videoUrl.includes("twitter.com/") || videoUrl.includes("x.com/")) && videoUrl.includes("/status/")) {
        urlDetectedPlatform = "Twitter/X";
      } else if ((videoUrl.includes("facebook.com/") && (videoUrl.includes("/videos/") || videoUrl.includes("/watch"))) || videoUrl.includes("fb.watch")) {
        urlDetectedPlatform = "Facebook";
      } else if (videoUrl.includes("reddit.com/r/") && videoUrl.includes("/comments/")) {
        urlDetectedPlatform = "Reddit";
      }
      chrome.tabs.sendMessage(tabs[0].id, {action: "checkVideoPage"}, function(response) {
        if (chrome.runtime.lastError) {
          console.log('Content script error:', chrome.runtime.lastError.message);
          displayUrlInfo(urlDetectedPlatform, videoUrl);
          return;
        }
        let platform = urlDetectedPlatform;
        if (response && response.platform) {
          platform = getPlatformDisplayName(response.platform);
        }
        displayUrlInfo(platform, videoUrl);
      });

      function displayUrlInfo(platform, url) {
        const urlInfoDiv = document.createElement("div");
        urlInfoDiv.className = "url-info";
        urlInfoDiv.innerHTML = `
          <p><strong>Platform:</strong> ${platform}</p>
          <p><strong>URL:</strong> ${url}</p>
        `;
        loadingStateDiv.insertBefore(urlInfoDiv, document.querySelector(".progress"));
      }
      
      updateProgress(10, "Downloading video...");
      chrome.runtime.sendMessage(
        {action: "downloadVideo", videoUrl: videoUrl},
        function(response) {
          if (response.error) {
            showError(response.error);
            return;
          }
          updateProgress(40, "Processing video...");
          chrome.runtime.sendMessage(
            {action: "analyzeVideo", videoPath: response.videoPath},
            function(analysisResponse) {
              updateProgress(90, "Finishing analysis...");
              setTimeout(() => {
                updateProgress(100, "Analysis complete!");
                loadingStateDiv.classList.add("hidden");
                resultStateDiv.classList.remove("hidden");
                const fakeScore = analysisResponse.fakeScore;
                const urlInfoDiv = loadingStateDiv.querySelector(".url-info");
                if (urlInfoDiv) {
                  const resultUrlInfo = urlInfoDiv.cloneNode(true);
                  resultStateDiv.insertBefore(resultUrlInfo, resultStateDiv.firstChild);
                }
                if (fakeScore > 50) {
                  realResultDiv.classList.add("hidden");
                  fakeResultDiv.classList.remove("hidden");
                  fakeScoreDiv.textContent = `${fakeScore}% AI-Generated`;
                  fakeExplanationP.textContent = `This video shows signs of facial inconsistency between frames, indicating AI manipulation. ${fakeScore}% of analyzed frames appear to be modified.`;
                  detailedViewLink.href = analysisResponse.detailedViewUrl;
                } else {
                  fakeResultDiv.classList.add("hidden");
                  realResultDiv.classList.remove("hidden");
                  const realScore = 100 - fakeScore;
                  realScoreDiv.textContent = `${realScore}% Real`;
                }
              }, 1000);
            }
          );
        }
      );
    });
  });

  analyzeAgainBtn.addEventListener("click", function() {
    resultStateDiv.classList.add("hidden");
    initialStateDiv.classList.remove("hidden");
  });

  function updateProgress(percent, message) {
    progressIndicator.style.width = `${percent}%`;
    progressStep.textContent = message;
  }

  function showError(message) {
    loadingStateDiv.classList.add("hidden");
    initialStateDiv.classList.remove("hidden");
    let userMessage = message;
    if (message.includes("Server connection failed")) {
      userMessage = "Cannot connect to the analysis server. Please make sure the Python server is running by executing 'python server.py' in the server directory.";
    }
    const errorDiv = document.createElement("div");
    errorDiv.className = "message error";
    errorDiv.innerHTML = `<p><strong>Error:</strong> ${userMessage}</p>`;
    initialStateDiv.insertBefore(errorDiv, analyzeBtn);
    setTimeout(() => {
      if (errorDiv.parentNode === initialStateDiv) {
        initialStateDiv.removeChild(errorDiv);
      }
    }, 10000);
  }

  function getPlatformDisplayName(platform) {
    switch(platform.toLowerCase()) {
      case "youtube": return "YouTube";
      case "facebook": return "Facebook";
      case "twitter": return "Twitter/X";
      case "reddit": return "Reddit";
      default: return platform || "Unknown";
    }
  }

});