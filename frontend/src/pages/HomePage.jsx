/*
Last Edited: 2024-06-15
Description:
Dashboard showing quick stats.
*/

import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';

function HomePage() {
    const { user } = useAuth();
    const navigate = useNavigate();

    // Request type cards data
    const requestTypes = [
        {
            id: 'pva',
            title: 'PVA 3D Print',
            description: 'Submit a request for PVA (water-soluble support) 3D printing. Ideal for complex geometries and overhangs.',
            icon: '🖨️',
            color: '#3b82f6',
            path: '/submit/pva',
        },
        {
            id: 'resin',
            title: 'Resin 3D Print',
            description: 'Submit a request for resin 3D printing. Perfect for high-detail models and smooth surface finish.',
            icon: '💧',
            color: '#8b5cf6',
            path: '/submit/resin',
        },
        {
            id: 'laser',
            title: 'Laser Cutting',
            description: 'Submit a request for laser cutting services. Great for precise cuts on wood, acrylic, and more.',
            icon: '⚡',
            color: '#ef4444',
            path: '/submit/laser',
        },
    ];

    // Handle card click - navigate to the specific form
    const handleCardClick = (path) => {
        navigate(path);
    };

    return (
        <div style={styles.pageContainer}>
            {/* Navigation Bar */}
            <Navbar />

            {/* Main Content */}
            <main style={styles.main}>
                {/* Welcome Section */}
                <section style={styles.welcomeSection}>
                    <h1 style={styles.welcomeTitle}>
                        Welcome back, {user?.name || 'Student'}!
                    </h1>
                    <p style={styles.welcomeText}>
                        What would you like to create today? Select a service below to submit a new request.
                    </p>
                </section>

                {/* Request Type Cards */}
                <section style={styles.cardsContainer}>
                    {requestTypes.map((type) => (
                        <div
                            key={type.id}
                            style={styles.card}
                            onClick={() => handleCardClick(type.path)}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.transform = 'translateY(-8px)';
                                e.currentTarget.style.boxShadow = '0 12px 40px rgba(0, 0, 0, 0.15)';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.transform = 'translateY(0)';
                                e.currentTarget.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.08)';
                            }}
                        >
                            {/* Card Icon */}
                            <div
                                style={{
                                    ...styles.iconContainer,
                                    backgroundColor: `${type.color}15`,
                                }}
                            >
                                <span style={styles.icon}>{type.icon}</span>
                            </div>

                            {/* Card Content */}
                            <h2 style={styles.cardTitle}>{type.title}</h2>
                            <p style={styles.cardDescription}>{type.description}</p>

                            {/* Card Button */}
                            <button
                                style={{
                                    ...styles.cardButton,
                                    backgroundColor: type.color,
                                }}
                            >
                                Start Request →
                            </button>
                        </div>
                    ))}
                </section>

                {/* Quick Stats Section (Optional) */}
                <section style={styles.statsSection}>
                    <div style={styles.statBox}>
                        <span style={styles.statNumber}>0</span>
                        <span style={styles.statLabel}>Pending Requests</span>
                    </div>
                    <div style={styles.statBox}>
                        <span style={styles.statNumber}>0</span>
                        <span style={styles.statLabel}>Completed</span>
                    </div>
                    <div style={styles.statBox}>
                        <span style={styles.statNumber}>0</span>
                        <span style={styles.statLabel}>In Progress</span>
                    </div>
                </section>
            </main>
        </div>
    );
}

// Styles for the home page
const styles = {
    pageContainer: {
        minHeight: '100vh',
        backgroundColor: '#f5f7fa',
    },
    main: {
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '40px 24px',
    },
    welcomeSection: {
        textAlign: 'center',
        marginBottom: '48px',
    },
    welcomeTitle: {
        fontSize: '32px',
        fontWeight: 'bold',
        color: '#1a1a2e',
        margin: '0 0 12px 0',
    },
    welcomeText: {
        fontSize: '18px',
        color: '#666',
        margin: 0,
    },
    cardsContainer: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '24px',
        marginBottom: '48px',
    },
    card: {
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        padding: '32px',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
    },
    iconContainer: {
        width: '80px',
        height: '80px',
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: '20px',
    },
    icon: {
        fontSize: '36px',
    },
    cardTitle: {
        fontSize: '22px',
        fontWeight: '600',
        color: '#1a1a2e',
        margin: '0 0 12px 0',
    },
    cardDescription: {
        fontSize: '15px',
        color: '#666',
        lineHeight: '1.6',
        margin: '0 0 24px 0',
        flexGrow: 1,
    },
    cardButton: {
        padding: '12px 28px',
        fontSize: '15px',
        fontWeight: '600',
        color: '#ffffff',
        border: 'none',
        borderRadius: '8px',
        cursor: 'pointer',
        transition: 'opacity 0.2s',
    },
    statsSection: {
        display: 'flex',
        justifyContent: 'center',
        gap: '32px',
        flexWrap: 'wrap',
    },
    statBox: {
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        padding: '24px 40px',
        textAlign: 'center',
        boxShadow: '0 2px 12px rgba(0, 0, 0, 0.06)',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
    },
    statNumber: {
        fontSize: '32px',
        fontWeight: 'bold',
        color: '#1a1a2e',
    },
    statLabel: {
        fontSize: '14px',
        color: '#666',
    },
};

export default HomePage;
