"use strict";

const $ = (id) => document.getElementById(id);
const ui = {
  messages: $("messages"), form: $("composer"), input: $("message"), send: $("send"),
  model: $("model"), mode: $("mode"), reset: $("reset"), sidebarReset: $("sidebar-reset"),
  status: $("status"), dot: $("status-dot"), summary: $("model-summary"),
  badge: $("model-badge"), info: $("model-info"), jump: $("jump-latest"),
  connection: $("connection-status"), subsystem: $("subsystem-status"), session: $("session-info"),
  sessionList: $("session-list"), sessionSearch: $("session-search"),
  voiceSettings: $("voice-settings"), voicePanel: $("voice-panel"), voicePreset: $("voice-preset"),
  voiceStyle: $("voice-style"), voiceDeveloper: $("voice-developer"), voiceAutoplay: $("voice-autoplay"), voiceStatus: $("voice-status"),
  workspace: document.querySelector(".workspace"), sidebar: $("sidebar"), nav: $("workspace-nav"), pageSlot: $("page-slot"), chatPage: $("chat-page"),
  mobileNav: $("mobile-nav-toggle"), mobileCharacter: $("mobile-character-toggle"), characterPanel: $("shion-panel"), characterClose: $("character-close"), scrim: $("mobile-scrim"),
  archiveDialog: $("archive-dialog"), archiveTitle: $("archive-title"), archiveConfirm: $("archive-confirm"),
  renderer: $("character-renderer"), monitorConversation: $("monitor-conversation"), monitorVoice: $("monitor-voice"), monitorModel: $("monitor-model"), monitorPreset: $("monitor-preset"),
};

