"use strict";

const messages = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const connection = document.getElementById("connection");
const handoffPanel = document.getElementById("handoff-panel");
const handoffForm = document.getElementById("handoff-form");
const handoffResult = document.getElementById("handoff-result");
const sessionKey = "mti-demo-session";
let sessionId = sessionStorage.getItem(sessionKey);
if (!sessionId) {
  sessionId = crypto.randomUUID();
  sessionStorage.setItem(sessionKey, sessionId);
}
let lastQuestion = "";

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function addUserMessage(text) {
  const article = node("article", "message user");
  article.append(node("div", "bubble", text));
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function addAssistantMessage(result) {
  const article = node("article", "message assistant");
  const bubble = node("div", "bubble");
  bubble.dir = result.language === "ar" ? "rtl" : "auto";
  const status = node("span", `status ${result.status}`, result.status.replaceAll("_", " "));
  bubble.append(status, document.createElement("br"), node("span", "answer", result.answer));
  if (result.citations && result.citations.length) {
    const list = node("div", "citations");
    for (const citation of result.citations) {
      const item = node("div", "citation");
      item.append(
        node("strong", "", `${citation.doc_id} · ${citation.title}`),
        node("p", "", citation.section),
        node("p", "", citation.snippet),
      );
      list.append(item);
    }
    bubble.append(list);
  }
  article.append(bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  handoffPanel.hidden = result.status !== "escalated";
  document.getElementById("handoff-summary").value = lastQuestion.slice(0, 1000);
}

async function checkHealth() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error("Service is not ready");
    connection.textContent = "Service ready";
    connection.className = "connection ready";
  } catch (_) {
    connection.textContent = "Service unavailable";
    connection.className = "connection error";
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  lastQuestion = message;
  addUserMessage(message);
  messageInput.value = "";
  sendButton.disabled = true;
  sendButton.textContent = "Thinking…";
  handoffPanel.hidden = true;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 29000);
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The service could not answer right now.");
    addAssistantMessage(result);
  } catch (error) {
    const article = node("article", "message assistant");
    article.append(node("div", "bubble", error.name === "AbortError" ? "The request timed out. Please try again." : error.message));
    messages.append(article);
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Send";
    messageInput.focus();
  }
});

// Immediate send on Enter key (Shift+Enter for newline)
messageInput.addEventListener("keydown", (event) => {
  if ((event.key === "Enter" || event.keyCode === 13) && !event.shiftKey) {
    event.preventDefault();
    if (!sendButton.disabled && messageInput.value.trim()) {
      chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  }
});

function dismissHandoff() {
  handoffPanel.hidden = true;
  handoffResult.textContent = "";
  handoffForm.reset();
}

document.getElementById("handoff-close-btn")?.addEventListener("click", dismissHandoff);
document.getElementById("handoff-dismiss-btn")?.addEventListener("click", dismissHandoff);

handoffForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  handoffResult.textContent = "Saving…";
  try {
    const response = await fetch("/handoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        summary: document.getElementById("handoff-summary").value,
        contact_name: document.getElementById("contact-name").value,
        contact_method: document.getElementById("contact-method").value,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not save handoff details.");
    handoffResult.textContent = result.message + " (Closing...)";
    handoffForm.reset();
    setTimeout(dismissHandoff, 3500);
  } catch (error) {
    handoffResult.textContent = error.message;
  }
});

checkHealth();
