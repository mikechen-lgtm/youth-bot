import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

interface User {
  member_id: number;
  provider: 'google' | 'line' | 'facebook';
  external_id: string;
  email?: string;
  name: string;
  picture?: string;
}

interface AuthConfig {
  google: { enabled: boolean; client_id: string; redirect_uri: string };
  line: { enabled: boolean; channel_id: string; redirect_uri: string };
  facebook: { enabled: boolean; app_id: string; redirect_uri: string };
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  authConfig: AuthConfig | null;
  login: (provider: 'google' | 'line' | 'facebook') => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);

  const checkAuth = useCallback(async () => {
    console.log('[AuthContext] checkAuth starting...');
    try {
      const response = await fetch('/api/user', { credentials: 'include' });
      console.log('[AuthContext] /api/user response status:', response.status);
      const data = await response.json();
      console.log('[AuthContext] /api/user data:', data);
      if (data.success) {
        setUser(data.user);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('[AuthContext] checkAuth error:', error);
      setUser(null);
    } finally {
      console.log('[AuthContext] checkAuth complete, setting isLoading=false');
      setIsLoading(false);
    }
  }, []);

  const fetchAuthConfig = useCallback(async () => {
    console.log('[AuthContext] fetchAuthConfig starting...');
    try {
      const response = await fetch('/auth/config');
      console.log('[AuthContext] /auth/config response status:', response.status);
      const data = await response.json();
      console.log('[AuthContext] /auth/config data:', data);
      setAuthConfig(data);
    } catch (error) {
      console.error('[AuthContext] fetchAuthConfig error:', error);
    }
  }, []);

  useEffect(() => {
    checkAuth();
    fetchAuthConfig();

    // Check for login success/error in URL params
    const urlParams = new URLSearchParams(window.location.search);
    const loginStatus = urlParams.get('login');
    const error = urlParams.get('error');

    if (loginStatus === 'success') {
      // Re-check auth after successful login redirect
      checkAuth();
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (error) {
      console.error('Login error:', error);
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [checkAuth, fetchAuthConfig]);

  /**
   * Build the OAuth authorization URL for a given provider.
   * Each provider has different URL structure and parameter requirements.
   */
  const buildOAuthUrl = (
    provider: 'google' | 'line' | 'facebook',
    config: AuthConfig,
    state: string
  ): string | null => {
    if (provider === 'google') {
      if (!config.google.enabled) return null;
      const params = new URLSearchParams({
        client_id: config.google.client_id,
        redirect_uri: config.google.redirect_uri,
        response_type: 'code',
        scope: 'openid email profile',
        state: state,
        access_type: 'offline',
        prompt: 'consent',
      });
      return `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
    }

    if (provider === 'line') {
      if (!config.line.enabled) return null;
      const params = new URLSearchParams({
        response_type: 'code',
        client_id: config.line.channel_id,
        redirect_uri: config.line.redirect_uri,
        state: state,
        scope: 'profile openid email',
      });
      return `https://access.line.me/oauth2/v2.1/authorize?${params}`;
    }

    if (provider === 'facebook') {
      if (!config.facebook.enabled) return null;
      const params = new URLSearchParams({
        client_id: config.facebook.app_id,
        redirect_uri: config.facebook.redirect_uri,
        state: state,
        scope: 'public_profile,email',
      });
      return `https://www.facebook.com/v18.0/dialog/oauth?${params}`;
    }

    return null;
  };

  const login = async (provider: 'google' | 'line' | 'facebook'): Promise<void> => {
    if (!authConfig) {
      console.error('[AuthContext] Cannot login: auth config not loaded');
      return;
    }

    try {
      // Request a CSRF-protected state token from the backend
      const stateResponse = await fetch(`/api/auth/state/${provider}`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!stateResponse.ok) {
        console.error('[AuthContext] Failed to get OAuth state from backend:', stateResponse.status);
        return;
      }

      const { state } = await stateResponse.json();
      const authUrl = buildOAuthUrl(provider, authConfig, state);

      if (!authUrl) {
        console.error(`[AuthContext] Provider ${provider} is not enabled`);
        return;
      }

      // Redirect to OAuth provider
      window.location.href = authUrl;
    } catch (error) {
      console.error('[AuthContext] Error initiating OAuth login:', error);
    }
  };

  const logout = async () => {
    try {
      await fetch('/api/logout', { method: 'POST', credentials: 'include' });
      setUser(null);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <AuthContext.Provider value={{
      user,
      isLoading,
      isAuthenticated: !!user,
      authConfig,
      login,
      logout,
      checkAuth
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
