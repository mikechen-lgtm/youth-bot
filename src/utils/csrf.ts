/**
 * CSRF Token Management Utility
 *
 * This module manages CSRF tokens for authenticated requests.
 * It automatically fetches, stores, and includes CSRF tokens in API requests.
 */

class CSRFManager {
  private token: string | null = null;
  private baseURL: string;

  constructor(baseURL: string = "") {
    this.baseURL = baseURL;
  }

  private resolveURL(path: string): string {
    if (!this.baseURL) {
      return path;
    }
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    return `${this.baseURL}${normalizedPath}`;
  }

  /**
   * Fetch a new CSRF token from the server
   */
  async fetchToken(): Promise<string> {
    try {
      const response = await fetch(this.resolveURL("/api/csrf-token"), {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch CSRF token: ${response.status}`);
      }

      const data = await response.json();
      if (data.success && data.csrf_token) {
        this.token = data.csrf_token;
        return this.token;
      }

      throw new Error("Invalid CSRF token response");
    } catch (error) {
      console.error("Error fetching CSRF token:", error);
      throw error;
    }
  }

  /**
   * Get the current CSRF token, fetching a new one if needed
   */
  async getToken(): Promise<string> {
    if (!this.token) {
      await this.fetchToken();
    }
    return this.token || "";
  }

  /**
   * Set CSRF token manually (e.g., from login response)
   */
  setToken(token: string): void {
    this.token = token;
  }

  /**
   * Clear the stored CSRF token
   */
  clearToken(): void {
    this.token = null;
  }

  /**
   * Get headers object with CSRF token included
   */
  async getHeaders(additionalHeaders: Record<string, string> = {}): Promise<Record<string, string>> {
    const token = await this.getToken();
    return {
      "X-CSRF-Token": token,
      ...additionalHeaders,
    };
  }

  /**
   * Make a protected fetch request with CSRF token
   */
  async protectedFetch(
    url: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const token = await this.getToken();
    const headers = new Headers(options.headers || {});
    headers.set("X-CSRF-Token", token);

    return fetch(this.resolveURL(url), {
      ...options,
      credentials: "include",
      headers,
    });
  }
}

// Singleton instance
const DEFAULT_BASE_URL = (() => {
  const fromEnv = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (!fromEnv) {
    return "";
  }
  return fromEnv.replace(/\/+$/, "");
})();

export const csrfManager = new CSRFManager(DEFAULT_BASE_URL);

export default csrfManager;
