document.addEventListener('DOMContentLoaded', () => {
    // Only run if we are on the chat page
    const sendBtn = document.getElementById('send-btn');
    const inputField = document.getElementById('user-input');
    const endBtn = document.getElementById('end-chat-btn');
    const chatHistory = document.getElementById('chat-history');
    const loader = document.getElementById('loading-indicator'); // 1. Get the loader element

    if (!sendBtn) return; // Not chat page

    function addMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        msgDiv.innerHTML = `<div class="bubble">${text}</div>`;
        
        // 2. Insert BEFORE the loader so the loader always stays at the bottom
        if (loader && loader.parentNode === chatHistory) {
            chatHistory.insertBefore(msgDiv, loader);
        } else {
            chatHistory.appendChild(msgDiv);
        }
        
        scrollToBottom();
    }

    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    async function sendMessage() {
        const text = inputField.value.trim();
        if (!text) return;

        // Add user message immediately
        addMessage(text, 'user');
        inputField.value = '';

        // 3. SHOW "Thinking..."
        if (loader) {
            loader.style.display = 'flex';
            scrollToBottom();
        }

        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();

            // 4. HIDE "Thinking..."
            if (loader) loader.style.display = 'none';

            // Handle potential difference in API key (response vs message)
            const replyText = data.response || data.message || "I didn't catch that.";
            addMessage(replyText, 'agent');

        } catch (error) {
            // Hide loader on error too
            if (loader) loader.style.display = 'none';
            addMessage("Error communicating with Zooka.", 'agent');
            console.error(error);
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    endBtn.addEventListener('click', async () => {
        if (confirm("Are you sure you want to end the conversation?")) {
            try {
                await fetch('/api/end_session', { method: 'POST' });
            } catch (e) {
                console.error("End session failed", e);
            }
            alert("Thank you for chatting with Zooka");
            window.location.href = "/";
        }
    });
});