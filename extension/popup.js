document.addEventListener("DOMContentLoaded", function() {

  chrome.storage.local.get(["session"], function(result) {
    if (!result.session) {
      window.location.href = "auth.html";
      return;
    }
    const expiresAt = result.session.expires_at * 1000;
    if (Date.now() > expiresAt) {
      chrome.storage.local.remove(["session"], function() {
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
        url: "https://github.com/huzaifakhan04/truely-real-time-ai-generated-video-detection-framework-for-social-platforms/blob/main/README.md"
      });
    });

    function startAnalysis(videoUrl) {
      updateProgress(10, "Fetching video and audio...");
      chrome.runtime.sendMessage(
        {action: "downloadCombined", videoUrl: videoUrl},
        function(response) {
          if (response.error) {
            showError(response.error);
            return;
          }
          updateProgress(30, "Scanning frames...");
          setTimeout(() => {
            updateProgress(50, "Checking facial details...");
            setTimeout(() => {
              updateProgress(70, "Assessing credibility...");
              chrome.runtime.sendMessage(
                {
                  action: "analyzeCombined", 
                  videoPath: response.videoPath,
                  audioPath: response.audioPath
                },
                function(analysisResponse) {
                  if (analysisResponse.error) {
                    showError(analysisResponse.error);
                    return;
                  }
                  updateProgress(90, "Finalizing...");
                  setTimeout(() => {
                    updateProgress(100, "Done!");
                    
                    setTimeout(() => {
                      displayResults(analysisResponse);
                    }, 500);
                  }, 500);
                }
              );
            }, 800);
          }, 800);
        }
      );
    }

    function updateCredibilityScore(score) {
      const credibilityValueElem = document.getElementById("credibility-score");
      if (credibilityValueElem) {
        const displayScore = 100 - score;
        credibilityValueElem.textContent = `${displayScore}%`;
        // Since we're inverting the score (100 - score), we also invert the color logic
        credibilityValueElem.style.color = displayScore < 50 ? "red" : "green";
      }
    }

    function displayResults(analysisResponse) {
      loadingStateDiv.classList.add("hidden");
      resultStateDiv.classList.remove("hidden");
      const fakeScore = analysisResponse.fakeScore;
      const newsScore = analysisResponse.newsScore || 0;
      const realScore = fakeScore;
      const urlInfoDiv = loadingStateDiv.querySelector(".url-info");
      if (urlInfoDiv) {
        const resultUrlInfo = urlInfoDiv.cloneNode(true);
        document.getElementById("result-url-info").innerHTML = "";
        document.getElementById("result-url-info").appendChild(resultUrlInfo);
      }
      detailedViewLink.href = analysisResponse.detailedViewUrl;
      const newsSection = document.getElementById("news-analysis-section");
      if (newsSection) {
        if (analysisResponse.newsSummary && analysisResponse.newsSummary !== "No audio analysis available") {
          updateCredibilityScore(newsScore);
          const verdictElem = document.getElementById("content-verdict");
          if (verdictElem && analysisResponse.verdict) {
            let verdictText = "Unknown";
            let verdictClass = "";
            switch(analysisResponse.verdict.toLowerCase()) {
              case "authentic":
                verdictText = "Authentic";
                verdictClass = "high-credibility";
                break;
              case "misleading":
                verdictText = "Misleading";
                verdictClass = "medium-credibility";
                break;
              case "fake":
                verdictText = "Fake";
                verdictClass = "low-credibility";
                break;
              case "uncertain":
                verdictText = "Uncertain";
                verdictClass = "medium-credibility";
                break;
            }
            verdictElem.textContent = verdictText;
            verdictElem.className = `report-detail-value ${verdictClass}`;
          }
          const confidenceElem = document.getElementById("verdict-confidence");
          if (confidenceElem) {
            confidenceElem.textContent = `${analysisResponse.confidence || 0}%`;
          }
          const summaryElem = document.getElementById("news-summary");
          if (summaryElem) {
            summaryElem.textContent = analysisResponse.newsSummary;
          }
        } else {
          const summaryElem = document.getElementById("news-summary");
          if (summaryElem) {
            summaryElem.textContent = "No audio analysis available. The video may not have audio content, or the audio could not be transcribed.";
          }
          const credibilityElem = document.getElementById("credibility-score");
          if (credibilityElem) {
            credibilityElem.textContent = "N/A";
          }
          const verdictElem = document.getElementById("content-verdict");
          if (verdictElem) {
            verdictElem.textContent = "Not Available";
          }
          const confidenceElem = document.getElementById("verdict-confidence");
          if (confidenceElem) {
            confidenceElem.textContent = "N/A";
          }
        }
      }
      const handleEvidenceList = (containerId, sectionId) => {
        const evidenceContainer = document.getElementById(containerId);
        if (evidenceContainer && analysisResponse.evidence && analysisResponse.evidence.length > 0) {
          evidenceContainer.innerHTML = "";
          analysisResponse.evidence.forEach(source => {
            const sourceItem = document.createElement("div");
            sourceItem.className = "evidence-item";
            sourceItem.innerHTML = `
              <a href="${source.url}" target="_blank" class="evidence-link">
                <div class="evidence-title">${source.title}</div>
                <div class="evidence-snippet">${source.snippet || 'Source confirming this'}</div>
                <div class="evidence-url">${new URL(source.url).hostname}</div>
              </a>
            `;
            evidenceContainer.appendChild(sourceItem);
          });
        } else if (evidenceContainer) {
          evidenceContainer.innerHTML = "<p class='no-sources'>No verified sources available for this content.</p>";
        }
      };
      handleEvidenceList("evidence-list", "sources-section");
      handleEvidenceList("real-evidence-list", "real-sources-section");
      const realNewsSection = document.getElementById("real-news-analysis-section");
      if (realNewsSection) {
        if (analysisResponse.newsSummary && analysisResponse.newsSummary !== "No audio analysis available") {
          const credibilityElem = document.getElementById("real-credibility-score");
          if (credibilityElem) {
            const displayScore = 100 - newsScore;
            credibilityElem.textContent = `${displayScore}%`;
            // Apply color based on the inverted score
            credibilityElem.classList.remove("low", "medium", "high");
            if (displayScore < 40) {
              credibilityElem.classList.add("low");
            } else if (displayScore < 70) {
              credibilityElem.classList.add("medium");
            } else {
              credibilityElem.classList.add("high");
            }
          }
          const verdictElem = document.getElementById("real-content-verdict");
          if (verdictElem && analysisResponse.verdict) {
            let verdictText = "Unknown";
            let verdictClass = "";
            switch(analysisResponse.verdict.toLowerCase()) {
              case "authentic":
                verdictText = "Authentic";
                verdictClass = "low-credibility";
                break;
              case "misleading":
                verdictText = "Misleading";
                verdictClass = "medium-credibility";
                break;
              case "fake":
                verdictText = "Fake";
                verdictClass = "high-credibility";
                break;
              case "uncertain":
                verdictText = "Uncertain";
                verdictClass = "medium-credibility";
                break;
            }
            verdictElem.textContent = verdictText;
            verdictElem.className = `report-detail-value ${verdictClass}`;
          }
          const confidenceElem = document.getElementById("real-verdict-confidence");
          if (confidenceElem) {
            confidenceElem.textContent = `${analysisResponse.confidence || 0}%`;
          }
          const summaryElem = document.getElementById("real-news-summary");
          if (summaryElem) {
            summaryElem.textContent = analysisResponse.newsSummary;
          }
        } else {
          const summaryElem = document.getElementById("real-news-summary");
          if (summaryElem) {
            summaryElem.textContent = "No audio analysis available. The video may not have audio content, or the audio could not be transcribed.";
          }
          const credibilityElem = document.getElementById("real-credibility-score");
          if (credibilityElem) {
            credibilityElem.textContent = "N/A";
          }
          const verdictElem = document.getElementById("real-content-verdict");
          if (verdictElem) {
            verdictElem.textContent = "Not Available";
          }
          const confidenceElem = document.getElementById("real-verdict-confidence");
          if (confidenceElem) {
            confidenceElem.textContent = "N/A";
          }
        }
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
      } else {
        fakeResultDiv.classList.add("hidden");
        realResultDiv.classList.remove("hidden");
        updateDonutChart(realProgress, realScore);
        realScoreElem.textContent = `${realScore}%`;
        document.getElementById("real-consistency").textContent = 
          realScore < 25 ? "Very High" : "High";
        document.getElementById("real-anomalies").textContent = 
          realScore < 25 ? "Very Low" : "Low";
        document.getElementById("real-detailed-view-link").href = analysisResponse.detailedViewUrl;
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
        userMessage = "Connection failed: Please ensure the analysis server is running. Start it by executing 'python server.py' in the server folder.";
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
        <p>${displayUrl}</p>
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
          "⚠️ Truely works only on video pages.";
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
        return "This video shows strong signs of AI-generated alteration – facial inconsistencies and anomalies suggest possible manipulation.";
      } else if (fakeScore > 70) {
        return "This video shows clear indications of AI manipulation – recurring facial inconsistencies across frames suggest AI-generated editing.";
      } else {
        return `This video shows mild signs of possible AI alteration – subtle inconsistencies were detected in ${fakeScore}% of analyzed frames.`;
      }
    }
  
  }

});