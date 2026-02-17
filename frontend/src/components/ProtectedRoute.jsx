/*
Last Edited: 2024-06-15
Description:
Guards pages that require login. Redirects unauthenticated users to /login.
*/

import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function ProtectedRoute({ children }) {
    // Get auth state from AuthContext
    const { isAuthenticated, loading } = useAuth();

    // While checking if user is logged in, show a loading state
    // This prevents a flash of the login page before redirect
    if (loading) {
        return (
            <div style={styles.loadingContainer}>
                <div style={styles.spinner}></div>
                <p>Loading...</p>
            </div>
        );
    }

    // If not authenticated, redirect to login page
    // "replace" prevents the protected page from appearing in browser history
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    // If authenticated, render the protected content (children)
    return children;
}

// Simple inline styles for the loading state
const styles = {
    loadingContainer: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        fontSize: '18px',
        color: '#666',
    },
    spinner: {
        width: '40px',
        height: '40px',
        border: '4px solid #f3f3f3',
        borderTop: '4px solid #3498db',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
        marginBottom: '16px',
    },
};

export default ProtectedRoute;
