/*
Last Edited: 2024-06-15
Description:
Manages login state globally. Stores user info, provides login() and logout() functions, 
and persists sessions to localStorage. 
*/

import { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

// Create the context - this is like a "global container" for auth data
const AuthContext = createContext(null);

// AuthProvider component - wraps your entire app to provide auth state everywhere
export function AuthProvider({ children }) {
  // State to store the current user's information
  const [user, setUser] = useState(null);
  
  // State to store the authentication token
  const [token, setToken] = useState(null);
  
  // State to track if we're still checking for an existing session
  const [loading, setLoading] = useState(true);

  // useEffect runs when the component first loads
  // It checks if the user was previously logged in
  useEffect(() => {
    // Try to get saved auth data from localStorage
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');

    if (savedToken && savedUser) {
      // If we found saved data, restore the session
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }

    // Done checking, set loading to false
    setLoading(false);
  }, []);

  // Login function - called when user submits login form
  const login = async (email, password) => {
    try {
      // Send login request to your backend
      const response = await api.post('/auth/login', {
        email,
        password,
      });

      // Extract token and user data from response
      const { token: newToken, user: userData } = response.data;

      // Save to localStorage so user stays logged in after refresh
      localStorage.setItem('token', newToken);
      localStorage.setItem('user', JSON.stringify(userData));

      // Update state
      setToken(newToken);
      setUser(userData);

      // Return success
      return { success: true };
    } catch (error) {
      // If login fails, return the error message
      return {
        success: false,
        error: error.response?.data?.message || 'Login failed. Please try again.',
      };
    }
  };

  // Logout function - clears all auth data
  const logout = () => {
    // Remove from localStorage
    localStorage.removeItem('token');
    localStorage.removeItem('user');

    // Clear state
    setToken(null);
    setUser(null);
  };

  // Check if user is authenticated
  // Returns true if we have both a token and user data
  const isAuthenticated = !!token && !!user;

  // The value object contains everything we want to share with other components
  const value = {
    user,
    token,
    loading,
    isAuthenticated,
    login,
    logout,
  };

  // Render the provider with all children components inside
  // Any component inside AuthProvider can access the auth state
  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// Custom hook to easily access auth context from any component
// Usage: const { user, login, logout } = useAuth();
export function useAuth() {
  const context = useContext(AuthContext);
  
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
}
