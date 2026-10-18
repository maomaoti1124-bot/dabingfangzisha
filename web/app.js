"use strict";
const byId = (id) => document.getElementById(id);
const form = byId("chat-form"), input = byId("message"), send = byId("send");
const consent = byId("consent"), feedback = byId("feedback"), retry = byId("retry");
const log = byId("messages"), welcome = byId("welcome"), stop = byId("stop");
let history = [], configured = false, pending = false, failed = false, controller = null, epoch = 0;

function controls() {
  send.disabled = pending || failed || !consent.checked || !configured || !input.value.trim();
  input.disabled = pending || failed;
  stop.hidden = !pending;
  retry.hidden = !failed;
  retry.disabled = pending || !consent.checked;
}
function addMessage(role, text) {
  welcome.hidden = true;
  const row = document.createElement("div"); row.className = "bubble-row " + role;
  if (role === "assistant") { const avatar = document.createElement("span"); avatar.className = "avatar"; avatar.textContent = "◡"; row.append(avatar); }
  const bubble = document.createElement("div"); bubble.className = "bubble";
  if (role === "assistant") { const label = document.createElement("div"); label.className = "message-label"; label.textContent = "AI · 支持性对话"; bubble.append(label); }
  const content = document.createElement("span"); content.textContent = text; bubble.append(content); row.append(bubble); log.append(row);
  row.scrollIntoView({ block: "nearest", behavior: "auto" });
}
async function transmit() {
  if (pending || !consent.checked || !configured) return;
  const ticket = epoch; pending = true; failed = false; controller = new AbortController();
  feedback.textContent = "正在等待 DeepSeek 回复。你可以随时停止等待。"; controls();
  try {
    const response = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: history }), signal: controller.signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "本次请求未成功，请稍后重试。");
    if (ticket !== epoch) return;
    history.push({ role: "assistant", content: data.reply }); addMessage("assistant", data.reply);
    feedback.textContent = data.truncated ? "本次回复可能未完整生成。你可以继续补充；紧急情况请直接联系现实中的帮助。" : "";
  } catch (error) {
    if (ticket !== epoch) return;
    failed = true;
    feedback.textContent = error.name === "AbortError" ? "已停止等待。服务端请求可能仍在处理；稍后可手动重试，或开启新对话。" : error.message;
  } finally {
    if (ticket === epoch) { pending = false; controller = null; controls(); if (!failed) input.focus(); }
  }
}
form.addEventListener("submit", (event) => {
  event.preventDefault(); if (send.disabled) return;
  if (history.length >= 39) { feedback.textContent = "本次对话已达到 20 轮，请开启新对话。当前页面内容不会被自动截断。"; return; }
  const text = input.value.trim(); history.push({ role: "user", content: text }); addMessage("user", text); input.value = ""; transmit();
});
input.addEventListener("input", controls); consent.addEventListener("change", controls);
input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!send.disabled) form.requestSubmit(); } });
retry.addEventListener("click", transmit); stop.addEventListener("click", () => { if (controller) controller.abort(); });
byId("clear").addEventListener("click", () => {
  if (history.length && !window.confirm("清空当前页面的对话？本应用不会保留聊天副本。")) return;
  epoch += 1; if (controller) controller.abort(); history = []; pending = false; failed = false; controller = null;
  log.replaceChildren(); welcome.hidden = false; feedback.textContent = ""; input.value = ""; controls(); input.focus();
});
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
  if (pending || failed) return; input.value = button.dataset.prompt; controls(); input.focus();
}));
byId("setup").addEventListener("click", () => byId("setup-dialog").showModal());
byId("help").addEventListener("click", () => byId("help-dialog").showModal());
document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => byId(button.dataset.close).close()));
byId("copy-help").addEventListener("click", async () => {
  const text = document.querySelector("blockquote").textContent;
  try { await navigator.clipboard.writeText(text); byId("copy-feedback").textContent = "已复制，可以发给你信任的人。"; }
  catch { byId("copy-feedback").textContent = "无法自动复制，请选中上方文字手动复制。"; }
});
fetch("/api/status").then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then((status) => {
  configured = Boolean(status.configured); byId("connection").classList.toggle("ready", configured);
  byId("connection").querySelector("span").textContent = configured ? "DeepSeek · " + status.model : "尚未配置 API Key";
  if (!configured) feedback.textContent = "点击右上角“连接说明”，在本地终端配置密钥后即可对话。";
  controls();
}).catch(() => { byId("connection").querySelector("span").textContent = "无法连接本地服务"; feedback.textContent = "请确认 server.py 正在运行，然后刷新页面。"; });
controls();
