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

function generateRandomState(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

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

  const login = (provider: 'google' | 'line' | 'facebook') => {
    if (!authConfig) return;

    let authUrl = '';
    const state = generateRandomState();
    sessionStorage.setItem(`${provider}_oauth_state`, state);

    switch (provider) {
      case 'google':
        if (!authConfig.google.enabled) return;
        authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
          `client_id=${authConfig.google.client_id}&` +
          `redirect_uri=${encodeURIComponent(authConfig.google.redirect_uri)}&` +
          `response_type=code&` +
          `scope=${encodeURIComponent('openid email profile')}&` +
          `access_type=offline&prompt=consent`;
        break;
      case 'line':
        if (!authConfig.line.enabled) return;
        authUrl = `https://access.line.me/oauth2/v2.1/authorize?` +
          `response_type=code&` +
          `client_id=${authConfig.line.channel_id}&` +
          `redirect_uri=${encodeURIComponent(authConfig.line.redirect_uri)}&` +
          `state=${state}&` +
          `scope=profile%20openid%20email`;
        break;
      case 'facebook':
        if (!authConfig.facebook.enabled) return;
        authUrl = `https://www.facebook.com/v18.0/dialog/oauth?` +
          `client_id=${authConfig.facebook.app_id}&` +
          `redirect_uri=${encodeURIComponent(authConfig.facebook.redirect_uri)}&` +
          `state=${state}&` +
          `scope=public_profile,email`;
        break;
    }

    window.location.href = authUrl;
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
