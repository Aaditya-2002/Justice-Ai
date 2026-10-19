// Base URL for the API
const API_BASE_URL = '/api/v1';

// Token storage key
const TOKEN_KEY = 'hermes_token';

// Get token from localStorage
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

// Set token in localStorage
function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

// Remove token from localStorage
function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
}

// Check if user is authenticated
function isAuthenticated() {
    return !!getToken();
}

// Make an authenticated request
async function authenticatedFetch(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    return fetch(url, {
        ...options,
        headers: headers,
    });
}

// Handle login form
if (document.getElementById('login-form')) {
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        try {
            const response = await fetch(`${API_BASE_URL}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    'username': username,
                    'password': password,
                }),
            });
            if (response.ok) {
                const data = await response.json();
                setToken(data.access_token);
                window.location.href = 'chat.html';
            } else {
                const error = await response.json();
                alert(error.detail || 'Login failed');
            }
        } catch (error) {
            alert('An error occurred during login');
        }
    });
}

// Handle registration form
if (document.getElementById('register-form')) {
    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('register-username').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        try {
            const response = await fetch(`${API_BASE_URL}/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    email: email,
                    password: password,
                }),
            });
            if (response.ok) {
                alert('Registration successful');
                window.location.href = 'login.html';
            } else {
                const error = await response.json();
                alert(error.detail || 'Registration failed');
            }
        } catch (error) {
            alert('An error occurred during registration');
        }
    });
}

// Handle logout button
if (document.getElementById('logout-btn')) {
    document.getElementById('logout-btn').addEventListener('click', () => {
        removeToken();
        window.location.href = 'login.html';
    });
}

// Redirect to login if not authenticated and on a protected page
if (!isAuthenticated() && (window.location.pathname.endsWith('chat.html') || window.location.pathname.endsWith('documents.html'))) {
    window.location.href = 'login.html';
}
