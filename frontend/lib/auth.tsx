"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ACCESS_TOKEN_KEY, ApiError, getCurrentUser, login, NetworkError, USER_KEY } from "@/lib/api";
import type { AuthenticatedProfile } from "@/lib/types";

type AuthContextValue = {
  user: AuthenticatedProfile | null;
  ready: boolean;
  signIn: (email: string) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [user, setUser] = useState<AuthenticatedProfile | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
    const cachedUser = window.localStorage.getItem(USER_KEY);
    if (!token) {
      setReady(true);
      return;
    }
    if (cachedUser) {
      try {
        setUser(JSON.parse(cachedUser) as AuthenticatedProfile);
      } catch {
        window.localStorage.removeItem(USER_KEY);
      }
    }
    getCurrentUser(token)
      .then((profile) => {
        setUser(profile);
        window.localStorage.setItem(USER_KEY, JSON.stringify(profile));
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 401) {
          setUser(null);
        } else if (!(reason instanceof NetworkError) && !(reason instanceof ApiError)) {
          setUser(null);
        }
      })
      .finally(() => setReady(true));
  }, []);

  const signIn = useCallback(async (email: string) => {
    const result = await login(email);
    window.localStorage.setItem(ACCESS_TOKEN_KEY, result.access_token);
    window.localStorage.setItem(USER_KEY, JSON.stringify(result.user));
    setUser(result.user);
  }, []);

  const signOut = useCallback(() => {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, ready, signIn, signOut }), [user, ready, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
