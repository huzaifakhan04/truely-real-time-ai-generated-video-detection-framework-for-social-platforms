// Implementation of Supabase authentication
(function() {
  console.log("Initializing Supabase authentication");

  // Define the Supabase client implementation
  window.supabase = {
    createClient: function(url, key) {
      return {
        auth: {
          // Sign in with email and password
          signInWithPassword: async function(credentials) {
            try {
              const response = await fetch(`${url}/auth/v1/token?grant_type=password`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'apikey': key,
                  'Authorization': `Bearer ${key}`
                },
                body: JSON.stringify({
                  email: credentials.email,
                  password: credentials.password
                })
              });
              
              const data = await response.json();
              
              if (!response.ok) {
                return {
                  data: null,
                  error: data || { message: 'Failed to sign in' }
                };
              }
              
              const user = {
                id: data.user.id,
                email: data.user.email,
                identities: data.user.identities || []
              };
              
              const session = {
                access_token: data.access_token,
                refresh_token: data.refresh_token,
                expires_at: Math.floor(Date.now() / 1000) + data.expires_in,
                user: user
              };
              
              return {
                data: {
                  user: user,
                  session: session
                },
                error: null
              };
            } catch (error) {
              console.error('Authentication error:', error);
              return {
                data: null,
                error: { message: error.message || 'Authentication failed' }
              };
            }
          },
          
          // Sign up with email and password
          signUp: async function(credentials) {
            try {
              const response = await fetch(`${url}/auth/v1/signup`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'apikey': key
                },
                body: JSON.stringify({
                  email: credentials.email,
                  password: credentials.password,
                  data: credentials.data || {},
                  redirect_to: (credentials.options && credentials.options.emailRedirectTo) || undefined
                })
              });
              
              const data = await response.json();
              
              if (!response.ok) {
                return {
                  data: null,
                  error: data || { message: 'Failed to sign up' }
                };
              }
              
              // If auto-confirm is enabled, we'll get a session back
              if (data.access_token) {
                const user = {
                  id: data.user.id,
                  email: data.user.email,
                  identities: data.user.identities || []
                };
                
                const session = {
                  access_token: data.access_token,
                  refresh_token: data.refresh_token,
                  expires_at: Math.floor(Date.now() / 1000) + 3600,
                  user: user
                };
                
                return {
                  data: {
                    user: user,
                    session: session
                  },
                  error: null
                };
              }
              
              // Email confirmation required
              return {
                data: {
                  user: data.user,
                  session: null
                },
                error: null
              };
            } catch (error) {
              console.error('Sign up error:', error);
              return {
                data: null,
                error: { message: error.message || 'Sign up failed' }
              };
            }
          },
          
          // Get user details with token
          getUser: async function(token) {
            try {
              const response = await fetch(`${url}/auth/v1/user`, {
                headers: {
                  'Authorization': `Bearer ${token || ''}`,
                  'apikey': key
                }
              });
              
              const data = await response.json();
              
              if (!response.ok) {
                return {
                  data: { user: null },
                  error: data || { message: 'Failed to get user' }
                };
              }
              
              return {
                data: { user: data },
                error: null
              };
            } catch (error) {
              console.error('Get user error:', error);
              return {
                data: { user: null },
                error: { message: error.message || 'Failed to get user' }
              };
            }
          },
          
          // Refresh session
          refreshSession: async function(options) {
            try {
              const response = await fetch(`${url}/auth/v1/token?grant_type=refresh_token`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'apikey': key
                },
                body: JSON.stringify({
                  refresh_token: options.refresh_token
                })
              });
              
              const data = await response.json();
              
              if (!response.ok) {
                return {
                  data: null,
                  error: data || { message: 'Failed to refresh session' }
                };
              }
              
              const user = {
                id: data.user.id,
                email: data.user.email
              };
              
              const session = {
                access_token: data.access_token,
                refresh_token: data.refresh_token,
                expires_at: Math.floor(Date.now() / 1000) + data.expires_in,
                user: user
              };
              
              return {
                data: {
                  user: user,
                  session: session
                },
                error: null
              };
            } catch (error) {
              console.error('Refresh session error:', error);
              return {
                data: null,
                error: { message: error.message || 'Failed to refresh session' }
              };
            }
          },
          
          // Sign out
          signOut: async function() {
            try {
              const token = localStorage.getItem('supabase.auth.token');
              
              if (token) {
                const response = await fetch(`${url}/auth/v1/logout`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'apikey': key,
                    'Authorization': `Bearer ${JSON.parse(token).access_token}`
                  }
                });
                
                if (!response.ok) {
                  const data = await response.json();
                  return {
                    error: data || { message: 'Failed to sign out' }
                  };
                }
              }
              
              return { error: null };
            } catch (error) {
              console.error('Sign out error:', error);
              return {
                error: { message: error.message || 'Failed to sign out' }
              };
            }
          },
          
          // Auth state change listener
          onAuthStateChange: function(callback) {
            const subscription = {
              unsubscribe: function() {
                // Do nothing in this simplified implementation
              }
            };
            
            // Call with initial state
            callback('INITIAL_SESSION', null);
            
            return { data: { subscription } };
          }
        }
      };
    }
  };

  console.log("Supabase authentication initialized");
})();
