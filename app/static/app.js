"use strict";

const $ = (id) => document.getElementById(id);
const ui = {
  messages: $("messages"), form: $("composer"), input: $("message"), send: $("send"),
  model: $("model"), mode: $("mode"), reset: $("reset"), sidebarReset: $("sidebar-reset"),
  status: $("status"), dot: $("status-dot"), summary: $("model-summary"),
  badge: $("model-badge"), info: $("model-info"),
};
const sessionId = crypto.randomUUID();
let busy = false;
let lastStatus = "Starting";
let currentModel = null;

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
}

function markdown(value) {
  let safe = escapeHtml(value), blocks = [];
  safe = safe.replace(/```([^\n]*)\n([\s\S]*?)```/g, (_, language, code) => {
    blocks.push(`<pre><code data-language="${language.trim()}">${code}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  safe = safe.replace(/`([^`\n]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
  return safe.replace(/\u0000(\d+)\u0000/g, (_, index) => blocks[Number(index)]);
}

function contentParts(content) {
  return typeof content === "string" ? [{type: "text", text: content}] : content;
}

function addMessage(role, content, temporary = false) {
  document.querySelector(".welcome")?.remove();
  const row = document.createElement("article");
  row.className = `message ${role}${temporary ? " generating-message" : ""}`;
  const identity = document.createElement("div");
  identity.className = "message-identity";
  identity.innerHTML = role === "assistant"
    ? '<img src="/assets/shion/avatar.svg" alt=""><span>SHION</span>'
    : '<span class="user-mark">You</span>';
  const body = document.createElement("div");
  body.className = "message-body";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  for (const part of contentParts(content)) {
    if (part.type === "text") bubble.innerHTML += markdown(part.text);
  }
  body.appendChild(bubble);
  if (!temporary) {
    const actions = document.createElement("div");
    actions.className = "message-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.setAttribute("aria-label", `Copy ${role} message`);
    copy.addEventListener("click", async () => {
      const plainText = contentParts(content).filter((part) => part.type === "text").map((part) => part.text).join("\n");
      await navigator.clipboard.writeText(plainText);
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = "Copy"; }, 1200);
    });
    actions.appendChild(copy);
    body.appendChild(actions);
  }
  row.append(identity, body);
  ui.messages.appendChild(row);
  ui.messages.scrollTop = ui.messages.scrollHeight;
  return row;
}

function setStatus(state) {
  lastStatus = state;
  ui.status.textContent = state === "Generating" ? "紫苑が応答を紡いでいます…" : state;
  ui.dot.className = "";
  const key = state.toLowerCase();
  if (key === "ready") ui.dot.classList.add("ready");
  else if (key === "generating" || key === "loading model") ui.dot.classList.add("generating");
  else if (key === "error") ui.dot.classList.add("error");
  const ready = state === "Ready";
  ui.input.disabled = !ready || busy;
  ui.model.disabled = !ready || busy;
  ui.mode.disabled = busy;
  ui.reset.disabled = busy;
  ui.sidebarReset.disabled = busy;
  ui.send.textContent = busy ? "Stop" : "Send";
  ui.send.classList.toggle("stop", busy);
  ui.send.disabled = busy ? false : !ready;
}

function populateModels(models) {
  if (ui.model.options.length) return;
  for (const item of models) {
    const option = new Option(item.display_name, item.alias);
    option.disabled = !item.available;
    option.title = item.unavailable_reason || item.modification_type;
    ui.model.add(option);
  }
}

function renderModelInfo(data) {
  currentModel = data;
  ui.summary.textContent = `Model: ${data.display_name} · Mode: ${ui.mode.options[ui.mode.selectedIndex].text}`;
  const experimental = /Experimental|Third-party/i.test(data.provenance || "");
  ui.badge.hidden = !experimental;
  const fields = [
    ["Repository", data.repo_id], ["Revision", data.revision], ["Parent", data.parent_model],
    ["Base origin:", data.base_origin || "not specified"], ["Provenance", data.provenance],
    ["Model change", data.modification_type], ["Quantization", data.quantization],
    ["Context", data.context_limit], ["VRAM allocated", `${data.gpu_memory_allocated_mib} MiB`],
  ];
  ui.info.replaceChildren();
  for (const [label, value] of fields) {
    const term = document.createElement("dt"), description = document.createElement("dd");
    term.textContent = label; description.textContent = value;
    ui.info.append(term, description);
  }
}

async function poll() {
  try {
    const response = await fetch("/api/status", {cache: "no-store"});
    const data = await response.json();
    populateModels(data.models || []);
    setStatus(data.state);
    if (data.model_alias) {
      ui.model.value = data.model_alias;
      renderModelInfo(data);
    }
  } catch {
    setStatus("Error");
    ui.summary.textContent = "Local server unavailable";
  }
}

async function stopGeneration() {
  if (!busy) return;
  ui.send.disabled = true;
  ui.send.textContent = "Stopping…";
  try {
    await fetch("/api/stop", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: sessionId}),
    });
  } catch {
    ui.send.disabled = false;
    ui.send.textContent = "Stop";
  }
}

async function send(event) {
  event.preventDefault();
  if (busy) { await stopGeneration(); return; }
  const message = ui.input.value.trim();
  if (!message) return;
  busy = true;
  ui.input.value = "";
  ui.input.style.height = "auto";
  addMessage("user", message);
  const waiting = addMessage("assistant", "紫苑が応答を紡いでいます…", true);
  setStatus("Generating");
  try {
    const response = await fetch("/api/chat", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: sessionId, mode: ui.mode.value, message}),
    });
    const data = await response.json();
    waiting.remove();
    if (!response.ok) throw new Error(data.error || "応答に失敗しました。");
    addMessage("assistant", data.response || "生成を停止しました。");
  } catch (error) {
    waiting.remove();
    addMessage("assistant", error.message || "モデルの応答生成に失敗しました。");
  } finally {
    busy = false;
    await poll();
    ui.input.focus();
  }
}

async function newChat() {
  if (busy) return;
  await fetch("/api/reset", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId})});
  ui.messages.innerHTML = '<div class="welcome"><p class="eyebrow">NEW CONVERSATION</p><h2>新しい対話を始めましょう。</h2><p>以前の短期会話履歴はメモリから削除されました。</p></div>';
}

ui.form.addEventListener("submit", send);
ui.input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ui.form.requestSubmit(); } });
ui.input.addEventListener("input", () => { ui.input.style.height = "auto"; ui.input.style.height = `${Math.min(ui.input.scrollHeight, 220)}px`; });
ui.reset.addEventListener("click", newChat);
ui.sidebarReset.addEventListener("click", newChat);
ui.mode.addEventListener("change", async () => { await newChat(); if (currentModel) renderModelInfo(currentModel); await poll(); });
ui.model.addEventListener("change", async () => {
  if (busy) return;
  setStatus("Loading model");
  const response = await fetch("/api/model", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId, model_alias: ui.model.value})});
  if (!response.ok) { const data = await response.json(); addMessage("assistant", data.error || "Model switching failed."); }
  await poll();
});

poll();
setInterval(poll, 1500);
