document.addEventListener("DOMContentLoaded", function() {
  // Get user profile information from storage
  chrome.storage.local.get(['session'], function(result) {
    if (result.session && result.session.user) {
      loadUserProfile(result.session.user);
    }
  });
});

// Function to load and display user profile
function loadUserProfile(user) {
  if (!user) return;
  
  // Create profile element if header exists
  const header = document.querySelector('header');
  if (header) {
    // Remove any existing profile element
    const existingProfile = document.querySelector('.user-profile');
    if (existingProfile) {
      existingProfile.remove();
    }
    
    // Create user profile element
    const profileElem = document.createElement('div');
    profileElem.className = 'user-profile';
    
    // Create user avatar with colorized background based on email
    const avatarElem = document.createElement('div');
    avatarElem.className = 'user-avatar';
    avatarElem.textContent = user.email.substring(0, 1).toUpperCase();
    
    // Generate a color from the user's email
    const emailHash = btoa(user.email).split('').reduce((a, b) => a + b.charCodeAt(0), 0);
    avatarElem.style.backgroundColor = `hsl(${emailHash % 360}, 70%, 80%)`;
    
    // Create user email tooltip
    const tooltipElem = document.createElement('div');
    tooltipElem.className = 'user-tooltip';
    tooltipElem.textContent = user.email;
    
    // Add elements to DOM
    profileElem.appendChild(avatarElem);
    profileElem.appendChild(tooltipElem);
    
    // Add to header
    header.appendChild(profileElem);
    
    // Add tooltip functionality
    profileElem.addEventListener('mouseenter', function() {
      tooltipElem.classList.add('visible');
    });
    
    profileElem.addEventListener('mouseleave', function() {
      tooltipElem.classList.remove('visible');
    });
  }
}
