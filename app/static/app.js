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
  floating: $("floating-assistant"), floatingToggle: $("floating-toggle"), floatingCard: $("floating-card"), floatingClose: $("floating-close"), floatingForm: $("floating-form"), floatingInput: $("floating-input"), floatingMessages: $("floating-messages"),
  connectionActions: $("connection-actions"), connectionRetry: $("connection-retry"), connectionReload: $("connection-reload"), currentCharacter: $("current-character"),
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
let autoFollow = true;
let programmaticScroll = false;
let workspacePreferences = {layout: "auto", typewriter: true, auto_scroll: true, enter_behavior: "desktop-send", markdown: true};
try { workspacePreferences = {...workspacePreferences, ...JSON.parse(sessionStorage.getItem("shion-workspace-preferences:v1") || "{}")}; } catch {}
let voiceMeta = {approved_presets: [], developer_models: {}};
let activeAudio = null;
const pendingVoiceRequests = new Map();
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
    button.title = session.title;
    button.innerHTML = `<span></span><p>${escapeHtml(session.title)}</p>`;
    button.addEventListener("click", () => switchSession(session.session_id));
    const menu = document.createElement("details"); menu.className = "session-menu";
    const summary = document.createElement("summary"); summary.setAttribute("aria-label", `Conversation menu for ${session.title}`); summary.textContent = "⋯";
    const commands = document.createElement("div"); commands.className = "session-menu-popover";
    const rename = actionButton("Rename", "rename-session", "Rename session");
    rename.addEventListener("click", () => beginRename(row, session));
    const archive = actionButton("Archive", "archive-session", "Archive conversation");
    archive.addEventListener("click", () => confirmArchive(session));
    for (const label of ["Pin / Unpin", "Favorite", "Export", "Duplicate / Branch", "Delete"]) {
      const unavailable = actionButton(label, "unavailable-session-action", `${label} is not implemented`); unavailable.disabled = true; commands.append(unavailable);
    }
    commands.prepend(rename); commands.append(archive); menu.append(summary, commands);
    row.append(button, menu); ui.sessionList.appendChild(row);
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

function compactAssistantResponse(value, limit = 520) {
  const text = String(value || "").trim();
  if (text.length <= limit) return text;
  const clipped = text.slice(0, limit);
  const boundary = Math.max(clipped.lastIndexOf("。"), clipped.lastIndexOf("！"), clipped.lastIndexOf("？"), clipped.lastIndexOf("\n"));
  return `${clipped.slice(0, boundary > limit * .55 ? boundary + 1 : limit).trim()}\n\n続きはFull Chatで話そう。`;
}

function typewriterText(bubble, content, keepFollowing) {
  const text = plainText(content), reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || !workspacePreferences.typewriter || !text || contentParts(content).some((part) => part.type !== "text")) {
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
      if (keepFollowing && autoFollow) scrollToLatest();
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
  const generation = metadata.generation || {};
  const details = [
    ["Message", metadata.message_id], ["Timestamp", metadata.created_at], ["Model", metadata.model?.id],
    ["Revision", metadata.model?.revision], ["Mode", metadata.mode],
    ["Latency", generation.latency_ms != null ? `${generation.latency_ms} ms` : null],
    ["Input tokens", generation.total_input_tokens ?? generation.context_tokens],
    ["History included", generation.conversation_history_tokens_included],
    ["History omitted", generation.conversation_history_tokens_omitted],
    ["System tokens", generation.system_tokens], ["Character tokens", generation.character_context_tokens],
    ["Memory tokens", generation.memory_tokens], ["Memory retrieval", generation.memory_retrieval_ms != null ? `${generation.memory_retrieval_ms} ms` : null],
    ["Current message tokens", generation.current_message_tokens],
    ["Output tokens", generation.output_tokens], ["Tokens/sec", generation.tokens_per_second],
    ["Stop reason", generation.stop_reason], ["Output budget", generation.output_budget_tokens],
    ["Self-correction review", generation.self_correction_review],
    ["Assistant answers withheld", generation.assistant_history_withheld],
    ["Private channel filtered", generation.private_channel_filtered],
    ["Decoding mode", generation.decoding_mode],
    ["Prompt build", generation.prompt_build_ms != null ? `${generation.prompt_build_ms} ms` : null],
    ["Persistence", "SQLite persistent history"],
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
  inline.className = "voice-inline"; inline.textContent = "会話生成完了後に音声を生成します"; row.querySelector(".message-body").append(inline);
  ui.voiceStatus.textContent = "Voice WAITING_FOR_GPU"; ui.monitorVoice.textContent = "Waiting for GPU";
  const payload = {session_id: activeSessionId, message_id: row.dataset.messageId, response_version: voiceVersion(row), retry};
  if (selection.startsWith("preset:")) payload.preset_id = selection.slice(7);
  else if (selection === "model:F1" || (ui.voiceDeveloper.checked && selection.startsWith("model:"))) {
    payload.developer_model = selection.slice(6);
    if (ui.voiceStyle.value) payload.developer_style = ui.voiceStyle.value;
  }
  const requestKey = `${payload.message_id}:${payload.response_version}:${payload.preset_id || `${payload.developer_model}:${payload.developer_style || ""}`}`;
  if (pendingVoiceRequests.has(requestKey)) return pendingVoiceRequests.get(requestKey).promise;
  const controller = new AbortController();
  try {
    const promise = fetch("/api/voice/generate", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload), signal: controller.signal});
    pendingVoiceRequests.set(requestKey, {controller, payload, promise});
    const response = await promise;
    const data = await response.json(); if (!response.ok) throw new Error(data.error || "Voice generation failed");
    record.voice_artifacts = [...(record.voice_artifacts || []), data];
    const audio = document.createElement("audio"); audio.controls = true; audio.preload = "metadata"; audio.src = data.audio_url;
    audio.addEventListener("play", () => { if (activeAudio && activeAudio !== audio) activeAudio.pause(); activeAudio = audio; ui.monitorVoice.textContent = "Speaking"; ui.monitorConversation.textContent = "SPEAKING"; $("monitor-message").textContent = "声で話してるよ。"; ui.renderer.classList.add("speaking"); ui.renderer.dataset.presentationState = "speaking"; applyCharacterAssets(ui.renderer); });
    audio.addEventListener("ended", () => { ui.monitorVoice.textContent = "Ready"; ui.monitorConversation.textContent = "READY"; $("monitor-message").textContent = "ここにいるよ。話したくなったら、いつでも呼んで。"; ui.renderer.classList.remove("speaking"); ui.renderer.dataset.presentationState = "idle"; applyCharacterAssets(ui.renderer); });
    audio.addEventListener("pause", () => { if (!audio.ended) { ui.monitorVoice.textContent = "Ready"; ui.monitorConversation.textContent = "READY"; ui.renderer.classList.remove("speaking"); ui.renderer.dataset.presentationState = "idle"; applyCharacterAssets(ui.renderer); } });
    const retryButton = actionButton("Retry Voice", "retry-voice"); retryButton.addEventListener("click", () => generateVoice(row, record, true));
    inline.replaceChildren(audio, retryButton, document.createTextNode(` ${data.voice_model_id} · ${data.duration}s · attempt ${data.attempt}`));
    ui.voiceStatus.textContent = "Voice READY"; ui.monitorVoice.textContent = "Ready";
    if (autoFollow) scrollToLatest();
    if (ui.voiceAutoplay.checked) audio.play().catch(() => { ui.voiceStatus.textContent = "Auto Play requested · tap Play to enable audio"; });
  } catch (error) {
    if (error.name === "AbortError") { inline.textContent = "Voice request cancelled"; return; }
    inline.textContent = `Voice failed: ${error.message} `;
    const retryButton = actionButton("Retry Voice", "retry-voice"); retryButton.addEventListener("click", () => generateVoice(row, record, true)); inline.append(retryButton);
    ui.voiceStatus.textContent = "Voice ERROR"; ui.monitorVoice.textContent = "Error";
  } finally {
    pendingVoiceRequests.delete(requestKey);
  }
}

