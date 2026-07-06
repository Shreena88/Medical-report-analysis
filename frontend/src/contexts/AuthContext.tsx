import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/axios';

export interface UserProfile {
  id: string;
  email: string;
  gender: 'male' | 'female';
  created_at: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, gender: 'male' | 'female') => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [loading, setLoading] = useState<boolean>(true);

  // Load profile if token is present on startup
  useEffect(() => {
    const loadProfile = async () => {
      if (token) {
        try {
          const res = await api.get<UserProfile>('/auth/profile');
          setUser(res.data);
        } catch (err) {
          console.error('Failed to load user profile', err);
          // 401 interceptor in axios will handle token clearing
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    };
    loadProfile();
  }, [token]);

  const login = async (email: string, password: string) => {
    const res = await api.post<{ access_token: string; token_type: string }>('/auth/login', {
      email,
      password,
    });
    const { access_token } = res.data;
    localStorage.setItem('token', access_token);
    setToken(access_token);
    
    // Fetch profile
    const profileRes = await api.get<UserProfile>('/auth/profile');
    setUser(profileRes.data);
  };

  const signup = async (email: string, password: string, gender: 'male' | 'female') => {
    await api.post('/auth/signup', {
      email,
      password,
      gender,
    });
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
