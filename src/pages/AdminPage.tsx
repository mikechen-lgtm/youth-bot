import { useState, useEffect } from "react";
import { AdminLogin } from "../components/admin/AdminLogin";
import { HeroImageManager } from "../components/admin/HeroImageManager";
import { adminApi } from "../services/adminApi";

export function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const result = await adminApi.checkAuth();
      setIsAuthenticated(result.success && result.authenticated === true);
    } catch {
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-500">載入中...</div>
      </div>
    );
  }

  return isAuthenticated ? (
    <HeroImageManager onLogout={() => setIsAuthenticated(false)} />
  ) : (
    <AdminLogin onSuccess={() => setIsAuthenticated(true)} />
  );
}
