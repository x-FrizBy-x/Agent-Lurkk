const input = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const chatBox = document.getElementById("chatBox");

function appendMessage(text, sender) {
    const message = document.createElement("div");
    message.className = `message ${sender}`;
    message.textContent = text;
    chatBox.appendChild(message);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function setLoading(isLoading) {
    sendBtn.disabled = isLoading;
    sendBtn.textContent = isLoading ? "Sending..." : "Send";
    input.disabled = isLoading;
}

async function sendMessage() {
    const message = input.value.trim();
    if (!message) return;

    appendMessage(message, "user");
    input.value = "";
    setLoading(true);

    const payload = {
        user_id: "alexander",
        message,
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
        appendMessage(data.response || "I’m not sure how to respond to that.", "agent");
    } catch (err) {
        appendMessage("Error: Could not reach backend.", "agent");
    } finally {
        setLoading(false);
        input.focus();
    }
}

sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});
