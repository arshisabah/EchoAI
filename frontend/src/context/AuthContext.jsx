import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

const STORAGE_KEY = 'echoai_user';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load user from localStorage on mount
    try {
      const storedUser = localStorage.getItem(STORAGE_KEY);
      if (storedUser) {
        const parsed = JSON.parse(storedUser);
        setUser(parsed);
        console.log('✅ User loaded from storage:', parsed.username);
      }
    } catch (error) {
      console.error('❌ Error loading user from storage:', error);
      localStorage.removeItem(STORAGE_KEY);
    } finally {
      setLoading(false);
    }
  }, []);

  const login = (userData) => {
    const user = {
      user_id: userData.user_id || `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      username: userData.username.trim(),
      email: userData.email?.trim() || '',
      role: userData.role || 'participant',
      avatar: userData.avatar || userData.username.charAt(0).toUpperCase(),
      loginTime: new Date().toISOString(),
    };
    
    setUser(user);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    console.log('✅ User logged in:', user.username);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
    console.log('👋 User logged out');
  };

  const updateUser = (updates) => {
    if (!user) return;
    
    const updatedUser = { ...user, ...updates };
    setUser(updatedUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedUser));
    console.log('🔄 User updated:', updatedUser.username);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export default AuthContext;