async function cancelQueuedVoice(sessionId, filter = {}) {
  const matches = ({payload}) => payload.session_id === sessionId
    && (filter.message_id === undefined || payload.message_id === filter.message_id)
    && (filter.response_version === undefined || payload.response_version === filter.response_version);
  for (const request of [...pendingVoiceRequests.values()].filter(matches)) request.controller.abort();
  try {
    await fetch("/api/voice/queue/cancel", {method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({session_id:sessionId,...filter})});
  } catch {}
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
  const followTypewriter = autoFollow;
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
  if (autoFollow) scrollToLatest();
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
  ui.monitorConversation.textContent = state === "Generating" || state === "Loading model" ? "THINKING" : state.toUpperCase();
  $("monitor-message").textContent = state === "Generating" ? "考え中。ちゃんと返すから、少し待ってて。" : state === "Ready" ? "ここにいるよ。話したくなったら、いつでも呼んで。" : "SHIONの準備状態を確認しています。";
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
  ui.monitorModel.textContent = ui.mode.options[ui.mode.selectedIndex]?.text || "Normal";
  const fields = [
    ["Model", data.model_identity], ["Base", data.base_model_label], ["Experiment", data.experiment],
    ["Adapter", data.adapter_status], ["LoRA targets", data.adapter_target_count],
    ["Dataset", data.dataset_label], ["Training", data.training_epochs ? `${data.training_epochs} epochs` : null],
    ["LoRA", data.lora_config], ["Status", data.evaluation_status],
    ["Recommended mode", data.recommended_mode === "neutral" ? "Neutral Conversation" : data.recommended_mode],
    ["Repository", data.repo_id], ["Revision", data.revision], ["Parent", data.parent_model],
    ["Base origin:", data.base_origin || "not specified"], ["Provenance", data.provenance],
    ["Model change", data.modification_type], ["Quantization", data.quantization],
    ["Context", data.context_limit], ["VRAM allocated", `${data.gpu_memory_allocated_mib} MiB`],
  ];
  ui.info.replaceChildren();
  for (const [label, value] of fields) {
    if (value === undefined || value === null || value === "") continue;
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
    setStatus(busy && data.state === "Ready" ? "Generating" : data.state);
    ui.connection.textContent = reconnecting ? "Reconnected" : "Connected";
    ui.connectionActions.hidden = true;
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
    ui.connectionActions.hidden = false;
    ui.summary.textContent = `${initializing ? "Initialization failed" : "Connection failed"}: ${error?.message || "unknown error"}`;
  }
}