function createSessionId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    return `session-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
  }
  return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

const ephemeralKey = "shion-ephemeral-sessions:v1";
let sessions = [];
let activeSessionId = null;
let busy = false;
let currentModel = null;
let lastUserMessage = "";
let reconnecting = false;
let composing = false;
let messageCount = 0;
let voiceMeta = {approved_presets: [], developer_models: {}};
let activeAudio = null;
const characterProfiles = {shion: "/assets/characters/shion/profile.json"};
const fallbackCharacterAsset = "/assets/shion/avatar.svg";
let activeCharacter = {character_id: "shion", renderer: {type: "static_2d"}, assets: {avatar: fallbackCharacterAsset, panel: fallbackCharacterAsset}, presentation_states: {}};

function safeCharacterPath(baseUrl, path) {
  if (typeof path !== "string" || !path || path.includes("..") || path.startsWith("/") || path.includes("\\")) throw new Error("invalid character asset path");
  return new URL(path, baseUrl).pathname;
}

function resolveCharacterAsset(role, state = "idle") {
  const resolvedRole = role === "panel" ? (activeCharacter.presentation_states?.[state] || "panel") : role;
  return activeCharacter.assets?.[resolvedRole] || fallbackCharacterAsset;
}

function applyCharacterAssets(root = document) {
  for (const image of root.querySelectorAll("img[data-character-asset]")) {
    const role = image.dataset.characterAsset;
    image.src = resolveCharacterAsset(role, role === "panel" ? (ui.renderer.dataset.presentationState || "idle") : "idle");
    image.onerror = () => {
      image.onerror = null; image.src = fallbackCharacterAsset;
      if (role === "panel") document.querySelector(".asset-state").hidden = false;
    };
  }
}

async function loadCharacterProfile(characterId = "shion") {
  const profileUrl = characterProfiles[characterId];
  if (!profileUrl) throw new Error("character is not registered");
  const profileResponse = await fetch(profileUrl, {cache: "no-store"});
  if (!profileResponse.ok) throw new Error("character profile unavailable");
  const profile = await profileResponse.json();
  if (profile.character_id !== characterId || profile.renderer?.type !== "static_2d") throw new Error("invalid character profile");
  const manifestUrl = new URL(profile.renderer.manifest, new URL(profileUrl, location.origin)).pathname;
  const manifestResponse = await fetch(manifestUrl, {cache: "no-store"});
  if (!manifestResponse.ok) throw new Error("character asset manifest unavailable");
  const manifest = await manifestResponse.json();
  if (!manifest.owner_approved || manifest.status !== "official" || manifest.character_id !== characterId || manifest.asset_set_id !== profile.renderer.asset_set) throw new Error("character asset set is not Owner-approved");
  const manifestBase = new URL(".", new URL(manifestUrl, location.origin));
  const assets = Object.fromEntries(Object.entries(manifest.assets).map(([role, asset]) => [role, safeCharacterPath(manifestBase, asset.path)]));
  activeCharacter = {...profile, assets, presentation_states: manifest.presentation_states || {}};
  ui.renderer.dataset.assetSet = manifest.asset_set_id;
  document.querySelector(".asset-state").hidden = true;
  applyCharacterAssets();
}

function activeSession() { return sessions.find((session) => session.session_id === activeSessionId); }
function createSession() {
  const created = new Date().toISOString();
  return {session_id: createSessionId(), title: "New Chat", created_at: created, updated_at: created,
    model_alias: ui.model?.value || "gemma4_12b_heretic_ja_v2_manual", mode: ui.mode?.value || "minimal", draft: "", messages: []};
}
function persistSessions() {
  const drafts = Object.fromEntries(sessions.map((session) => [session.session_id, session.draft || ""]));
  try { sessionStorage.setItem(ephemeralKey, JSON.stringify({active_session_id: activeSessionId, drafts})); }
  catch { if (ui.connection) ui.connection.textContent = "Session storage full"; }
}
async function loadSessions() {
  let saved = null;
  try {
    saved = JSON.parse(sessionStorage.getItem(ephemeralKey) || "null");
  } catch { sessionStorage.removeItem(ephemeralKey); }
  const response = await fetch("/api/sessions", {cache: "no-store"});
  if (!response.ok) throw new Error("Persistence unavailable");
  sessions = (await response.json()).sessions.map((session) => ({...session, mode: session.conversation_mode, model_alias: null, draft: saved?.drafts?.[session.session_id] || "", messages: []}));
  activeSessionId = saved?.active_session_id;
  if (!sessions.length) {
    const session = createSession();
    const created = await fetch("/api/sessions", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: session.session_id, mode: session.mode})});
    if (!created.ok) throw new Error("Session creation failed");
    sessions = [session]; activeSessionId = session.session_id;
  } else if (!sessions.some((session) => session.session_id === activeSessionId)) {
    activeSessionId = sessions[0].session_id;
  }
  await hydrateSession(activeSessionId);
}
async function hydrateSession(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {cache: "no-store"});
  if (!response.ok) throw new Error("Session load failed");
  const data = await response.json(), session = sessions.find((item) => item.session_id === sessionId);
  session.title = data.title; session.mode = data.conversation_mode; session.created_at = data.created_at; session.updated_at = data.updated_at;
  session.messages = [];
  for (const item of data.messages) {
    if (item.role !== "assistant" || !item.versions?.length) {
      session.messages.push({role: item.role, content: item.parts, metadata: {message_id: item.message_id, created_at: item.created_at}, favorite: item.favorite, feedback: item.feedback});
      continue;
    }
    for (const version of item.versions) session.messages.push({role: "assistant", content: version.content,
      metadata: {message_id: item.message_id, response_version: version.version, created_at: version.created_at, model: {id: version.model_id, revision: version.model_revision}, generation: version.generation},
      regeneratable: version.version === item.active_version, favorite: item.favorite, feedback: item.feedback,
      previous_version: version.version !== item.active_version, version_candidate: item.versions.length > 1,
      selected_version: version.version === item.active_version, version_group: item.message_id, voice_artifacts: version.voice_artifacts || []});
  }
}
function renderSidebar() {
  ui.sessionList.replaceChildren();
  for (const session of [...sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at))) {
    const row = document.createElement("div"); row.className = "session-row";
    const button = document.createElement("button");
    button.type = "button"; button.className = "session-item";
    button.classList.toggle("current", session.session_id === activeSessionId);
    button.innerHTML = `<span></span><p>${escapeHtml(session.title)}<br><small>${new Date(session.created_at).toLocaleString()}</small></p>`;
    button.addEventListener("click", () => switchSession(session.session_id));
    const rename = actionButton("Rename", "rename-session", "Rename session");
    rename.addEventListener("click", () => beginRename(row, session));
    const archive = actionButton("Archive", "archive-session", "Archive conversation");
    archive.addEventListener("click", () => confirmArchive(session));
    row.append(button, rename, archive); ui.sessionList.appendChild(row);
  }
}

function beginRename(row, session) {
  const form = document.createElement("form"); form.className = "session-rename-form";
  const input = document.createElement("input"); input.type = "text"; input.maxLength = 80;
  input.value = session.title; input.setAttribute("aria-label", "Session title");
  const save = actionButton("Save", "save-session-title", "Save title"); save.type = "submit";
  const cancel = actionButton("Cancel", "cancel-session-title", "Cancel rename");
  cancel.addEventListener("click", () => renderSidebar());
  form.addEventListener("submit", async (event) => { event.preventDefault(); await renameSession(session, input.value); });
  form.append(input, save, cancel); row.replaceChildren(form); input.focus(); input.select();
}

async function renameSession(session, requestedTitle) {
  const title = requestedTitle.trim();
  if (!title) { renderSidebar(); return; }
  const response = await fetch("/api/sessions/rename", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: session.session_id, title})});
  const data = await response.json();
  if (!response.ok) { ui.connection.textContent = data.error || "Rename failed"; renderSidebar(); return; }
  session.title = data.title; renderSidebar();
}

function confirmArchive(session) {
  if (busy) return;
  ui.archiveDialog.dataset.sessionId = session.session_id;
  ui.archiveTitle.textContent = `「${session.title}」をArchiveしますか？`;
  ui.archiveDialog.showModal();
}

async function archiveSession(sessionId) {
  const session = sessions.find((item) => item.session_id === sessionId);
  if (!session) return;
  const response = await fetch("/api/sessions/archive", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId})});
  const data = await response.json();
  if (!response.ok) { ui.connection.textContent = data.error || "Archive failed"; return; }
  sessions = sessions.filter((item) => item.session_id !== sessionId);
  if (!sessions.length) {
    const replacement = createSession();
    const created = await fetch("/api/sessions", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: replacement.session_id, mode: replacement.mode})});
    if (!created.ok) { ui.connection.textContent = "New session creation failed"; return; }
    sessions.push(replacement);
  }
  if (activeSessionId === sessionId) activeSessionId = sessions[0].session_id;
  await hydrateSession(activeSessionId);
  persistSessions(); renderSession();
}

async function searchSessions() {
  const response = await fetch(`/api/sessions?q=${encodeURIComponent(ui.sessionSearch.value)}`, {cache: "no-store"});
  if (!response.ok) return;
  const result = await response.json();
  const known = new Map(sessions.map((session) => [session.session_id, session]));
  sessions = result.sessions.map((session) => ({...session, mode: session.conversation_mode, draft: known.get(session.session_id)?.draft || "", messages: known.get(session.session_id)?.messages || []}));
  renderSidebar();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
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
  return typeof content === "string" ? [{type: "text", text: content}] : (content || []);
}

function renderPart(part) {
  if (part.type === "text") return markdown(part.text || "");
  if (part.type === "image" && part.url) return `<img class="message-image" src="${escapeHtml(part.url)}" alt="${escapeHtml(part.alt || "Generated image")}">`;
  if (part.type === "audio" && part.url) return `<audio controls preload="metadata" src="${escapeHtml(part.url)}"></audio>`;
  const label = {attachment: "Attachment", tool_result: "Tool result"}[part.type] || "Unsupported content";
  return `<div class="typed-part"><strong>${label}</strong><br>${escapeHtml(part.name || part.summary || "Unavailable")}</div>`;
}

function plainText(content) {
  return contentParts(content).filter((part) => part.type === "text").map((part) => part.text).join("\n");
}

function typewriterText(bubble, content, keepFollowing) {
  const text = plainText(content), reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || !text || contentParts(content).some((part) => part.type !== "text")) {
    bubble.innerHTML = contentParts(content).map(renderPart).join("");
    return Promise.resolve();
  }
  bubble.textContent = "";
  bubble.classList.add("typewriter-caret");
  const segmenter = globalThis.Intl?.Segmenter ? new Intl.Segmenter("ja", {granularity: "grapheme"}) : null;
  const characters = segmenter ? Array.from(segmenter.segment(text), (item) => item.segment) : Array.from(text);
  let index = 0;
  return new Promise((resolve) => {
    const step = () => {
      const chunk = Math.max(1, Math.ceil(characters.length / 180));
      index = Math.min(characters.length, index + chunk);
      bubble.textContent = characters.slice(0, index).join("");
      if (keepFollowing) ui.messages.scrollTop = ui.messages.scrollHeight;
      else ui.jump.hidden = false;
      if (index < characters.length) setTimeout(step, 18);
      else {
        bubble.classList.remove("typewriter-caret");
        bubble.innerHTML = contentParts(content).map(renderPart).join("");
        resolve();
      }
    };
    step();
  });
}

function actionButton(label, action, title = label) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.title = title;
  button.dataset.action = action;
  return button;
}

function showDetails(metadata) {
  const details = [
    ["Message", metadata.message_id], ["Timestamp", metadata.created_at], ["Model", metadata.model?.id],
    ["Revision", metadata.model?.revision], ["Mode", metadata.mode],
    ["Latency", metadata.generation?.latency_ms != null ? `${metadata.generation.latency_ms} ms` : null],
    ["Context tokens", metadata.generation?.context_tokens], ["Persistence", "SQLite persistent history"],
  ].filter(([, value]) => value !== undefined && value !== null);
  alert(details.map(([key, value]) => `${key}: ${value}`).join("\n"));
}

async function loadVoiceMeta() {
  const response = await fetch("/api/voice/meta", {cache: "no-store"});
  voiceMeta = response.ok ? await response.json() : {state: "UNAVAILABLE", approved_presets: [], developer_models: {}};
  const approved = voiceMeta.approved_presets || [], developer = Object.entries(voiceMeta.developer_models || {});
  const previous = ui.voicePreset.value;
  const options = approved.map((item) => {
    const model = voiceMeta.developer_models?.[item.voice_model];
    const detail = model ? ` · ${model.name.replace(/ — Purchased Developer Candidate$/, "")} · ${item.style}` : "";
    return new Option(`${item.preset_name}${detail}`, `preset:${item.preset_name}`);
  });
  const f1 = developer.find(([id]) => id === "F1");
  if (ui.voiceDeveloper.checked) for (const [id, item] of developer) options.push(new Option(`Developer · ${item.name}`, `model:${id}`));
  ui.voicePreset.replaceChildren(...options);
  if (!options.length) ui.voicePreset.add(new Option("No approved SHION voice preset", ""));
  if (previous && [...ui.voicePreset.options].some((item) => item.value === previous)) ui.voicePreset.value = previous;
  else if (approved.some((item) => item.preset_name === "SHION Default")) ui.voicePreset.value = "preset:SHION Default";
  else if (approved.length) ui.voicePreset.value = `preset:${approved[0].preset_name}`;
  else if (f1 && ui.voiceDeveloper.checked) ui.voicePreset.value = "model:F1";
  updateVoiceStyles();
  ui.monitorPreset.textContent = ui.voicePreset.selectedOptions[0]?.textContent || "Not selected";
  const selectedDefault = approved.find((item) => item.preset_name === "SHION Default");
  ui.voiceStatus.textContent = selectedDefault
    ? `Voice AVAILABLE · SHION Default · Nene V3 · ${selectedDefault.style}`
    : `Voice ${voiceMeta.state || "UNAVAILABLE"} · no approved SHION voice preset`;
}

function updateVoiceStyles() {
  const previous = ui.voiceStyle.value, selection = ui.voicePreset.value;
  const modelId = selection.startsWith("model:") ? selection.slice(6) : null;
  const styles = modelId ? (voiceMeta.developer_models?.[modelId]?.styles || []) : [];
  ui.voiceStyle.replaceChildren(...styles.map((style) => new Option(style, style)));
  if (previous && styles.includes(previous)) ui.voiceStyle.value = previous;
  ui.voiceStyle.disabled = !modelId || !styles.length;
}

function voiceVersion(row) { return Number(row.dataset.version || row.dataset.responseVersion || "1"); }

async function generateVoice(row, record, retry = false) {
  const selection = ui.voicePreset.value;
  if (!selection) {
    ui.voicePanel.hidden = false; ui.voiceStatus.textContent = "Voice presetを選択してください";
    const notice = row.querySelector(".voice-inline") || document.createElement("div");
    notice.className = "voice-inline voice-selection-required"; notice.textContent = "Voice presetを選択してください。";
    row.querySelector(".message-body").append(notice); return;
  }
  const inline = row.querySelector(".voice-inline") || document.createElement("div");
  inline.className = "voice-inline"; inline.textContent = "Generating voice..."; row.querySelector(".message-body").append(inline);
  ui.voiceStatus.textContent = "Voice GENERATING"; ui.monitorVoice.textContent = "Generating";
  const payload = {session_id: activeSessionId, message_id: row.dataset.messageId, response_version: voiceVersion(row), retry};
  if (selection.startsWith("preset:")) payload.preset_id = selection.slice(7);
  else if (selection === "model:F1" || (ui.voiceDeveloper.checked && selection.startsWith("model:"))) {
    payload.developer_model = selection.slice(6);
    if (ui.voiceStyle.value) payload.developer_style = ui.voiceStyle.value;
  }
  try {
    const response = await fetch("/api/voice/generate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || "Voice generation failed");
    record.voice_artifacts = [...(record.voice_artifacts || []), data];
    const audio = document.createElement("audio"); audio.controls = true; audio.preload = "metadata"; audio.src = data.audio_url;
    audio.addEventListener("play", () => { if (activeAudio && activeAudio !== audio) activeAudio.pause(); activeAudio = audio; ui.monitorVoice.textContent = "Speaking"; ui.renderer.classList.add("speaking"); ui.renderer.dataset.presentationState = "speaking"; applyCharacterAssets(ui.renderer); });
    audio.addEventListener("ended", () => { ui.monitorVoice.textContent = "Ready"; ui.renderer.classList.remove("speaking"); ui.renderer.dataset.presentationState = "idle"; applyCharacterAssets(ui.renderer); });
    audio.addEventListener("pause", () => { if (!audio.ended) { ui.monitorVoice.textContent = "Ready"; ui.renderer.classList.remove("speaking"); ui.renderer.dataset.presentationState = "idle"; applyCharacterAssets(ui.renderer); } });
    const retryButton = actionButton("Retry Voice", "retry-voice"); retryButton.addEventListener("click", () => generateVoice(row, record, true));
    inline.replaceChildren(audio, retryButton, document.createTextNode(` ${data.voice_model_id} · ${data.duration}s · attempt ${data.attempt}`));
    ui.voiceStatus.textContent = "Voice READY"; ui.monitorVoice.textContent = "Ready";
    if (ui.voiceAutoplay.checked) audio.play().catch(() => { ui.voiceStatus.textContent = "Auto Play requested · tap Play to enable audio"; });
  } catch (error) {
    inline.textContent = `Voice failed: ${error.message} `;
    const retryButton = actionButton("Retry Voice", "retry-voice"); retryButton.addEventListener("click", () => generateVoice(row, record, true)); inline.append(retryButton);
    ui.voiceStatus.textContent = "Voice ERROR"; ui.monitorVoice.textContent = "Error";
  }
}

function addMessage(role, content, options = {}) {
  document.querySelector(".welcome")?.remove();
  const row = document.createElement("article");
  row.className = `message ${role}${options.temporary ? " generating-message" : ""}`;
  row.dataset.messageId = options.metadata?.message_id || createSessionId();
  const record = options.record || {role, content, metadata: options.metadata || {}, regeneratable: Boolean(options.regeneratable), favorite: false, feedback: null, previous_version: false};
  const identity = document.createElement("div");
  identity.className = "message-identity";
  identity.innerHTML = role === "assistant"
    ? '<img data-character-asset="avatar" alt=""><span>SHION</span>'
    : '<span class="user-mark">You</span>';
  const body = document.createElement("div");
  body.className = "message-body";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const followTypewriter = nearLatest();
  if (!options.typewriter) bubble.innerHTML = contentParts(content).map(renderPart).join("");
  body.appendChild(bubble);

  if (!options.temporary) {
    const actions = document.createElement("div");
    actions.className = "message-actions";
    const copy = actionButton("Copy", "copy");
    copy.addEventListener("click", async () => {
      await navigator.clipboard.writeText(plainText(content));
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = "Copy"; }, 1200);
    });
    actions.append(copy);
    if (role === "assistant") {
      const favorite = actionButton("☆", "favorite", "Favorite (session only)");
      favorite.addEventListener("click", async () => {
        const next = !row.classList.contains("favorite");
        const response = await fetch("/api/messages/favorite", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: activeSessionId, message_id: row.dataset.messageId, favorite: next})});
        if (!response.ok) return;
        row.classList.toggle("favorite", next); favorite.textContent = next ? "★" : "☆"; record.favorite = next;
      });
      const good = actionButton("Good", "good", "Good (session only)");
      const bad = actionButton("Bad", "bad", "Bad (session only)");
      for (const button of [good, bad]) button.addEventListener("click", async () => {
        const rating = button.classList.contains("active") ? null : button.dataset.action;
        const response = await fetch("/api/messages/feedback", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: activeSessionId, message_id: row.dataset.messageId, rating})});
        if (!response.ok) return;
        const active = button.classList.toggle("active", rating !== null);
        (button === good ? bad : good).classList.remove("active");
        if (!active) button.classList.remove("active");
        record.feedback = rating;
      });
      const details = actionButton("Details", "details");
      details.addEventListener("click", () => showDetails(options.metadata || {}));
      const readAloud = actionButton("Read Aloud", "read-aloud");
      readAloud.addEventListener("click", () => generateVoice(row, record));
      actions.append(favorite, good, bad, details, readAloud);
      if (options.regeneratable) {
        const regenerate = actionButton("Regenerate", "regenerate");
        regenerate.addEventListener("click", () => regenerateLast(row));
        actions.append(regenerate);
      }
      if (record.version_candidate) {
        const select = actionButton(record.selected_version ? "Selected" : "Use version", "select-version");
        select.disabled = Boolean(record.selected_version);
        select.addEventListener("click", () => selectResponseVersion(row, record));
        actions.append(select);
      }
    }
    body.appendChild(actions);
  }
  row.append(identity, body);
  applyCharacterAssets(row);
  row.classList.toggle("favorite", Boolean(record.favorite));
  row.classList.toggle("previous-version", Boolean(record.previous_version));
  row.classList.toggle("selected-version", Boolean(record.selected_version));
  if (record.version_group) row.dataset.versionGroup = record.version_group;
  row.dataset.version = String(record.metadata?.response_version || options.metadata?.version || 1);
  if (record.favorite) row.querySelector("[data-action=favorite]").textContent = "★";
  if (record.feedback) row.querySelector(`[data-action=${record.feedback}]`)?.classList.add("active");
  if (role === "assistant" && record.voice_artifacts?.length) {
    const latest = record.voice_artifacts[record.voice_artifacts.length - 1], inline = document.createElement("div"); inline.className = "voice-inline";
    const audio = document.createElement("audio"); audio.controls = true; audio.preload = "metadata"; audio.src = `/api/voice/artifacts/${latest.artifact_id}`;
    audio.addEventListener("play", () => { if (activeAudio && activeAudio !== audio) activeAudio.pause(); activeAudio = audio; });
    const retryButton = actionButton("Retry Voice", "retry-voice"); retryButton.addEventListener("click", () => generateVoice(row, record, true));
    inline.append(audio, retryButton, document.createTextNode(` ${latest.voice_model_id} · ${latest.duration}s · attempt ${latest.attempt}`)); body.append(inline);
  }
  ui.messages.appendChild(row);
  row.typewriterDone = options.typewriter ? typewriterText(bubble, content, followTypewriter) : Promise.resolve();
  messageCount += options.temporary ? 0 : 1;
  updateSessionInfo();
  if (nearLatest()) ui.messages.scrollTop = ui.messages.scrollHeight;
  else ui.jump.hidden = false;
  if (!options.temporary && options.persist !== false) {
    const session = activeSession();
    session.messages.push(record);
    session.updated_at = new Date().toISOString();
    persistSessions(); renderSidebar();
  }
  return row;
}

function setStatus(state) {
  ui.status.textContent = state === "Loading model" ? "Loading model..." : state;
  ui.dot.className = "";
  const key = state.toLowerCase();
  if (key === "ready") ui.dot.classList.add("ready");
  else if (key === "generating" || key === "loading model" || key === "connecting") ui.dot.classList.add("generating");
  else if (key === "error" || key === "offline") ui.dot.classList.add("error");
  const ready = state === "Ready";
  ui.monitorConversation.textContent = state;
  ui.renderer.dataset.presentationState = state === "Generating" || state === "Loading model" ? "generating" : "idle";
  applyCharacterAssets(ui.renderer);
  ui.renderer.classList.toggle("generating", state === "Generating" || state === "Loading model");
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
  if (activeSession() && !activeSession().model_alias) { activeSession().model_alias = data.model_alias; persistSessions(); }
  ui.summary.textContent = `Model: ${data.display_name} · Mode: ${ui.mode.options[ui.mode.selectedIndex].text}`;
  ui.badge.hidden = !/Experimental|Third-party/i.test(data.provenance || "");
  ui.monitorModel.textContent = data.display_name || data.model_alias || "Unavailable";
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
  updateSessionInfo();
}

function renderSubsystems(capabilities = {}, history = {}, voice = {}) {
  ui.subsystem.textContent = `Conversation READY · History ${history.state || "EPHEMERAL"} · Voice ${voice.state || "UNAVAILABLE"} · Image DISABLED · Vision DISABLED · Memory ${capabilities.long_term_memory ? "READY" : "DISABLED"}`;
  if (!ui.renderer.classList.contains("speaking") && ui.voiceStatus.textContent !== "Voice GENERATING") ui.monitorVoice.textContent = voice.state || "Unavailable";
}

function updateSessionInfo() {
  const session = activeSession();
  if (!session) return;
  ui.session.textContent = `Session ${activeSessionId.slice(0, 16)}… · ${messageCount} messages · ${session.mode} · persistent history · started ${new Date(session.created_at).toLocaleTimeString()}`;
}

async function poll(initializing = false) {
  try {
    const response = await fetch("/api/status", {cache: "no-store"});
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try { detail = (await response.json()).error || detail; } catch { /* non-JSON error */ }
      throw new Error(detail);
    }
    const data = await response.json();
    if (!data.state) throw new Error("status response has no model state");
    populateModels(data.models || []);
    setStatus(data.state);
    ui.connection.textContent = reconnecting ? "Reconnected" : "Connected";
    reconnecting = false;
    renderSubsystems(data.capabilities || {}, data.history || {}, data.voice || {});
    if (data.history?.state === "UNAVAILABLE") ui.connection.textContent = `Persistence unavailable: ${data.history.error || "database error"}`;
    if (data.model_alias) {
      ui.model.value = data.model_alias;
      renderModelInfo(data);
    }
  } catch (error) {
    reconnecting = true;
    setStatus("Offline");
    ui.connection.textContent = "Reconnecting";
    ui.summary.textContent = `${initializing ? "Initialization failed" : "Connection failed"}: ${error?.message || "unknown error"}`;
  }
}

async function stopGeneration() {
  if (!busy) return;
  ui.send.disabled = true;
  ui.send.textContent = "Stopping...";
  try {
    await fetch("/api/stop", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: activeSessionId})});
  } finally {
    ui.send.disabled = false;
  }
}

async function requestChat(message) {
  const response = await fetch("/api/chat", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({session_id: activeSessionId, mode: ui.mode.value, message}),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Generation failed.");
  return data;
}

async function send(event) {
  event.preventDefault();
  if (busy) { await stopGeneration(); return; }
  const message = ui.input.value.trim();
  if (!message) return;
  lastUserMessage = message;
  activeSession().draft = ""; persistSessions();
  busy = true;
  ui.input.value = "";
  ui.input.style.height = "auto";
  addMessage("user", message);
  const waiting = addMessage("assistant", "SHION is thinking...", {temporary: true});
  setStatus("Generating");
  try {
    const data = await requestChat(message);
    waiting.remove();
    if (data.session_title) activeSession().title = data.session_title;
    const responseRow = addMessage("assistant", data.response || "Generation stopped.", {metadata: {...data, response_version: 1}, regeneratable: true, typewriter: true});
    await responseRow.typewriterDone;
    if (ui.voiceAutoplay.checked) generateVoice(responseRow, activeSession().messages[activeSession().messages.length - 1]);
  } catch (error) {
    waiting.remove();
    const row = addMessage("assistant", error.message || "Generation failed.", {metadata: {created_at: new Date().toISOString()}});
    const retry = actionButton("Retry", "retry");
    retry.addEventListener("click", () => retryLast(row));
    row.querySelector(".message-actions")?.append(retry);
  } finally {
    busy = false;
    await poll();
    ui.input.focus();
  }
}

async function regenerateLast(oldRow) {
  if (busy || oldRow !== document.querySelector(".message.assistant:last-of-type")) return;
  busy = true;
  setStatus("Generating");
  try {
    const response = await fetch("/api/regenerate", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: activeSessionId, mode: ui.mode.value, message_id: oldRow.dataset.messageId}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Regeneration failed.");
    oldRow.classList.add("previous-version");
    const oldRecord = activeSession().messages.find((item) => item.metadata?.message_id === oldRow.dataset.messageId);
    const versionGroup = oldRecord?.version_group || oldRecord?.metadata?.message_id || createSessionId();
    if (oldRecord) { oldRecord.previous_version = true; oldRecord.version_candidate = true; oldRecord.selected_version = false; oldRecord.version_group = versionGroup; }
    oldRow.querySelector("[data-action=regenerate]")?.remove();
    const newRecord = {role: "assistant", content: data.response, metadata: {...data, response_version: data.version}, regeneratable: true, favorite: false, feedback: null, previous_version: false, version_candidate: true, selected_version: true, version_group: versionGroup, voice_artifacts: []};
    const replacement = addMessage("assistant", data.response, {metadata: data, regeneratable: true, record: newRecord, typewriter: true});
    replacement.dataset.version = String(Number(oldRow.dataset.version || "1") + 1);
    await replacement.typewriterDone;
    persistSessions();
  } catch (error) {
    addMessage("assistant", error.message || "Regeneration failed.");
  } finally {
    busy = false;
    await poll();
  }
}

async function selectResponseVersion(row, record) {
  const response = await fetch("/api/response/select", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: activeSessionId, mode: ui.mode.value, response: plainText(record.content)})});
  if (!response.ok) { addMessage("assistant", "Response version selection failed."); return; }
  for (const item of activeSession().messages.filter((item) => item.version_group === record.version_group)) item.selected_version = item === record;
  for (const candidate of ui.messages.querySelectorAll(`[data-version-group="${record.version_group}"]`)) {
    const selected = candidate === row;
    candidate.classList.toggle("selected-version", selected);
    const button = candidate.querySelector("[data-action=select-version]");
    if (button) { button.disabled = selected; button.textContent = selected ? "Selected" : "Use version"; }
  }
  persistSessions();
}

async function retryLast(row) {
  if (!lastUserMessage || busy) return;
  row.remove();
  busy = true;
  setStatus("Generating");
  try {
    const data = await requestChat(lastUserMessage);
    const responseRow = addMessage("assistant", data.response, {metadata: data, regeneratable: true, typewriter: true});
    await responseRow.typewriterDone;
  } catch (error) {
    addMessage("assistant", error.message || "Retry failed.");
  } finally {
    busy = false;
    await poll();
  }
}

async function newChat() {
  if (busy) return;
  const session = createSession();
  const response = await fetch("/api/sessions", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: session.session_id, mode: session.mode})});
  if (!response.ok) { ui.connection.textContent = "Persistence unavailable"; return; }
  sessions.push(session); activeSessionId = session.session_id;
  persistSessions(); renderSession();
}

function renderSession() {
  const session = activeSession();
  ui.messages.innerHTML = session.messages.length ? "" : '<div class="welcome"><p class="eyebrow">NEW CONVERSATION</p><h2>新しい対話を始めましょう。</h2><p>会話はローカルのPersistent Historyへ安全に保存されます。Long-Term MemoryやDatasetには自動転送されません。</p></div>';
  messageCount = 0;
  ui.mode.value = session.mode;
  ui.input.value = session.draft || "";
  for (const record of session.messages) addMessage(record.role, record.content, {metadata: record.metadata, regeneratable: record.regeneratable, record, persist: false});
  renderSidebar(); updateSessionInfo();
}

async function switchSession(sessionId) {
  if (busy || sessionId === activeSessionId) return;
  activeSession().draft = ui.input.value;
  activeSessionId = sessionId;
  await hydrateSession(sessionId);
  persistSessions(); renderSession();
  const desiredModel = activeSession().model_alias;
  if (desiredModel && currentModel?.model_alias && desiredModel !== currentModel.model_alias) {
    setStatus("Loading model");
    const response = await fetch("/api/model", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: activeSessionId, model_alias: desiredModel})});
    if (!response.ok) addMessage("assistant", "Saved session model is unavailable.");
  }
}

function nearLatest() {
  return ui.messages.scrollHeight - ui.messages.scrollTop - ui.messages.clientHeight < 120;
}

const workspacePages = {
  room: ["SHION Room", "Coming Soon", "Character interaction and relationship systems are not implemented in Phase A–C."],
  voice: ["Voice Lab", "Foundation", "Full Voice Console migration is deferred. Current SHION Default and playback controls remain available in Chat."],
  image: ["Image Lab", "Not Integrated", "No image-generation backend is enabled or started."],
  characters: ["Characters", "Foundation", "SHION remains the active Character. Multi-character editing is not implemented."],
  memory: ["Memory", "Disabled", "Long-Term Memory is a separate, default-disabled domain and receives no automatic conversation data."],
  system: ["System", "Status only", "Runtime, History and Voice status remain visible in Chat. No privileged system tools are enabled."],
  settings: ["Settings", "Foundation", "Workspace settings are reserved. Voice and model controls remain in Chat for this phase."],
};

function closeMobilePanels() {
  ui.sidebar.classList.remove("mobile-open"); ui.characterPanel.classList.remove("mobile-open");
  ui.mobileNav.setAttribute("aria-expanded", "false"); ui.mobileCharacter.setAttribute("aria-expanded", "false"); ui.scrim.hidden = true;
}

function renderRoute() {
  const route = location.hash.replace(/^#\//, "") || "chat";
  const page = route === "chat" || workspacePages[route] ? route : "chat";
  ui.workspace.dataset.page = page;
  for (const link of ui.nav.querySelectorAll("[data-route]")) link.classList.toggle("active", link.dataset.route === page);
  const isChat = page === "chat";
  ui.chatPage.hidden = !isChat; ui.pageSlot.hidden = isChat; document.querySelector(".chat-nav").hidden = !isChat;
  if (!isChat) {
    const [title, status, description] = workspacePages[page];
    ui.pageSlot.innerHTML = `<article><p class="panel-eyebrow">PROJECT SHION WORKSPACE</p><span class="page-status">${escapeHtml(status)}</span><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p><p>このページは将来のroute / component boundaryのみです。未実装機能を利用可能にはしていません。</p></article>`;
    if (page === "characters") {
      const master = document.createElement("img"); master.className = "character-master"; master.dataset.characterAsset = "master"; master.alt = "Official Static 2D SHION master";
      ui.pageSlot.querySelector("article").append(master); applyCharacterAssets(ui.pageSlot);
    }
  }
  closeMobilePanels();
}

ui.form.addEventListener("submit", send);
ui.input.addEventListener("compositionstart", () => { composing = true; });
ui.input.addEventListener("compositionend", () => { composing = false; });
ui.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !composing) {
    event.preventDefault();
    ui.form.requestSubmit();
  }
});
ui.input.addEventListener("input", () => {
  ui.input.style.height = "auto";
  ui.input.style.height = `${Math.min(ui.input.scrollHeight, 220)}px`;
  activeSession().draft = ui.input.value; activeSession().updated_at = new Date().toISOString(); persistSessions();
});
ui.messages.addEventListener("scroll", () => { ui.jump.hidden = nearLatest(); });
ui.jump.addEventListener("click", () => { ui.messages.scrollTop = ui.messages.scrollHeight; ui.jump.hidden = true; });
ui.reset.addEventListener("click", newChat);
ui.sidebarReset.addEventListener("click", newChat);
ui.sessionSearch.addEventListener("input", searchSessions);
ui.archiveDialog.addEventListener("close", async () => { if (ui.archiveDialog.returnValue === "confirm") await archiveSession(ui.archiveDialog.dataset.sessionId); });
ui.voiceSettings.addEventListener("click", () => { ui.voicePanel.hidden = !ui.voicePanel.hidden; });
ui.voiceDeveloper.addEventListener("change", loadVoiceMeta);
ui.voicePreset.addEventListener("change", () => { updateVoiceStyles(); ui.monitorPreset.textContent = ui.voicePreset.selectedOptions[0]?.textContent || "Not selected"; });
ui.voiceAutoplay.addEventListener("change", () => { try { sessionStorage.setItem("shion-voice-autoplay", ui.voiceAutoplay.checked ? "1" : "0"); } catch {} });
ui.mode.addEventListener("change", async () => {
  activeSession().mode = ui.mode.value; activeSession().updated_at = new Date().toISOString(); persistSessions();
  if (currentModel) renderModelInfo(currentModel); await poll();
});
ui.model.addEventListener("change", async () => {
  if (busy) return;
  setStatus("Loading model");
  try {
    const response = await fetch("/api/model", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: activeSessionId, model_alias: ui.model.value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Model switching failed.");
    activeSession().model_alias = ui.model.value; activeSession().updated_at = new Date().toISOString(); persistSessions();
  } catch (error) {
    addMessage("assistant", error.message || "Model switching failed.");
  }
  await poll();
});
ui.mobileNav.addEventListener("click", () => { const open = !ui.sidebar.classList.contains("mobile-open"); closeMobilePanels(); ui.sidebar.classList.toggle("mobile-open", open); ui.mobileNav.setAttribute("aria-expanded", String(open)); ui.scrim.hidden = !open; });
ui.mobileCharacter.addEventListener("click", () => { const open = !ui.characterPanel.classList.contains("mobile-open"); closeMobilePanels(); ui.characterPanel.classList.toggle("mobile-open", open); ui.mobileCharacter.setAttribute("aria-expanded", String(open)); ui.scrim.hidden = !open; });
ui.characterClose.addEventListener("click", closeMobilePanels); ui.scrim.addEventListener("click", closeMobilePanels);
window.addEventListener("hashchange", renderRoute);

async function initialize() {
  renderRoute();
  try { await loadCharacterProfile("shion"); }
  catch (error) { document.querySelector(".asset-state").hidden = false; applyCharacterAssets(); console.warn("Official character asset fallback:", error.message); }
  setStatus("Loading model");
  try { await loadSessions(); renderSession(); }
  catch (error) { ui.connection.textContent = `Persistence unavailable: ${error.message}`; sessions = [createSession()]; activeSessionId = sessions[0].session_id; renderSession(); }
  await poll(true);
  ui.voiceAutoplay.checked = sessionStorage.getItem("shion-voice-autoplay") === "1";
  await loadVoiceMeta();
}
initialize();
setInterval(() => poll(false), 1500);
