// Base URL for the API
const API_BASE_URL = '/api/v1';

// Token storage key
const TOKEN_KEY = 'hermes_token';

// Get token from localStorage
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
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

// Load conversations and populate the list
async function loadConversations() {
    try {
        const response = await authenticatedFetch(`${API_BASE_URL}/conversations`);
        if (response.ok) {
            const conversations = await response.json();
            const conversationList = document.getElementById('conversation-list');
            conversationList.innerHTML = '';
            conversations.forEach(conv => {
                const li = document.createElement('li');
                li.textContent = conv.title || 'Untitled';
                li.dataset.id = conv.id;
                li.addEventListener('click', () => selectConversation(conv.id));
                conversationList.appendChild(li);
            });
            // If there's a selected conversation in localStorage, select it
            const selectedId = localStorage.getItem('selectedConversation');
            if (selectedId) {
                selectConversation(selectedId);
            }
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to load conversations');
        }
    } catch (error) {
        alert('An error occurred while loading conversations');
    }
}

// Select a conversation and load its messages
async function selectConversation(conversationId) {
    // Update UI
    document.querySelectorAll('.conversation-list li').forEach(li => {
        li.classList.remove('active');
        if (li.dataset.id === conversationId) {
            li.classList.add('active');
        }
    });
    document.getElementById('chat-title').textContent = 'Loading conversation...';
    document.getElementById('chat-messages').innerHTML = '';

    // Save selected conversation ID
    localStorage.setItem('selectedConversation', conversationId);

    // Load messages
    try {
        // We need to get the messages for this conversation.
        // We don't have an endpoint for that yet.
        // We'll simulate by sending an empty message and then displaying the response? 
        // That doesn't work for loading history.
        // We'll just show a placeholder and when the user sends a message, we'll get the response.
        // We'll also need to store the messages in the frontend state.
        // For now, we'll just show a message that says "Messages will be loaded here."
        document.getElementById('chat-messages').innerHTML = '<p>Messages will be loaded here. Start by sending a message.</p>';
        document.getElementById('chat-title').textContent = 'Chat';
    } catch (error) {
        alert('An error occurred while loading messages');
    }
}

// Send a message
async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const message = chatInput.value.trim();
    if (!message) {
        return;
    }
    const conversationId = localStorage.getItem('selectedConversation');
    if (!conversationId) {
        alert('Please select a conversation first');
        return;
    }
    // Disable input while sending
    chatInput.disabled = true;
    document.getElementById('chat-send-btn').disabled = true;
    try {
        const response = await authenticatedFetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            body: JSON.stringify({
                conversation_id: conversationId,
                message: message,
            }),
        });
        if (response.ok) {
            const data = await response.json();
            // We'll display the user message and the assistant response
            const chatMessages = document.getElementById('chat-messages');
            // User message
            const userMsgDiv = document.createElement('div');
            userMsgDiv.className = 'chat-message user';
            userMsgDiv.textContent = message;
            chatMessages.appendChild(userMsgDiv);
            // Assistant response
            const assistantMsgDiv = document.createElement('div');
            assistantMsgDiv.className = 'chat-message assistant';
            assistantMsgDiv.textContent = data.response;
            chatMessages.appendChild(assistantMsgDiv);
            
            // Display citations if available
            if (data.citations && data.citations.length > 0) {
                const citationsDiv = document.createElement('div');
                citationsDiv.className = 'chat-citations';
                citationsDiv.textContent = 'Sources: ' + data.citations.map(c => c.filename).join(', ');
                chatMessages.appendChild(citationsDiv);
            }
            // Scroll to the bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
            // Clear input
            chatInput.value = '';
        } else {
            const error = await response.json();
            alert(error.detail || 'Failed to send message');
        }
    } catch (error) {
        alert('An error occurred while sending the message');
    } finally {
        chatInput.disabled = false;
        document.getElementById('chat-send-btn').disabled = false;
    }
}

// New conversation button
if (document.getElementById('new-conversation-btn')) {
    document.getElementById('new-conversation-btn').addEventListener('click', async () => {
        const title = prompt('Enter a title for the new conversation:');
        if (title !== null) {
            try {
                const response = await authenticatedFetch(`${API_BASE_URL}/conversations`, {
                    method: 'POST',
                    body: JSON.stringify({ title: title }),
                });
                if (response.ok) {
                    const conversation = await response.json();
                    // Add the new conversation to the list and select it
                    loadConversations();
                    selectConversation(conversation.id);
                } else {
                    const error = await response.json();
                    alert(error.detail || 'Failed to create conversation');
                }
            } catch (error) {
                alert('An error occurred while creating the conversation');
            }
        }
    });
}

// Set up chat input
if (document.getElementById('chat-send-btn')) {
    document.getElementById('chat-send-btn').addEventListener('click', sendMessage);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}

// Load conversations when the page loads
if (document.getElementById('conversation-list')) {
    loadConversations();
}
