/*
Last Edited: 2024-06-15
Description:
Login form with email/password fields, error handling, and loading states.
*/

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Login() {
    // Form input states
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    // Error message state
    const [error, setError] = useState('');

    // Loading state for submit button
    const [isLoading, setIsLoading] = useState(false);

    // Get login function from auth context
    const { login } = useAuth();

    // For redirecting after successful login
    const navigate = useNavigate();

    // Handle form submission
    const handleSubmit = async (e) => {
        // Prevent page refresh
        e.preventDefault();

        // Clear any previous errors
        setError('');

        // Basic validation
        if (!email || !password) {
            setError('Please enter both email and password');
            return;
        }

        // Set loading state
        setIsLoading(true);

        // Attempt login
        const result = await login(email, password);

        if (result.success) {
            // Login successful - redirect to home page
            navigate('/');
        } else {
            // Login failed - show error message
            setError(result.error);
            setIsLoading(false);
        }
    };

    return (
        <div style={styles.container}>
            <div style={styles.loginCard}>
                {/* Header */}
                <div style={styles.header}>
                    <h1 style={styles.title}>Welcome to the DG Space</h1>
                    <p style={styles.subtitle}>Donald's Garage Services Portal</p>
                </div>

                {/* Error Message */}
                {error && (
                    <div style={styles.errorBox}>
                        {error}
                    </div>
                )}

                {/* Login Form */}
                <form onSubmit={handleSubmit} style={styles.form}>
                    {/* Email Field */}
                    <div style={styles.inputGroup}>
                        <label htmlFor="USD email" style={styles.label}>
                            USD Email
                        </label>
                        <input
                            type="email"
                            id="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="Enter your USD email"
                            style={styles.input}
                            disabled={isLoading}
                        />
                    </div>

                    {/* Password Field */}
                    <div style={styles.inputGroup}>
                        <label htmlFor="password" style={styles.label}>
                            Password
                        </label>
                        <input
                            type="password"
                            id="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter your password"
                            style={styles.input}
                            disabled={isLoading}
                        />
                    </div>

                    {/* Submit Button */}
                    <button
                        type="submit"
                        style={{
                            ...styles.submitButton,
                            opacity: isLoading ? 0.7 : 1,
                            cursor: isLoading ? 'not-allowed' : 'pointer',
                        }}
                        disabled={isLoading}
                    >
                        {isLoading ? 'Logging in...' : 'Log In'}
                    </button>
                </form>

                {/* Footer */}
                <p style={styles.footer}>
                    Need an account? Contact your administrator.
                </p>
            </div>
        </div>
    );
}

// Styles for the login page
const styles = {
    container: {
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'url(/images/background.jpeg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        padding: '20px',
    },
    loginCard: {
        width: '100%',
        maxWidth: '400px',
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)',
        padding: '40px',
    },
    header: {
        textAlign: 'center',
        marginBottom: '32px',
    },
    title: {
        fontSize: '28px',
        fontWeight: 'bold',
        color: '#1a1a2e',
        margin: '0 0 8px 0',
    },
    subtitle: {
        fontSize: '16px',
        color: '#666',
        margin: 0,
    },
    errorBox: {
        backgroundColor: '#fee2e2',
        color: '#dc2626',
        padding: '12px 16px',
        borderRadius: '8px',
        marginBottom: '20px',
        fontSize: '14px',
        textAlign: 'center',
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
    },
    label: {
        fontSize: '14px',
        fontWeight: '500',
        color: '#333',
    },
    input: {
        padding: '12px 16px',
        fontSize: '16px',
        border: '1px solid #ddd',
        borderRadius: '8px',
        outline: 'none',
        transition: 'border-color 0.2s',
    },
    submitButton: {
        padding: '14px',
        fontSize: '16px',
        fontWeight: '600',
        color: '#ffffff',
        backgroundColor: '#1a1a2e',
        border: 'none',
        borderRadius: '8px',
        marginTop: '8px',
        transition: 'background-color 0.2s',
    },
    footer: {
        textAlign: 'center',
        marginTop: '24px',
        fontSize: '14px',
        color: '#666',
    },
};

export default Login;