async function stopGeneration() {
  if (!busy) return;
  ui.send.disabled = true;
  ui.send.textContent = "Stopping...";
  try {
    await cancelQueuedVoice(activeSessionId);
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
  autoFollow = workspacePreferences.auto_scroll;
  ui.input.value = "";
  ui.input.style.height = "auto";
  addMessage("user", message);
  const waiting = addMessage("assistant", "SHION THINKING", {temporary: true});
  setStatus("Generating");
  try {
    const data = await requestChat(message);
    waiting.remove();
    if (data.session_title) activeSession().title = data.session_title;
    const responseRow = addMessage("assistant", data.response || "Generation stopped.", {metadata: {...data, response_version: 1}, regeneratable: true, typewriter: true});
    await responseRow.typewriterDone;
    if (data.memory_candidate) ui.subsystem.textContent = `Memory candidate created · ${data.memory_candidate.type} · Owner review required`;
    else if (data.memory_candidate_rejected) ui.subsystem.textContent = data.memory_candidate_rejected;
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
  await cancelQueuedVoice(activeSessionId, {message_id: oldRow.dataset.messageId, response_version: voiceVersion(oldRow)});
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
  const previous = activeSession().messages.find((item) => item.version_group === record.version_group && item.selected_version);
  if (previous?.metadata?.message_id) await cancelQueuedVoice(activeSessionId, {message_id: previous.metadata.message_id, response_version: previous.metadata.response_version || 1});
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
  if (activeSessionId) await cancelQueuedVoice(activeSessionId);
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
  autoFollow = true; scrollToLatest();
  renderSidebar(); updateSessionInfo();
}

async function switchSession(sessionId) {
  if (busy || sessionId === activeSessionId) return;
  await cancelQueuedVoice(activeSessionId);
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

function scrollToLatest() {
  programmaticScroll = true;
  ui.messages.scrollTop = ui.messages.scrollHeight;
  ui.jump.hidden = true;
  requestAnimationFrame(() => { programmaticScroll = false; });
}

const workspacePages = {
  home: ["Project SHION", "Personal AI Assistant", "SHIONと会話、Voice、Character、Systemの現在地を確認できます。"],
  room: ["SHION Room", "Coming Soon", "Character interaction and relationship systems are not implemented in Phase A–C."],
  voice: ["Voice Lab", "Foundation", "Full Voice Console migration is deferred. Current SHION Default and playback controls remain available in Chat."],
  image: ["Image Lab", "Not Integrated", "No image-generation backend is enabled or started."],
  characters: ["Characters", "Foundation", "SHION remains the active Character. Multi-character editing is not implemented."],
  memory: ["Memory", "Owner Control", "Long-Term Memory stores explicit Owner records and reviewed candidates. Automatic promotion is OFF."],
  system: ["System", "Status only", "Runtime, History and Voice status remain visible in Chat. No privileged system tools are enabled."],
  settings: ["Settings", "Foundation", "Workspace settings are reserved. Voice and model controls remain in Chat for this phase."],
};

function metricCard(label, value, detail = "") { return `<div class="metric-card"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value ?? "Unavailable")}</strong><p>${escapeHtml(detail)}</p></div>`; }

async function renderHomePage() {
  const response = await fetch("/api/dashboard", {cache: "no-store"}); if (!response.ok) return;
  const data = await response.json(), article = ui.pageSlot.querySelector("article");
  const recent = data.recent_conversations || [], latest = recent[0];
  article.innerHTML = `<div class="dashboard-hero home-presence"><img data-character-asset="panel" alt="SHION"><div><p class="panel-eyebrow">PERSONAL AI ASSISTANT SHION</p><h2>おかえり、お兄さん。</h2><p class="assistant-note">${data.runtime.state === "Ready" ? "準備できてるよ。前の続きでも、新しい話でもどうぞ。" : "いま準備中。状態はChatで確認できるよ。"}</p><div class="home-primary-actions">${latest ? `<button data-session-link="${escapeHtml(latest.session_id)}">Continue conversation</button>` : ""}<button id="home-new-chat">New Chat</button></div></div></div><section class="quick-access-grid"><a href="#/room"><strong>SHION Room</strong><span>紫苑と触れ合う空間 · Foundation</span></a><a href="#/voice"><strong>Voice Lab</strong><span>Nene V3 / Bright</span></a><a href="#/characters"><strong>Character</strong><span>Official SHION profile</span></a><a href="#/chat"><strong>Chat</strong><span>${escapeHtml(data.runtime.model_alias || "Heretic default")}</span></a></section><section><h3>Recent conversations</h3><div class="recent-list">${recent.length ? recent.map(item => `<button data-session-link="${escapeHtml(item.session_id)}"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.updated_at)}</small></button>`).join("") : "<p>まだ会話はありません。</p>"}</div></section>`;
  applyCharacterAssets(article);
  for (const button of article.querySelectorAll("[data-session-link]")) button.addEventListener("click", async () => { location.hash = "#/chat"; await switchSession(button.dataset.sessionLink); });
  article.querySelector("#home-new-chat")?.addEventListener("click", async () => { await newChat(); location.hash = "#/chat"; });
}

async function renderCharactersPage() {
  const response = await fetch("/api/characters/shion", {cache: "no-store"}); if (!response.ok) return;
  const character = await response.json(), article = ui.pageSlot.querySelector("article");
  article.innerHTML = `<div class="character-profile-page"><img class="character-master" data-character-asset="master" alt="Official SHION master"><div><p class="panel-eyebrow">CHARACTER MANAGEMENT</p><h2>${escapeHtml(character.display_name)} <span>${escapeHtml(character.display_name_ja)}</span></h2><p>現在正式登録されているPersonal AI CharacterはSHIONだけです。Header avatarが将来のselector入口になります。</p><button type="button" disabled>Active Character · SHION</button><dl class="profile-facts"><div><dt>Static 2D</dt><dd>${escapeHtml(character.asset_set.id)} · ${escapeHtml(character.asset_set.version)}</dd></div><div><dt>Conversation model</dt><dd>${escapeHtml(character.default_model)}</dd></div><div><dt>Voice</dt><dd>${escapeHtml(character.default_voice.preset_id)} · Nene V3 · ${escapeHtml(character.default_voice.style)}</dd></div><div><dt>Renderer</dt><dd>${escapeHtml(character.renderer.type)} · Live2D/3D replaceable</dd></div><div><dt>Subsystems</dt><dd>Conversation READY · Voice AVAILABLE · Owner Memory DISABLED</dd></div></dl><p class="feature-note">NONO / 美月は未登録です。未確定情報をfake表示しません。</p></div></div>`;
  applyCharacterAssets(article);
}

async function renderSystemPage() {
  const response = await fetch("/api/system", {cache: "no-store"}); if (!response.ok) return;
  const data = await response.json(), article = ui.pageSlot.querySelector("article");
  const meter = (label, used, total, detail) => `<div class="system-meter"><div><strong>${label}</strong><span>${escapeHtml(detail)}</span></div><progress max="${Number(total) || 1}" value="${Number(used) || 0}"></progress></div>`;
  const ramUsed = data.ram.total_mib && data.ram.available_mib ? data.ram.total_mib - data.ram.available_mib : 0;
  const storageUsed = data.storage.total_gib - data.storage.free_gib;
  article.innerHTML = `<div class="system-console"><header><div><p class="panel-eyebrow">LOCAL MONITORING CONSOLE</p><h2>System</h2></div><button id="system-refresh" type="button">Refresh</button></header><p>手動更新の最小telemetry。秘密情報・credential・private pathは表示しません。</p><div class="core-status"><div><span>SHION CORE</span><strong>${escapeHtml(data.server.state)}</strong></div><div><span>CONVERSATION</span><strong>${escapeHtml(data.conversation.state || data.sqlite.state)}</strong></div><div><span>VOICE</span><strong>${escapeHtml(data.voice.state)}</strong></div><div><span>IMAGE</span><strong>${escapeHtml(data.image.state)}</strong></div><div><span>MEMORY</span><strong>FOUNDATION · DISABLED</strong></div></div><section class="resource-meters">${meter("GPU VRAM", data.gpu.used_mib, data.gpu.total_mib, data.gpu.state === "AVAILABLE" ? `${data.gpu.used_mib} / ${data.gpu.total_mib} MiB` : data.gpu.state)}${meter("RAM", ramUsed, data.ram.total_mib, data.ram.state === "AVAILABLE" ? `${ramUsed} / ${data.ram.total_mib} MiB` : data.ram.state)}${meter("Storage", storageUsed, data.storage.total_gib, `${storageUsed.toFixed(1)} / ${data.storage.total_gib} GiB`)}</section><div class="system-foot">SQLite ${escapeHtml(data.sqlite.state)} · schema ${escapeHtml(data.sqlite.schema_version || "—")} · Voice preset SHION Default · Processes ${escapeHtml(data.processes.shion_server)}</div></div>`;
  article.querySelector(".core-status div:last-child strong").textContent = `${data.memory.state} · AUTO PROMOTION OFF`;
  article.querySelector("#system-refresh").addEventListener("click", renderSystemPage);
}

function renderRoomPage() {
  const article = ui.pageSlot.querySelector("article");
  article.innerHTML = `<div class="room-shell" data-room-background="night"><img data-character-asset="master" alt="SHION in her room"><div class="room-copy"><p class="panel-eyebrow">SHION ROOM · INTERACTION FOUNDATION</p><h2>紫苑の部屋</h2><p>SHION本人と触れ合い、いつでもPersonal AI Assistantとの会話へ戻れる空間です。Characters pageは管理、Roomは体験という役割に分離しています。</p><button id="room-talk">話しかける</button><div class="room-shortcuts"><button id="room-greeting" type="button">「おかえり」</button><button disabled>Short interaction · Coming Soon</button></div><div class="room-slots"><span>Character status · Ready</span><span>Outfit slot · Foundation</span><span>Room customization · Foundation</span><span>Relationship feature · Not integrated</span></div></div></div>`;
  applyCharacterAssets(article);
  article.querySelector("#room-talk").addEventListener("click", () => { location.hash = "#/chat"; });
  article.querySelector("#room-greeting").addEventListener("click", () => { ui.floating.hidden = false; ui.floatingCard.hidden = false; ui.floatingToggle.setAttribute("aria-expanded", "true"); ui.floatingMessages.insertAdjacentHTML("beforeend", "<p>おかえり、お兄さん。今日はどうする？</p>"); });
}

async function memoryMutation(path, method = "POST", body = {}) {
  const response = await fetch(path, {method, headers:{"Content-Type":"application/json"}, body:JSON.stringify({session_id:activeSessionId,...body})});
  const data = await response.json(); if (!response.ok) throw new Error(data.error || "Memory operation failed"); return data;
}

async function renderMemoryPage(selectedTab = "remembered") {
  const article = ui.pageSlot.querySelector("article"), response = await fetch("/api/memory", {cache:"no-store"});
  if (!response.ok) { article.innerHTML = '<p class="feature-note">Memory backend unavailable. Chat remains available.</p>'; return; }
  const data = await response.json(), all = data.memories || [];
  const tabs = {remembered:"Remembered",candidates:"Candidates",temporary:"Temporary",character:"Character",archived:"Archived",settings:"Settings"};
  const filtered = all.filter(item => selectedTab === "remembered" ? item.status === "active" && item.type !== "temporary"
    : selectedTab === "candidates" ? item.status === "candidate" : selectedTab === "temporary" ? item.type === "temporary"
    : selectedTab === "character" ? item.scope === "character" || item.type === "character_specific"
    : selectedTab === "archived" ? ["archived","rejected","expired"].includes(item.status) : false);
  const options = values => values.map(value=>`<option>${value}</option>`).join("");
  const card = item => `<article class="memory-record" data-memory-id="${escapeHtml(item.id)}"><header><div><span class="memory-type">${escapeHtml(item.type)}</span><strong>${escapeHtml(item.content)}</strong></div>${item.pinned ? '<span class="page-status">PINNED</span>' : ""}</header><dl><div><dt>Character</dt><dd>${escapeHtml(item.character_id)}</dd></div><div><dt>Scope</dt><dd>${escapeHtml(item.scope)}</dd></div><div><dt>Status</dt><dd>${escapeHtml(item.status)}</dd></div><div><dt>Importance</dt><dd>${item.importance}/5</dd></div><div><dt>Created</dt><dd>${escapeHtml(item.created_at)}</dd></div><div><dt>Last used</dt><dd>${escapeHtml(item.last_used_at || "Never")}</dd></div><div><dt>Expires</dt><dd>${escapeHtml(item.expires_at || "Never")}</dd></div><div><dt>Source</dt><dd>${escapeHtml(item.source_conversation_id || "Owner UI")} / ${escapeHtml(item.source_message_id || "direct")}</dd></div><div><dt>Version</dt><dd>${item.version}</dd></div></dl><div class="memory-actions">${item.status === "candidate" ? '<button data-memory-action="approve">Approve</button><button data-memory-action="reject">Reject</button>' : ""}<button data-memory-action="edit">Edit</button><button data-memory-action="pin">${item.pinned ? "Unpin" : "Pin"}</button>${item.status === "active" ? '<button data-memory-action="archive">Archive</button>' : ["archived","rejected","expired"].includes(item.status) ? '<button data-memory-action="restore">Restore</button>' : ""}<button data-memory-action="scope">Change scope</button><button data-memory-action="character">Change character</button><button class="danger" data-memory-action="delete">Delete</button></div></article>`;
  const records = `<form id="memory-create" class="memory-create"><textarea name="content" maxlength="2000" required placeholder="Owner-approved memory"></textarea><select name="type">${options(["preference","profile","project","relationship","decision","temporary","character_specific","system"])}</select><select name="scope">${options(["global_owner","character","project","conversation","temporary"])}</select><input name="character_id" value="shion" maxlength="40"><label>Expires (optional)<input name="expires_at" type="datetime-local"></label><button type="submit">Add active memory</button></form><section class="memory-records">${filtered.length ? filtered.map(card).join("") : "<p>No memory records in this view.</p>"}</section>`;
  const settings = '<section class="memory-settings"><h3>Settings</h3><label><input type="checkbox" disabled> Automatic permanent promotion</label><p>Default OFF. Enabling remains an Owner Gate.</p><p>Retrieval: deterministic local text relevance · Vector/embedding retrieval deferred.</p></section>';
  article.innerHTML = `<div class="foundation-header"><div><p class="panel-eyebrow">OWNER MEMORY · PHASE F</p><h2>Memory</h2><p>Conversation Historyとは分離されています。候補はOwner承認までcontextへ入りません。</p></div><span class="page-status">AUTOMATIC PROMOTION OFF</span></div><nav class="memory-tabs">${Object.entries(tabs).map(([id,label])=>`<button class="${id===selectedTab?"active":""}" data-memory-tab="${id}">${label}</button>`).join("")}</nav><p id="memory-error" class="feature-note">${escapeHtml(data.last_error || "Owner-controlled · Explainable · Reversible")}</p>${selectedTab === "settings" ? settings : records}<aside class="memory-policy"><strong>Privacy boundary</strong><p>Passwords, API keys, tokens, private keys and credential-like content are rejected. Assistant or external content cannot become active Owner Memory.</p></aside>`;
  for (const button of article.querySelectorAll("[data-memory-tab]")) button.addEventListener("click",()=>renderMemoryPage(button.dataset.memoryTab));
  article.querySelector("#memory-create")?.addEventListener("submit", async event => { event.preventDefault(); const form=new FormData(event.currentTarget); try { await memoryMutation("/api/memory","POST",Object.fromEntries(form)); await renderMemoryPage(selectedTab); } catch(error){article.querySelector("#memory-error").textContent=error.message;} });
  for (const button of article.querySelectorAll("[data-memory-action]")) button.addEventListener("click", async () => {
    const record=button.closest("[data-memory-id]"), id=record.dataset.memoryId, action=button.dataset.memoryAction;
    try {
      if (["approve","reject","archive","restore"].includes(action)) await memoryMutation(`/api/memory/${id}/${action}`);
      else if (action === "edit") { const content=prompt("Edit memory",record.querySelector("strong").textContent); if(content!==null)await memoryMutation(`/api/memory/${id}`,"PATCH",{content}); }
      else if (action === "pin") await memoryMutation(`/api/memory/${id}`,"PATCH",{pinned:button.textContent==="Pin"});
      else if (action === "scope") { const scope=prompt("Scope: global_owner / character / project / conversation / temporary"); if(scope)await memoryMutation(`/api/memory/${id}`,"PATCH",{scope}); }
      else if (action === "character") { const character_id=prompt("Character ID","shion"); if(character_id)await memoryMutation(`/api/memory/${id}`,"PATCH",{character_id}); }
      else if (action === "delete") { const confirmation=prompt("Hard Delete is permanent. Type DELETE to confirm."); if(confirmation==="DELETE")await memoryMutation(`/api/memory/${id}`,"DELETE",{confirm:"DELETE"}); }
      await renderMemoryPage(selectedTab);
    } catch(error){article.querySelector("#memory-error").textContent=error.message;}
  });
}

function saveWorkspacePreferences() {
  sessionStorage.setItem("shion-workspace-preferences:v1", JSON.stringify(workspacePreferences));
  applyLayoutPreference();
}

function applyLayoutPreference() {
  ui.workspace.classList.toggle("layout-force-mobile", workspacePreferences.layout === "mobile");
  ui.workspace.classList.toggle("layout-force-desktop", workspacePreferences.layout === "desktop");
}

function renderSettingsPage() {
  const article = ui.pageSlot.querySelector("article");
  const category = (name, body) => `<section class="settings-section"><h3>${name}</h3>${body}</section>`;
  article.innerHTML = `<div class="foundation-header"><div><p class="panel-eyebrow">WORKSPACE PREFERENCES</p><h2>Settings</h2><p>利用可能な項目だけがこのbrowser sessionへ反映されます。未統合backend設定は明示的に無効です。</p></div><span class="page-status">FOUNDATION</span></div><div class="settings-grid">${category("General", `<label>Language<select disabled><option>日本語</option></select></label><label>Startup page<select disabled><option>Chat · fixed</option></select></label><label>Layout<select id="setting-layout"><option value="auto">Auto</option><option value="mobile">Mobile</option><option value="desktop">Desktop</option></select></label>`)}${category("Chat", `<label><input id="setting-typewriter" type="checkbox"> Typewriter presentation</label><label><input id="setting-autoscroll" type="checkbox"> Auto-scroll after send</label><label>Enter behavior<select id="setting-enter"><option value="desktop-send">Desktop sends · Mobile newline</option><option value="newline">Always newline</option></select></label><label><input type="checkbox" checked disabled> Markdown rendering</label>`)}${category("Character", `<label>Active character<select disabled><option>SHION · only registered character</option></select></label><label>Renderer<select disabled><option>Official Static 2D</option></select></label><label><input type="checkbox" checked disabled> Presence panel</label>`)}${category("Model", `<label>Default conversation model<input value="gemma4_12b_heretic_ja_v2_manual" readonly></label><p>UI・backend parser・new session fallbackは同じaliasです。</p>`)}${category("Voice", `<label>Default preset<input value="SHION Default · Nene V3 · Bright" readonly></label><p>Auto PlayはChat Voice panelで変更できます。</p>`)}${category("Memory", `<label><input type="checkbox" disabled> Enable Long-Term Memory</label><p>Disabled · Owner approval policy required.</p>`)}${category("Storage", `<p>Conversation usage: Systemで確認</p><p>Voice artifact usage: Voice Labで確認</p>`)}${category("Privacy & Security", `<p>Localhost-only · Tailscale Host/Origin policy active.</p><p>Future Companion permissions: screen, window title, selected text and app state are individually default OFF.</p>`)}${category("Advanced", `<button type="button" disabled>Developer settings · Not integrated</button>`)}</div>`;
  const layout = article.querySelector("#setting-layout"), typewriter = article.querySelector("#setting-typewriter"), autoscroll = article.querySelector("#setting-autoscroll"), enter = article.querySelector("#setting-enter");
  const memorySetting = article.querySelector(".settings-section:nth-child(6)");
  if (memorySetting) memorySetting.innerHTML = '<h3>Memory</h3><label><input type="checkbox" checked disabled> Owner-controlled Long-Term Memory</label><p>Automatic permanent promotion remains OFF.</p>';
  layout.value = workspacePreferences.layout; typewriter.checked = workspacePreferences.typewriter; autoscroll.checked = workspacePreferences.auto_scroll; enter.value = workspacePreferences.enter_behavior;
  layout.addEventListener("change", () => { workspacePreferences.layout = layout.value; saveWorkspacePreferences(); });
  typewriter.addEventListener("change", () => { workspacePreferences.typewriter = typewriter.checked; saveWorkspacePreferences(); });
  autoscroll.addEventListener("change", () => { workspacePreferences.auto_scroll = autoscroll.checked; saveWorkspacePreferences(); });
  enter.addEventListener("change", () => { workspacePreferences.enter_behavior = enter.value; saveWorkspacePreferences(); });
}

async function renderVoiceLabPage() {
  const article = ui.pageSlot.querySelector("article");
  const parameter = (name, label, min, max, step, value, low, high) => `<div class="lab-parameter" data-parameter="${name}"><header><label for="lab-${name}">${label}</label><output>${value}</output><button type="button" data-reset="${name}">Reset</button></header><input id="lab-${name}" name="${name}" type="range" min="${min}" max="${max}" step="${step}" value="${value}"><div class="range-labels"><span>${low}</span><span>${high}</span></div></div>`;
  article.innerHTML = `<div class="foundation-header"><div><p class="panel-eyebrow">VOICE SYSTEM · PHASE G</p><h2>Nene V3 · Bright</h2><p>SHION DefaultとGpuResourceGateを共有するpersistent Voice subsystem。</p></div><span class="page-status">PERSISTENT</span></div><p class="feature-note">Display text is immutable. Character-aware pronunciation rules transform only the TTS layer.</p><form id="voice-lab-form" class="lab-form"><section class="pronunciation-lab"><h3>Voice Lab</h3><label>Conversation display text<textarea id="lab-display" maxlength="500">ざこの発音を確認するよ。</textarea></label><label>TTS transformation preview<textarea id="lab-tts" maxlength="500">ざこの発音を確認するよ。</textarea></label><p id="lab-preview">Replacement preview: 変更なし</p><button id="lab-apply-dictionary" type="button">Test pronunciation</button></section><section><h3>Voice Character Map</h3><div class="parameter-grid">${parameter("style_weight","Expression",0,2,.1,1,"Calm","Expressive")}${parameter("length","Tempo",.7,1.5,.05,1,"Fast","Slow")}${parameter("pitch_scale","Pitch",.8,1.2,.05,1,"Low","High")}${parameter("intonation_scale","Intonation",.5,1.5,.05,1,"Calm","Expressive")}</div></section><div class="lab-actions"><button type="submit">Generate Voice</button><button id="lab-retry" type="button">Retry current settings</button></div></form><div id="lab-result" class="lab-result" aria-live="polite"></div><section class="pronunciation-dictionary"><header><h3>Pronunciation Dictionary · SHION</h3></header><form id="pronunciation-form" class="dictionary-form"><input id="pronunciation-original" maxlength="200" placeholder="Original text" required><input id="pronunciation-replacement" maxlength="200" placeholder="Pronunciation / replacement" required><input id="pronunciation-priority" type="number" min="-1000" max="1000" value="100" aria-label="Priority"><button type="submit">Add rule</button></form><div id="pronunciation-rules"></div></section><section class="artifact-history"><header><div><h3>Voice Artifact Index</h3><p id="lab-usage">Loading…</p></div><span>Cross-session · newest first</span></header><div id="lab-history"><p>Loading persistent artifacts…</p></div></section>`;
  const formElement = article.querySelector("#voice-lab-form"), display = article.querySelector("#lab-display"), tts = article.querySelector("#lab-tts"), preview = article.querySelector("#lab-preview");
  let artifacts = [], rules = [];
  const request = async (url, options={}) => { const response=await fetch(url,{cache:"no-store",...options}); const data=await response.json(); if(!response.ok)throw new Error(data.error||"Voice request failed"); return data; };
  const updatePreview = () => { preview.textContent = display.value === tts.value ? "Replacement preview: 変更なし" : `Replacement preview: 「${display.value}」→ TTS「${tts.value}」`; };
  display.addEventListener("input", updatePreview); tts.addEventListener("input", updatePreview);
  for (const control of article.querySelectorAll(".lab-parameter")) {
    const input = control.querySelector("input"), output = control.querySelector("output"); input.addEventListener("input", () => { output.value = input.value; });
    control.querySelector("button").addEventListener("click", () => { input.value = "1"; output.value = "1"; });
  }
  const restore = artifact => { for (const [key, value] of Object.entries(artifact.parameters||{})) { const input = formElement.elements[key]; if(input){input.value=value;input.dispatchEvent(new Event("input"));} } display.value=artifact.source_text||"";tts.value=artifact.tts_text||artifact.source_text||"";updatePreview(); };
  const renderArtifacts = () => {
    const history = article.querySelector("#lab-history"), total = artifacts.reduce((sum, item) => sum + (item.file_size_bytes || 0), 0); article.querySelector("#lab-usage").textContent = `${artifacts.length} artifacts · ${total.toLocaleString()} bytes`;
    history.innerHTML = artifacts.length ? artifacts.map((item, index) => `<article class="artifact-card ${item.available?"":"missing"}"><header><time>${escapeHtml(item.created_at)}</time><button type="button" data-favorite="${index}" aria-label="Favorite artifact">${item.favorite ? "★" : "☆"}</button></header><p>${escapeHtml(item.text_preview || "")}</p><dl><div><dt>Source</dt><dd>${escapeHtml(item.source_type)}</dd></div><div><dt>Model / Style</dt><dd>${escapeHtml(item.voice_model_id)} · ${escapeHtml(item.voice_style)}</dd></div><div><dt>Duration / Latency</dt><dd>${item.duration}s · ${item.latency_seconds}s</dd></div><div><dt>Size</dt><dd>${Number(item.file_size_bytes || 0).toLocaleString()} bytes</dd></div></dl>${item.available?`<audio controls preload="metadata" src="${escapeHtml(item.audio_url)}"></audio>`:'<p class="feature-note">WAV missing · metadata is recoverable. Retry to regenerate.</p>'}<div class="artifact-actions"><button type="button" data-retry="${index}">Retry</button><button type="button" data-restore="${index}">Restore parameters</button><button type="button" data-delete="${index}">Delete</button></div></article>`).join("") : "<p>No persistent Voice artifacts yet.</p>";
    for (const button of history.querySelectorAll("[data-restore]")) button.addEventListener("click", () => restore(artifacts[Number(button.dataset.restore)]));
    for (const button of history.querySelectorAll("[data-retry]")) button.addEventListener("click", async()=>{button.disabled=true;try{await request(`/api/voice/artifacts/${artifacts[Number(button.dataset.retry)].artifact_id}/retry`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId()})});await loadArtifacts();}catch(error){alert(error.message);}finally{button.disabled=false;}});
    for (const button of history.querySelectorAll("[data-favorite]")) button.addEventListener("click", async()=>{const artifact=artifacts[Number(button.dataset.favorite)];await request(`/api/voice/artifacts/${artifact.artifact_id}/favorite`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),favorite:!artifact.favorite})});await loadArtifacts();});
    for (const button of history.querySelectorAll("[data-delete]")) button.addEventListener("click",async()=>{const artifact=artifacts[Number(button.dataset.delete)];if(!confirm(`Delete Voice artifact?\n${artifact.text_preview}\nWAV and metadata will be removed.`))return;await request(`/api/voice/artifacts/${artifact.artifact_id}`,{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),confirm:"DELETE"})});await loadArtifacts();});
  };
  const loadArtifacts=async()=>{artifacts=(await request("/api/voice/artifacts?character_id=shion")).artifacts;renderArtifacts();};
  const renderRules=()=>{article.querySelector("#pronunciation-rules").innerHTML=rules.length?rules.map((rule,index)=>`<div class="dictionary-rule"><label><input type="checkbox" data-rule-toggle="${index}" ${rule.enabled?"checked":""}> enabled</label><strong>${escapeHtml(rule.original_text)}</strong><span>→ ${escapeHtml(rule.replacement)}</span><small>priority ${rule.priority}</small><button type="button" data-rule-edit="${index}">Edit</button><button type="button" data-rule-delete="${index}">Delete</button></div>`).join(""):"<p>No SHION pronunciation rules.</p>";for(const button of article.querySelectorAll("[data-rule-toggle]"))button.addEventListener("change",async()=>{const rule=rules[Number(button.dataset.ruleToggle)];await request(`/api/voice/pronunciations/${rule.rule_id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),enabled:button.checked})});await loadRules();});for(const button of article.querySelectorAll("[data-rule-edit]"))button.addEventListener("click",async()=>{const rule=rules[Number(button.dataset.ruleEdit)],replacement=prompt("Pronunciation / replacement",rule.replacement);if(replacement===null)return;await request(`/api/voice/pronunciations/${rule.rule_id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),replacement})});await loadRules();});for(const button of article.querySelectorAll("[data-rule-delete]"))button.addEventListener("click",async()=>{const rule=rules[Number(button.dataset.ruleDelete)];if(!confirm(`Delete pronunciation rule “${rule.original_text}”?`))return;await request(`/api/voice/pronunciations/${rule.rule_id}`,{method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),confirm:"DELETE"})});await loadRules();});};
  const loadRules=async()=>{rules=(await request("/api/voice/pronunciations?character_id=shion")).rules;renderRules();};
  formElement.addEventListener("submit", async event => {
    event.preventDefault(); const form = new FormData(event.currentTarget), result = article.querySelector("#lab-result"); result.innerHTML = '<span class="thinking-label">WAITING_FOR_GPU · 会話生成完了後に音声を生成します</span>';
    const response = await fetch("/api/voice/lab/generate", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),tts_text:tts.value,parameters:Object.fromEntries(["style_weight","length","pitch_scale","intonation_scale"].map(key=>[key,Number(form.get(key))]))})}); const data=await response.json();
    if(!response.ok){result.innerHTML=`<p>${escapeHtml(data.error||"Voice generation failed")}</p><button id="lab-error-retry" type="button">Retry</button>`; result.querySelector("button").addEventListener("click",()=>formElement.requestSubmit()); return;}
    await loadArtifacts(); result.innerHTML=`<audio controls autoplay src="${escapeHtml(data.audio_url)}"></audio><p>${escapeHtml(data.voice_preset_id)} · ${escapeHtml(data.voice_style)} · ${data.latency_seconds}s · ${data.duration}s</p>`;
  });
  article.querySelector("#lab-apply-dictionary").addEventListener("click",async()=>{const data=await request("/api/voice/pronunciation/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),text:display.value,character_id:"shion"})});tts.value=data.tts_text;updatePreview();});
  article.querySelector("#pronunciation-form").addEventListener("submit",async event=>{event.preventDefault();await request("/api/voice/pronunciations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_id:createSessionId(),original_text:article.querySelector("#pronunciation-original").value,replacement:article.querySelector("#pronunciation-replacement").value,priority:Number(article.querySelector("#pronunciation-priority").value),character_id:"shion",enabled:true})});event.currentTarget.reset();article.querySelector("#pronunciation-priority").value="100";await loadRules();});
  article.querySelector("#lab-retry").addEventListener("click", () => formElement.requestSubmit());
  await Promise.all([loadRules(),loadArtifacts()]);
}

function closeMobilePanels() {
  ui.sidebar.classList.remove("mobile-open"); ui.characterPanel.classList.remove("mobile-open");
  ui.mobileNav.setAttribute("aria-expanded", "false"); ui.mobileCharacter.setAttribute("aria-expanded", "false"); ui.scrim.hidden = true;
}

async function renderRoute() {
  const route = location.hash.replace(/^#\//, "") || "chat";
  const page = route === "chat" || workspacePages[route] ? route : "chat";
  ui.workspace.dataset.page = page;
  for (const link of ui.nav.querySelectorAll("[data-route]")) link.classList.toggle("active", link.dataset.route === page);
  const isChat = page === "chat";
  ui.floating.hidden = isChat;
  ui.chatPage.hidden = !isChat; ui.pageSlot.hidden = isChat; document.querySelector(".chat-nav").hidden = !isChat;
  if (!isChat) {
    const [title, status, description] = workspacePages[page];
    ui.pageSlot.innerHTML = `<article><p class="panel-eyebrow">PROJECT SHION WORKSPACE</p><span class="page-status">${escapeHtml(status)}</span><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p><p>このページは将来のroute / component boundaryのみです。未実装機能を利用可能にはしていません。</p></article>`;
    if (page === "home") await renderHomePage();
    else if (page === "characters") await renderCharactersPage();
    else if (page === "system") await renderSystemPage();
    else if (page === "voice") await renderVoiceLabPage();
    else if (page === "room") renderRoomPage();
    else if (page === "memory") renderMemoryPage();
    else if (page === "settings") renderSettingsPage();
  }
  closeMobilePanels();
}

ui.form.addEventListener("submit", send);
ui.input.addEventListener("compositionstart", () => { composing = true; });
ui.input.addEventListener("compositionend", () => { composing = false; });
ui.input.addEventListener("keydown", (event) => {
  const mobile = matchMedia("(max-width: 760px)").matches || workspacePreferences.layout === "mobile";
  const sendsOnEnter = workspacePreferences.enter_behavior === "desktop-send" && !mobile;
  if (event.key === "Enter" && sendsOnEnter && !event.shiftKey && !event.isComposing && !composing) {
    event.preventDefault();
    ui.form.requestSubmit();
  }
});
ui.input.addEventListener("input", () => {
  ui.input.style.height = "auto";
  ui.input.style.height = `${Math.min(ui.input.scrollHeight, 220)}px`;
  activeSession().draft = ui.input.value; activeSession().updated_at = new Date().toISOString(); persistSessions();
});
ui.messages.addEventListener("scroll", () => {
  if (programmaticScroll) return;
  autoFollow = nearLatest(); ui.jump.hidden = autoFollow;
});
ui.jump.addEventListener("click", () => { autoFollow = true; scrollToLatest(); });
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
ui.currentCharacter.addEventListener("click", () => { location.hash = "#/characters"; });
ui.connectionRetry.addEventListener("click", () => poll(true));
ui.connectionReload.addEventListener("click", () => location.reload());
window.addEventListener("hashchange", renderRoute);
ui.floatingToggle.addEventListener("click", () => { const open=ui.floatingCard.hidden; ui.floatingCard.hidden=!open; ui.floatingToggle.setAttribute("aria-expanded",String(open)); if(open)ui.floatingInput.focus(); });
ui.floatingClose.addEventListener("click", () => { ui.floatingCard.hidden=true; ui.floatingToggle.setAttribute("aria-expanded","false"); });
ui.floatingForm.addEventListener("submit", async event => {
  event.preventDefault(); const message = ui.floatingInput.value.trim(); if (!message) return;
  ui.floatingInput.value = ""; const owner = document.createElement("p"); owner.className = "owner"; owner.textContent = message; ui.floatingMessages.append(owner);
  const thinking = document.createElement("p"); thinking.className = "thinking-label"; thinking.textContent = "SHION THINKING"; ui.floatingMessages.append(thinking); ui.floatingCard.dataset.state = "thinking";
  const page = location.hash.replace(/^#\//, "") || "home";
  const context = {page, selected_voice_model: page === "voice" ? "nene_v3_candidate" : undefined, selected_style: page === "voice" ? "Bright" : undefined, subsystem_status: ui.subsystem.textContent};
  try {
    const response = await fetch("/api/assistant", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({session_id:"workspace-assistant-shion", message, context})}); const data = await response.json();
    thinking.className = ""; thinking.textContent = response.ok ? compactAssistantResponse(data.response) : (data.error || "Assistant unavailable");
  } catch { thinking.className = ""; thinking.innerHTML = 'Connection failed. <button type="button">Retry from this page</button>'; thinking.querySelector("button").addEventListener("click", () => { ui.floatingInput.value = message; ui.floatingForm.requestSubmit(); }); }
  finally { ui.floatingCard.dataset.state = "ready"; ui.floatingMessages.scrollTop = ui.floatingMessages.scrollHeight; }
});

async function initialize() {
  applyLayoutPreference();
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
