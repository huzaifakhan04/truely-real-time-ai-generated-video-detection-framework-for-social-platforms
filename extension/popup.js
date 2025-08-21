document.addEventListener("DOMContentLoaded", function() {
  
  const analyzeBtn = document.getElementById("analyze-btn");
  const analyzeAgainBtn = document.getElementById("analyze-again-btn");
  const notYoutubeDiv = document.getElementById("not-youtube");
  const youtubeContentDiv = document.getElementById("youtube-content");
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
    if (currentUrl.includes("youtube.com/watch")) {
      notYoutubeDiv.classList.add("hidden");
      youtubeContentDiv.classList.remove("hidden");
    } else {
      notYoutubeDiv.classList.remove("hidden");
      youtubeContentDiv.classList.add("hidden");
    }
  });

  analyzeBtn.addEventListener("click", function() {
    initialStateDiv.classList.add("hidden");
    loadingStateDiv.classList.remove("hidden");
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      const videoUrl = tabs[0].url;
      const videoId = getYoutubeVideoId(videoUrl);
      if (!videoId) {
        showError("Could not identify YouTube video ID.");
        return;
      }
      updateProgress(10, "Downloading video...");
      chrome.runtime.sendMessage(
        {action: "downloadVideo", videoId: videoId},
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
    analyzeBtn.addEventListener("click", function() {
      initialStateDiv.classList.add("hidden");
      loadingStateDiv.classList.remove("hidden");
      chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        const videoUrl = tabs[0].url;
        const videoId = getYoutubeVideoId(videoUrl);
        if (!videoId) {
          showError("Could not identify YouTube video ID.");
          return;
        }
        updateProgress(10, "Downloading video...");
        chrome.runtime.sendMessage(
          {action: "downloadVideo", videoId: videoId},
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
                updateProgress(90, "Finishing analysis...");
                setTimeout(() => {
                  updateProgress(100, "Analysis complete!");
                  loadingStateDiv.classList.add("hidden");
                  resultStateDiv.classList.remove("hidden");
                  const fakeScore = analysisResponse.fakeScore;
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
    let userMessage = message;
    if (message.includes("Server connection failed")) {
      userMessage = "Cannot connect to the analysis server. Please make sure the Python server is running by executing 'python server.py' in the python_server directory.";
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

  function getYoutubeVideoId(url) {
    const urlObj = new URL(url);
    return urlObj.searchParams.get("v");
  }

});