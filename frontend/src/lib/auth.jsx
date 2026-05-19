import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, setAuthToken } from './api';

const AuthCtx = createContext({ user: null, login: () => {}, logout: () => {}, loading: true });

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api.me()
      .then(u => { if (mounted) setUser(u); })
      .catch(() => {
        // Token inválido o expirado: limpiar todo para mostrar login sin trabas
        if (mounted) {
          setAuthToken(null);
          setUser(null);
        }
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  const login = async (username, password) => {
    const res = await api.login({ username, password });
    setAuthToken(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const logout = async () => {
    try { await api.logout(); } catch (e) { /* ignore */ }
    setAuthToken(null);
    setUser(null);
  };

  return <AuthCtx.Provider value={{ user, login, logout, loading }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
export const isAdmin = (user) => user?.role === 'admin';
