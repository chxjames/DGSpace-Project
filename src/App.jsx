/*
Last Edited: 2024-06-15
Description:
Default React app component. Main app component that sets up routing and wraps everything in AuthProvider.
*/

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import HomePage from './pages/HomePage';

function App() {
  return (
    // AuthProvider wraps everything so all components can access auth state
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Route - Login Page */}
          {/* Anyone can access this page */}
          <Route path="/login" element={<Login />} />

          {/* Protected Route - Home Page */}
          {/* Only logged-in users can access this */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            }
          />

          {/* Placeholder routes for future form pages */}
          {/* These will be protected too */}
          <Route
            path="/submit/pva"
            element={
              <ProtectedRoute>
                <div style={{ padding: '100px', textAlign: 'center' }}>
                  <h1>PVA 3D Print Form</h1>
                  <p>Coming soon...</p>
                </div>
              </ProtectedRoute>
            }
          />

          <Route
            path="/submit/resin"
            element={
              <ProtectedRoute>
                <div style={{ padding: '100px', textAlign: 'center' }}>
                  <h1>Resin 3D Print Form</h1>
                  <p>Coming soon...</p>
                </div>
              </ProtectedRoute>
            }
          />

          <Route
            path="/submit/laser"
            element={
              <ProtectedRoute>
                <div style={{ padding: '100px', textAlign: 'center' }}>
                  <h1>Laser Cutting Form</h1>
                  <p>Coming soon...</p>
                </div>
              </ProtectedRoute>
            }
          />

          <Route
            path="/requests"
            element={
              <ProtectedRoute>
                <div style={{ padding: '100px', textAlign: 'center' }}>
                  <h1>My Requests</h1>
                  <p>Coming soon...</p>
                </div>
              </ProtectedRoute>
            }
          />

          {/* Catch-all route - redirects unknown paths to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;