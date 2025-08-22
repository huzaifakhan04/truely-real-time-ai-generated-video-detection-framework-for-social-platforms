function isVideoPage() {
  const url = window.location.href;
  if (url.includes("youtube.com/watch") || url.includes("youtu.be/")) {
    return "youtube";
  }
  if ((url.includes("twitter.com/") || url.includes("x.com/")) && url.includes("/status/")) {
    const videoElements = document.querySelectorAll('video');
    if (videoElements.length > 0) {
      return "twitter";
    }
  }
  if ((url.includes("facebook.com/") && 
      (url.includes("/videos/") || url.includes("/watch"))) || 
      url.includes("fb.watch/")) {
    return "facebook";
  }
  if (url.includes("reddit.com/r/") && url.includes("/comments/")) {
    const videoElements = document.querySelectorAll('video');
    const redditVideo = document.querySelector('.reddit-video-player');
    if (videoElements.length > 0 || redditVideo) {
      return "reddit";
    }
  }
  const videoElements = document.querySelectorAll('video');
  if (videoElements.length > 0) {
    if (url.includes("youtube.com") || url.includes("youtu.be")) {
      return "youtube";
    } else if (url.includes("facebook.com") || url.includes("fb.watch")) {
      return "facebook";
    } else if (url.includes("twitter.com") || url.includes("x.com")) {
      return "twitter";
    } else if (url.includes("reddit.com")) {
      return "reddit";
    }
  }
  return false;
}

chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === "checkVideoPage") {
    const platform = isVideoPage();
    sendResponse({ platform: platform });
  }
});