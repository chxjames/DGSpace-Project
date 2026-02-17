/*
Last Edited: 2024-06-15
Description:
Defines the top navigation bar. Displays links to Home, Profile, and Login/Logout based on auth state.
*/
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Navbar() {
    // Get user info and logout function from auth context
    const { user, logout } = useAuth();

    // useNavigate hook lets us redirect programmatically
    const navigate = useNavigate();

    // Handle logout button click
    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <nav style={styles.navbar}>
            {/* Left side - Logo/Brand */}
            <div style={styles.brand}>
                <Link to="/" style={styles.brandLink}>
                    OpsManager
                </Link>
            </div>

            {/* Center - Navigation Links */}
            <div style={styles.navLinks}>
                <Link to="/" style={styles.link}>
                    Home
                </Link>
                <Link to="/requests" style={styles.link}>
                    My Requests
                </Link>
                <Link to="/submit" style={styles.link}>
                    New Request
                </Link>
            </div>

            {/* Right side - User info and Logout */}
            <div style={styles.userSection}>
                <span style={styles.userName}>
                    Welcome, {user?.name || user?.email || 'User'}
                </span>
                <button onClick={handleLogout} style={styles.logoutButton}>
                    Logout
                </button>
            </div>
        </nav>
    );
}

// Styles for the navbar
const styles = {
    navbar: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 32px',
        backgroundColor: '#1a1a2e',
        color: '#ffffff',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
    },
    brand: {
        fontSize: '24px',
        fontWeight: 'bold',
    },
    brandLink: {
        color: '#ffffff',
        textDecoration: 'none',
    },
    navLinks: {
        display: 'flex',
        gap: '32px',
    },
    link: {
        color: '#ffffff',
        textDecoration: 'none',
        fontSize: '16px',
        padding: '8px 16px',
        borderRadius: '4px',
        transition: 'background-color 0.2s',
    },
    userSection: {
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
    },
    userName: {
        fontSize: '14px',
        color: '#a0a0a0',
    },
    logoutButton: {
        padding: '8px 20px',
        backgroundColor: 'transparent',
        color: '#ffffff',
        border: '1px solid #ffffff',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '14px',
        transition: 'all 0.2s',
    },
};

export default Navbar;