/**
 * Admin API service for Hero Banner management
 */

import { csrfManager } from "../utils/csrf";

export interface HeroImage {
  id: number;
  url: string;
  alt_text: string;
  display_order: number;
  is_active?: number;
  link_url?: string | null;
  gcs_object_name?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  error?: string;
  message?: string;
  images?: HeroImage[];
  image?: HeroImage;
  authenticated?: boolean;
  csrf_token?: string;
}

class AdminApiService {
  private baseUrl = "";

  /**
   * Check admin authentication status
   */
  async checkAuth(): Promise<ApiResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/admin/check`, {
        credentials: "include",
      });
      const data = await response.json();
      // Update CSRF token if provided
      if (data.csrf_token) {
        csrfManager.setToken(data.csrf_token);
      }
      return data;
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Admin login
   */
  async login(username: string, password: string): Promise<ApiResponse> {
    try {
      // Fetch CSRF token first
      await csrfManager.fetchToken();

      const response = await csrfManager.protectedFetch(`${this.baseUrl}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      // Store CSRF token from login response
      if (data.success && data.csrf_token) {
        csrfManager.setToken(data.csrf_token);
      }

      return data;
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Admin logout
   */
  async logout(): Promise<ApiResponse> {
    try {
      const response = await csrfManager.protectedFetch(`${this.baseUrl}/api/admin/logout`, {
        method: "POST",
      });
      const data = await response.json();

      // Clear CSRF token on logout
      if (data.success) {
        csrfManager.clearToken();
      }

      return data;
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Get all hero images (admin view)
   */
  async getHeroImages(): Promise<ApiResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/admin/hero-images`, {
        credentials: "include",
      });
      return await response.json();
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Upload a new hero image
   */
  async uploadImage(file: File, altText?: string, linkUrl?: string): Promise<ApiResponse> {
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (altText) {
        formData.append("alt_text", altText);
      }
      if (linkUrl) {
        formData.append("link_url", linkUrl);
      }

      const response = await csrfManager.protectedFetch(`${this.baseUrl}/api/admin/hero-images`, {
        method: "POST",
        body: formData,
      });
      return await response.json();
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Delete a hero image
   */
  async deleteImage(imageId: number): Promise<ApiResponse> {
    try {
      const response = await csrfManager.protectedFetch(
        `${this.baseUrl}/api/admin/hero-images/${imageId}`,
        {
          method: "DELETE",
        }
      );
      return await response.json();
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Reorder hero images
   */
  async reorderImages(order: number[]): Promise<ApiResponse> {
    try {
      const response = await csrfManager.protectedFetch(
        `${this.baseUrl}/api/admin/hero-images/reorder`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ order }),
        }
      );
      return await response.json();
    } catch {
      return { success: false, error: "Network error" };
    }
  }

  /**
   * Update hero image metadata
   */
  async updateImage(
    imageId: number,
    data: { alt_text?: string; is_active?: boolean; link_url?: string }
  ): Promise<ApiResponse> {
    try {
      const response = await csrfManager.protectedFetch(
        `${this.baseUrl}/api/admin/hero-images/${imageId}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      );
      return await response.json();
    } catch {
      return { success: false, error: "Network error" };
    }
  }
}

export const adminApi = new AdminApiService();
