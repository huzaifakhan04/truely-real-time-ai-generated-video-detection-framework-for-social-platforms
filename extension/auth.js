document.addEventListener("DOMContentLoaded", function() {
  // Initialize Supabase client with actual implementation
  const supabaseUrl = 'https://lgfgocwqlfpnkcteiyen.supabase.co';
  const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxnZmdvY3dxbGZwbmtjdGVpeWVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4OTY3NTEsImV4cCI6MjA3MTQ3Mjc1MX0.tSKgaRayWwnfNmYLM8GYzjfSPRRWMNvxqgNxATp0IPc';
  const supabase = window.supabase.createClient(supabaseUrl, supabaseKey);
  
  // DOM Elements
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const showRegisterBtn = document.getElementById("show-register");
  const showLoginBtn = document.getElementById("show-login");
  const loginFormElement = document.getElementById("login-form-element");
  const registerFormElement = document.getElementById("register-form-element");
  const loginError = document.getElementById("login-error");
  const registerError = document.getElementById("register-error");
  const loginButton = document.getElementById("login-button");
  const registerButton = document.getElementById("register-button");
  
  // Check if user is already logged in
  checkSession();
  
  // Event Listeners for form toggle
  showRegisterBtn.addEventListener("click", function(e) {
    e.preventDefault();
    loginForm.classList.add("hidden");
    registerForm.classList.remove("hidden");
  });
  
  showLoginBtn.addEventListener("click", function(e) {
    e.preventDefault();
    registerForm.classList.add("hidden");
    loginForm.classList.remove("hidden");
  });
  
  // Login form submission
  loginFormElement.addEventListener("submit", async function(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    
    setButtonLoading(loginButton, true);
    hideError(loginError);
    
    try {
      // Sign in with Supabase
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email,
        password: password
      });
      
      if (error) {
        showError(loginError, error.message);
        setButtonLoading(loginButton, false);
        return;
      }
      
      if (!data || !data.session) {
        showError(loginError, "No session returned. Please try again.");
        setButtonLoading(loginButton, false);
        return;
      }
      
      // Save session in extension storage
      const session = {
        access_token: data.session.access_token,
        refresh_token: data.session.refresh_token,
        expires_at: data.session.expires_at,
        user: {
          id: data.user.id,
          email: data.user.email
        }
      };
      
      chrome.storage.local.set({ session: session }, function() {
        // Redirect to main extension page
        window.location.href = "popup.html";
      });
      
    } catch (err) {
      showError(loginError, "An unexpected error occurred. Please try again.");
      setButtonLoading(loginButton, false);
      console.error(err);
    }
  });
  
  // Registration form submission
  registerFormElement.addEventListener("submit", async function(e) {
    e.preventDefault();
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;
    const confirm = document.getElementById("register-confirm").value;
    
    // Client-side validation
    if (password !== confirm) {
      showError(registerError, "Passwords don't match");
      return;
    }
    
    if (password.length < 6) {
      showError(registerError, "Password must be at least 6 characters");
      return;
    }
    
    setButtonLoading(registerButton, true);
    hideError(registerError);
    
    try {
      // Sign up with Supabase
      const { data, error } = await supabase.auth.signUp({
        email: email,
        password: password,
        options: {
          emailRedirectTo: chrome.runtime.getURL("auth.html") // Redirect URL for email confirmation
        }
      });
      
      if (error) {
        showError(registerError, error.message);
        setButtonLoading(registerButton, false);
        return;
      }
      
      // Check if user already exists
      if (data.user && data.user.identities && data.user.identities.length === 0) {
        showError(registerError, "This email is already registered. Please sign in instead.");
        setButtonLoading(registerButton, false);
        return;
      }
      
      // Handle email confirmation if required
      if (data.user && !data.session) {
        // Email confirmation is required
        registerForm.innerHTML = `
          <div class="message success">
            <div class="message-icon">
              <i class="fas fa-check-circle"></i>
            </div>
            <div class="message-content">
              <h3>Registration Successful!</h3>
              <p>Please check your email to confirm your account before signing in.</p>
            </div>
          </div>
          <button class="btn secondary-btn" id="back-to-login">
            <span>Back to Login</span>
          </button>
        `;
        
        document.getElementById("back-to-login").addEventListener("click", function() {
          window.location.reload();
        });
        return;
      }
      
      // If auto-confirmation is enabled (no email verification required)
      if (data.session) {
        // Save session in extension storage
        const session = {
          access_token: data.session.access_token,
          refresh_token: data.session.refresh_token,
          expires_at: data.session.expires_at,
          user: {
            id: data.user.id,
            email: data.user.email
          }
        };
        
        chrome.storage.local.set({ session: session }, function() {
          // Redirect to main extension page
          window.location.href = "popup.html";
        });
      }
      
    } catch (err) {
      showError(registerError, "An unexpected error occurred. Please try again.");
      setButtonLoading(registerButton, false);
      console.error(err);
    }
  });
  
  // Check if user has an active session
  async function checkSession() {
    chrome.storage.local.get(['session'], async function(result) {
      if (result.session) {
        try {
          // Verify user session with Supabase
          const { data, error } = await supabase.auth.getUser(result.session.access_token);
          
          if (!error && data && data.user) {
            // Session is valid, redirect to main page
            window.location.href = "popup.html";
          } else {
            // Session is invalid, try to refresh
            try {
              const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession({
                refresh_token: result.session.refresh_token
              });
              
              if (!refreshError && refreshData && refreshData.session) {
                // Save the new session
                const newSession = {
                  access_token: refreshData.session.access_token,
                  refresh_token: refreshData.session.refresh_token,
                  expires_at: refreshData.session.expires_at,
                  user: {
                    id: refreshData.user.id,
                    email: refreshData.user.email
                  }
                };
                
                chrome.storage.local.set({ session: newSession }, function() {
                  // Redirect to main extension page
                  window.location.href = "popup.html";
                });
              } else {
                // Session refresh failed, remove the old session
                chrome.storage.local.remove(['session']);
              }
            } catch (refreshErr) {
              console.error("Error refreshing session:", refreshErr);
              chrome.storage.local.remove(['session']);
            }
          }
        } catch (err) {
          console.error("Error checking session:", err);
          chrome.storage.local.remove(['session']);
        }
      }
    });
  }
  
  // Utility functions
  function showError(element, message) {
    element.textContent = message;
    element.classList.remove("hidden");
  }
  
  function hideError(element) {
    element.classList.add("hidden");
  }
  
  function setButtonLoading(button, isLoading) {
    if (isLoading) {
      const buttonText = button.querySelector("span");
      const buttonIcon = button.querySelector("i");
      
      if (buttonText) buttonText.style.visibility = "hidden";
      if (buttonIcon) buttonIcon.style.visibility = "hidden";
      
      button.classList.add("loading");
      button.disabled = true;
    } else {
      const buttonText = button.querySelector("span");
      const buttonIcon = button.querySelector("i");
      
      if (buttonText) buttonText.style.visibility = "visible";
      if (buttonIcon) buttonIcon.style.visibility = "visible";
      
      button.classList.remove("loading");
      button.disabled = false;
    }
  }
  
  // Setup Supabase auth listener
  supabase.auth.onAuthStateChange((event, session) => {
    if (event === 'SIGNED_IN' && session) {
      const sessionData = {
        access_token: session.access_token,
        refresh_token: session.refresh_token,
        expires_at: session.expires_at,
        user: {
          id: session.user.id,
          email: session.user.email
        }
      };
      
      chrome.storage.local.set({ session: sessionData }, function() {
        if (window.location.pathname.includes('auth.html')) {
          window.location.href = "popup.html";
        }
      });
    } else if (event === 'SIGNED_OUT') {
      chrome.storage.local.remove(['session'], function() {
        if (!window.location.pathname.includes('auth.html')) {
          window.location.href = "auth.html";
        }
      });
    }
  });
});
