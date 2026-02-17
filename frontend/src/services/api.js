/* 
Last Edited: 2024-06-15
Description: This module configures axios to communicate with the backend.
Automatically attaches auth tokens to requests and handles expired sessions.
*/
import axios from 'axios';

// Create an axios instance with your backend URL
// The URL comes from your .env file (REACT_APP_API_URL)
const api = axios.create({
    baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request Interceptor
// This runs BEFORE every request is sent to the server
// It automatically attaches the auth token to every request
api.interceptors.request.use(
    (config) => {
        // Get the token from localStorage
        const token = localStorage.getItem('token');

        // If a token exists, add it to the request headers
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response Interceptor
// This runs AFTER every response is received from the server
// It handles errors globally (like expired tokens)
api.interceptors.response.use(
    (response) => {
        // If the request was successful, just return the response
        return response;
    },
    (error) => {
        // If the server returns 401 (Unauthorized), the token is invalid or expired
        if (error.response && error.response.status === 401) {
            // Clear the invalid token
            localStorage.removeItem('token');
            localStorage.removeItem('user');

            // Redirect to login page
            window.location.href = '/login';
        }

        return Promise.reject(error);
    }
);

// Export the configured axios instance
export default api;
