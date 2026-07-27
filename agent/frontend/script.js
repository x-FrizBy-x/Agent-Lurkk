async function sendMessage() {
    const input = document.getElementById("userInput");
    const chatBox = document.getElementById("chatBox");

    const message = input.value.trim();
    if (!message) return;

    // Show user message
    chatBox.innerHTML += `<div class="message user">${message}</div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    const payload = {
        user_id: "alexander",
        message: message,
        session_id: "default"
    };

    try {
        const response = await fetch("http://127.0.0.1:8000/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        // Show agent reply
        chatBox.innerHTML += `<div class="message agent">${data.response}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;

    } catch (err) {
        chatBox.innerHTML += `<div class="message agent">Error: Could not reach backend.</div>`;
    }

    input.value = "";
}
