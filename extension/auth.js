document.addEventListener("DOMContentLoaded", async function() {

    let supabaseUrl = "";
    let supabaseKey = "";
    let supabase;

    function testSupabaseConnection(url, key) {
        fetch(`${url}/auth/v1/token?grant_type=password`, {
            method: "HEAD",
            headers: {
                "apikey": key
            }
        })
        .then(response => {
            console.log("Connection test status:", response.status);
        })
        .catch(error => {
            console.error("Connection test error:", error);
        });
    }

    chrome.runtime.sendMessage({action: "getEnvVars"}, function(response) {
        if (!response) {
            console.error("No response from background script");
            supabaseUrl = window.CONFIG.SUPABASE_URL;
            supabaseKey = window.CONFIG.SUPABASE_KEY;
        } else {
            supabaseUrl = response.SUPABASE_URL || window.CONFIG.SUPABASE_URL;
            supabaseKey = response.SUPABASE_KEY || window.CONFIG.SUPABASE_KEY;
        }
        console.log("Using Supabase URL:", supabaseUrl);
        supabase = window.supabase.createClient(supabaseUrl, supabaseKey);
        testSupabaseConnection(supabaseUrl, supabaseKey);
        initializeAuth();
    });
    
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
    
    function initializeAuth() {

        checkSession();
    
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
        
        loginFormElement.addEventListener("submit", async function(e) {
            e.preventDefault();
            const email = document.getElementById("login-email").value;
            const password = document.getElementById("login-password").value;
            setButtonLoading(loginButton, true);
            hideError(loginError);
            try {
            console.log("Attempting to sign in with:", supabaseUrl);
            const { data, error } = await supabase.auth.signInWithPassword({
                email: email,
                password: password
            }).catch(err => {
                console.error("Sign in request failed:", err);
                return { data: null, error: { message: "Failed to fetch: " + err.message } };
            });
            
            console.log("Sign in response:", data ? "Success" : "Failed");
            
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
                window.location.href = "popup.html";
            });
            } catch (err) {
            showError(loginError, "An unexpected error occurred. Please try again.");
            setButtonLoading(loginButton, false);
            console.error(err);
            }
        });

        registerFormElement.addEventListener("submit", async function(e) {
            e.preventDefault();
            const email = document.getElementById("register-email").value;
            const password = document.getElementById("register-password").value;
            const confirm = document.getElementById("register-confirm").value;
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
                console.log("Attempting to sign up with:", supabaseUrl);
                // Add more detailed logging for debugging
                const { data, error } = await supabase.auth.signUp({
                    email: email,
                    password: password,
                    options: {
                        emailRedirectTo: chrome.runtime.getURL("auth.html")
                    }
                }).catch(err => {
                    console.error("Sign up request failed:", err);
                    return { data: null, error: { message: "Failed to fetch: " + err.message } };
                });
                
                console.log("Sign up response:", data ? "Success" : "Failed");
                
                if (error) {
                    showError(registerError, error.message);
                    setButtonLoading(registerButton, false);
                    return;
                }
                if (data.user && data.user.identities && data.user.identities.length === 0) {
                    showError(registerError, "This email is already registered. Please sign in instead.");
                    setButtonLoading(registerButton, false);
                    return;
                }
                if (data.user && !data.session) {
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
                if (data.session) {
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
                    window.location.href = "popup.html";
                    });
                }
            } catch (err) {
                showError(registerError, "An unexpected error occurred. Please try again.");
                setButtonLoading(registerButton, false);
                console.error(err);
            }
        });

        async function checkSession() {
            chrome.storage.local.get(["session"], async function(result) {
                if (result.session) {
                    try {
                        const { data, error } = await supabase.auth.getUser(result.session.access_token);
                        if (!error && data && data.user) {
                            window.location.href = "popup.html";
                        } else {
                            try {
                                const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession({
                                    refresh_token: result.session.refresh_token
                                });
                                if (!refreshError && refreshData && refreshData.session) {
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
                                        window.location.href = "popup.html";
                                    });
                                } else {
                                    chrome.storage.local.remove(["session"]);
                                }
                            } catch (refreshErr) {
                                console.error("Error refreshing session:", refreshErr);
                                chrome.storage.local.remove(["session"]);
                            }
                        }
                    } catch (err) {
                        console.error("Error checking session:", err);
                        chrome.storage.local.remove(['session']);
                    }
                }
            });
        }

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
                    if (window.location.pathname.includes("auth.html")) {
                        window.location.href = "popup.html";
                    }
                });
            } else if (event === "SIGNED_OUT") {
                chrome.storage.local.remove(["session"], function() {
                    if (!window.location.pathname.includes("auth.html")) {
                        window.location.href = "auth.html";
                    }
                });
            }
        });

    }
  
});