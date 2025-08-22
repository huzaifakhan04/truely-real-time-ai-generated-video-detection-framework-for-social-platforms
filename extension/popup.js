document.addEventListener("DOMContentLoaded", function() {

  chrome.storage.local.get(["session"], function(result) {
    if (!result.session) {
      window.location.href = "auth.html";
      return;
    }
    const expiresAt = result.session.expires_at * 1000;
    if (Date.now() > expiresAt) {
      chrome.storage.local.remove(['session'], function() {
        window.location.href = "auth.html";
      });
      return;
    }
    initializePopup();
  });

  function initializePopup() {
    
    const aboutLink = document.getElementById("about-link");
    const footer = document.querySelector("footer");
    const logoutLink = document.createElement("a");
    logoutLink.href = "#";
    logoutLink.className = "footer-link focus-visible";
    logoutLink.id = "logout-link";
    logoutLink.textContent = "Logout";
    footer.querySelector(".footer-links").appendChild(logoutLink);

    logoutLink.addEventListener("click", function(e) {
      e.preventDefault();
      chrome.runtime.sendMessage({action: "logout"}, function(response) {
        if (response.success) {
          window.location.href = "auth.html";
        }
      });
    });

    const analyzeBtn = document.getElementById("analyze-btn");
    const analyzeAgainBtn = document.getElementById("analyze-again-btn");
    const notVideoPageDiv = document.getElementById("not-youtube");
    const videoContentDiv = document.getElementById("youtube-content");
    const initialStateDiv = document.getElementById("initial-state");
    const loadingStateDiv = document.getElementById("loading-state");
    const resultStateDiv = document.getElementById("result-state");
    const realResultDiv = document.getElementById("real-result");
    const fakeResultDiv = document.getElementById("fake-result");
    const realScoreElem = document.getElementById("real-score");
    const fakeScoreElem = document.getElementById("fake-score");
    const fakeExplanationP = document.getElementById("fake-explanation");
    const detailedViewLink = document.getElementById("detailed-view-link");
    const progressIndicator = document.getElementById("progress-indicator");
    const progressStep = document.getElementById("progress-step");
    const progressPercentage = document.querySelector(".progress-percentage");
    const errorContainer = document.getElementById("error-container");
    const realProgress = document.getElementById("real-progress");
    const fakeProgress = document.getElementById("fake-progress");

    initDonutCharts();

    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      const currentUrl = tabs[0].url;
      let detectedPlatform = detectPlatformFromUrl(currentUrl);
      chrome.tabs.sendMessage(tabs[0].id, {action: "checkVideoPage"}, function(response) {
        if (chrome.runtime.lastError) {
          console.log("Content script error:", chrome.runtime.lastError.message);
          handlePlatformDetection(detectedPlatform, currentUrl);
          return;
        }
        if (response && response.platform) {
          handlePlatformDetection(response.platform, currentUrl);
        } else {
          handlePlatformDetection(detectedPlatform, currentUrl);
        }
      });
    });

    analyzeBtn.addEventListener("click", function() {
      initialStateDiv.classList.add("hidden");
      loadingStateDiv.classList.remove("hidden");
      errorContainer.innerHTML = "";
      chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        const videoUrl = tabs[0].url;
        const urlDetectedPlatform = detectPlatformFromUrl(videoUrl);
        chrome.tabs.sendMessage(tabs[0].id, {action: "checkVideoPage"}, function(response) {
          const platform = (response && response.platform) ? 
                            getPlatformDisplayName(response.platform) : 
                            getPlatformDisplayName(urlDetectedPlatform);
          displayUrlInfo(platform, videoUrl);
          startAnalysis(videoUrl);
        });
      });
    });

    analyzeAgainBtn.addEventListener("click", function() {
      resultStateDiv.classList.add("hidden");
      initialStateDiv.classList.remove("hidden");
    });

    aboutLink.addEventListener("click", function(e) {
      e.preventDefault();
      chrome.tabs.create({
        url: "https://github.com/unesco-youth-hackathon-2025/ai-generated-video-detection-tool/blob/main/README.md"
      });
    });

    function startAnalysis(videoUrl) {
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
              if (analysisResponse.error) {
                showError(analysisResponse.error);
                return;
              }
              updateProgress(70, "Analyzing facial features...");
              setTimeout(() => {
                updateProgress(90, "Finalizing results...");
                setTimeout(() => {
                  updateProgress(100, "Analysis complete!");
                  
                  setTimeout(() => {
                    displayResults(analysisResponse);
                  }, 500);
                }, 500);
              }, 800);
            }
          );
        }
      );
    }

    function displayResults(analysisResponse) {
      loadingStateDiv.classList.add("hidden");
      resultStateDiv.classList.remove("hidden");
      const fakeScore = analysisResponse.fakeScore;
      const realScore = 100 - fakeScore;
      const urlInfoDiv = loadingStateDiv.querySelector(".url-info");
      if (urlInfoDiv) {
        const resultUrlInfo = urlInfoDiv.cloneNode(true);
        document.getElementById("result-url-info").innerHTML = "";
        document.getElementById("result-url-info").appendChild(resultUrlInfo);
      }
      if (fakeScore > 50) {
        realResultDiv.classList.add("hidden");
        fakeResultDiv.classList.remove("hidden");
        updateDonutChart(fakeProgress, fakeScore);
        fakeScoreElem.textContent = `${fakeScore}%`;
        fakeExplanationP.textContent = generateExplanationText(fakeScore);
        document.getElementById("fake-consistency").textContent = 
          fakeScore > 75 ? "Very Low" : "Low";
        document.getElementById("fake-anomalies").textContent = 
          fakeScore > 75 ? "Very High" : "High";
        document.getElementById("fake-confidence").textContent = 
          fakeScore > 90 ? "Very High" : (fakeScore > 70 ? "High" : "Medium");
        detailedViewLink.href = analysisResponse.detailedViewUrl;
      } else {
        fakeResultDiv.classList.add("hidden");
        realResultDiv.classList.remove("hidden");
        updateDonutChart(realProgress, realScore);
        realScoreElem.textContent = `${realScore}%`;
        document.getElementById("real-consistency").textContent = 
          realScore > 75 ? "Very High" : "High";
        document.getElementById("real-anomalies").textContent = 
          realScore > 75 ? "Very Low" : "Low";
      }
    }

    function updateProgress(percent, message) {
      progressIndicator.style.width = `${percent}%`;
      progressStep.textContent = message;
      progressPercentage.textContent = `${percent}%`;
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
      errorDiv.innerHTML = `
        <div class="message-icon">
          <i class="fas fa-exclamation-triangle"></i>
        </div>
        <div class="message-content">
          <p><strong>Error:</strong> ${userMessage}</p>
        </div>
      `;
      errorContainer.innerHTML = "";
      errorContainer.appendChild(errorDiv);
      setTimeout(() => {
        errorDiv.classList.add("fade-out");
        setTimeout(() => {
          if (errorDiv.parentNode === errorContainer) {
            errorContainer.removeChild(errorDiv);
          }
        }, 500);
      }, 10000);
    }

    function displayUrlInfo(platform, url) {
      const urlInfoDiv = document.createElement("div");
      urlInfoDiv.className = "url-info";
      const displayUrl = cleanUrlForDisplay(url);
      urlInfoDiv.innerHTML = `
        <p><strong>Platform:</strong> <span class="platform-badge"><i class="${getPlatformIcon(platform)}"></i> ${platform}</span></p>
        <p><strong>URL:</strong> ${displayUrl}</p>
      `;
      const urlInfoContainer = document.getElementById("url-info-container");
      urlInfoContainer.innerHTML = "";
      urlInfoContainer.appendChild(urlInfoDiv);
    }

    function getPlatformDisplayName(platform) {
      if (!platform) return "Unknown";
      switch(platform.toLowerCase()) {
        case "youtube": return "YouTube";
        case "facebook": return "Facebook";
        case "twitter": return "Twitter/X";
        case "reddit": return "Reddit";
        default: return platform || "Unknown";
      }
    }

    function getPlatformIcon(platform) {
      if (!platform) return "fa-solid fa-video";
      switch(platform.toLowerCase()) {
        case "youtube":
        case "YouTube": return "fab fa-youtube";
        case "facebook": 
        case "Facebook": return "fab fa-facebook";
        case "twitter":
        case "Twitter/X": return "fab fa-x-twitter";
        case "reddit":
        case "Reddit": return "fab fa-reddit";
        default: return "fa-solid fa-video";
      }
    }

    function detectPlatformFromUrl(url) {
      if (!url) return null;
      if (url.includes("youtube.com/watch") || url.includes("youtu.be/")) {
        return "youtube";
      } else if ((url.includes("twitter.com/") || url.includes("x.com/")) && url.includes("/status/")) {
        return "twitter";
      } else if ((url.includes("facebook.com/") && (url.includes("/videos/") || url.includes("/watch"))) || url.includes("fb.watch")) {
        return "facebook";
      } else if (url.includes("reddit.com/r/") && url.includes("/comments/")) {
        return "reddit";
      }
      return null;
    }

    function handlePlatformDetection(platform, url) {
      if (platform) {
        notVideoPageDiv.classList.add("hidden");
        videoContentDiv.classList.remove("hidden");
        const platformName = getPlatformDisplayName(platform);
        document.getElementById("platform-name").textContent = platformName;
      } else {
        videoContentDiv.classList.add("hidden");
        notVideoPageDiv.classList.remove("hidden");
        document.getElementById("unsupported-message").textContent = 
          "This extension works on YouTube, Facebook, Twitter, and Reddit video pages.";
      }
    }

    function initDonutCharts() { }

    function updateDonutChart(circleElement, percentage) { }

    function cleanUrlForDisplay(url) {
      try {
        const urlObj = new URL(url);
        if (urlObj.hostname.includes("youtube.com")) {
          return `${urlObj.origin}${urlObj.pathname}?v=${urlObj.searchParams.get("v")}`;
        }
        return `${urlObj.origin}${urlObj.pathname}`;
      } catch (e) {
        return url;
      }
    }

    function generateExplanationText(fakeScore) {
      if (fakeScore > 90) {
        return "This video shows significant facial inconsistencies between frames, strongly indicating AI manipulation. The high percentage of detected anomalies suggests this is likely AI-generated content.";
      } else if (fakeScore > 70) {
        return "This video displays notable facial inconsistencies between frames, indicating AI manipulation. The detected anomalies suggest this video contains AI-generated elements.";
      } else {
        return `This video shows some signs of facial inconsistency between frames, which may indicate AI manipulation. ${fakeScore}% of analyzed frames appear to have been modified.`;
      }
    }
  
  }

});