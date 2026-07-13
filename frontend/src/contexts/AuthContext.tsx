import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { User } from '../types';
import { authAPI } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
  hasRole: (minRole: string) => boolean;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem('mc_token');
    const savedUser = localStorage.getItem('mc_user');
    if (!savedToken || !savedUser) {
      setIsLoading(false);
      return;
    }
    setToken(savedToken);
    try {
      setUser(JSON.parse(savedUser));
    } catch {
      // usuario guardado corrupto: se validará contra el backend
    }
    authAPI.me()
      .then((fresh) => {
        setUser(fresh);
        localStorage.setItem('mc_user', JSON.stringify(fresh));
      })
      .catch(() => {
        localStorage.removeItem('mc_token');
        localStorage.removeItem('mc_user');
        setToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await authAPI.login(username, password);
    localStorage.setItem('mc_token', response.access_token);
    localStorage.setItem('mc_user', JSON.stringify(response.user));
    setToken(response.access_token);
    setUser(response.user);
  }, []);

  const logout = useCallback(() => {
    authAPI.logout().catch(() => { /* best-effort: invalidar token en el server */ });
    localStorage.removeItem('mc_token');
    localStorage.removeItem('mc_user');
    setToken(null);
    setUser(null);
  }, []);

  const hasRole = useCallback((minRole: string) => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    return (user.permissions || []).length > 0;
  }, [user]);

  const hasPermission = useCallback((permission: string) => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    return (user.permissions || []).includes(permission);
  }, [user]);

  const hasAnyPermission = useCallback((permissions: string[]) => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    const perms = user.permissions || [];
    return permissions.some(p => perms.includes(p));
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isLoading, hasRole, hasPermission, hasAnyPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
