"""
script.py — the entire client application, as a Python string. There is no
app.js on disk; this constant is inlined into the page by page.py. Written in
plain JS (what a browser can execute) but authored, owned, and served as
Python — you never touch a .js file to work on this app.
"""

JS = r"""
(() => {
  "use strict";
  const API = "";
  const state = {
    token: localStorage.getItem("gateway_token") || null,
    me: null,
    chats: [], activeChatId: null, messagesByChat: {},
    ws: null, wsRetryMs: 1000,
    providers: [],
    currentMode: "gateway",
    alphaScope: "foryou",
    alphaItems: [],
    activeDrawerPulseId: null,
    platformSettings: {},
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
  const esc = (s) => (s || "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
  const timeAgo = (ts) => {
    if (!ts) return "";
    const diff = Date.now()/1000 - ts;
    if (diff < 60) return "now";
    if (diff < 3600) return `${Math.floor(diff/60)}m`;
    if (diff < 86400) return `${Math.floor(diff/3600)}h`;
    if (diff < 604800) return `${Math.floor(diff/86400)}d`;
    return new Date(ts*1000).toLocaleDateString();
  };
  const clockTime = (ts) => new Date(ts*1000).toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" });

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
    const res = await fetch(API + path, { ...opts, headers });
    let data = {}; try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = reject;
      r.readAsDataURL(file);
    });
  }
  async function uploadFile(file) {
    const dataUrl = await fileToBase64(file);
    const res = await api("/api/upload", { method:"POST", body: JSON.stringify({ filename:file.name, data:dataUrl }) });
    return res.url;
  }
  function mediaKindOf(file) {
    if (file.type.startsWith("video")) return "video";
    if (file.type.startsWith("audio")) return "audio";
    return "image";
  }
  function openModal(id) { $(`#${id}`).classList.remove("hidden"); }
  function closeModal(id) { $(`#${id}`).classList.add("hidden"); }

  // ============================================================ AUTH
  const referralUsername = new URLSearchParams(location.search).get("ref");
  function showAuth() {
    $("#auth-screen").classList.remove("hidden"); $("#app").classList.add("hidden");
    const banner = $("#auth-referral-banner");
    if (referralUsername) {
      banner.textContent = `Invited by @${referralUsername} — sign up to chat with them`;
      banner.classList.remove("hidden");
      $$(".auth-tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === "register"));
      $("#login-form").classList.add("hidden");
      $("#register-form").classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }
  function showApp() { $("#auth-screen").classList.add("hidden"); $("#app").classList.remove("hidden"); }

  $$(".auth-tab").forEach((tab) => tab.addEventListener("click", () => {
    $$(".auth-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const which = tab.dataset.tab;
    $("#login-form").classList.toggle("hidden", which !== "login");
    $("#register-form").classList.toggle("hidden", which !== "register");
  }));

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault(); $("#login-error").textContent = "";
    try {
      const res = await api("/api/login", { method:"POST", body: JSON.stringify({
        username: $("#login-username").value.trim(), password: $("#login-password").value }) });
      onAuthed(res);
    } catch (err) { $("#login-error").textContent = err.message; }
  });
  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault(); $("#register-error").textContent = "";
    try {
      const res = await api("/api/register", { method:"POST", body: JSON.stringify({
        username: $("#reg-username").value.trim(), display_name: $("#reg-display").value.trim(),
        password: $("#reg-password").value }) });
      onAuthed(res);
      if (referralUsername) connectToReferrer(referralUsername);
    } catch (err) { $("#register-error").textContent = err.message; }
  });
  async function connectToReferrer(username) {
    try {
      const search = await api(`/api/users?q=${encodeURIComponent(username)}`);
      const match = search.users.find((u) => u.username.toLowerCase() === username.toLowerCase());
      if (!match) return; // referrer isn't findable (renamed, deleted) — fail quietly, not fatal to signup
      await api("/api/contacts", { method:"POST", body: JSON.stringify({ contact_id: match.id }) });
      const chats = await api("/api/chats"); state.chats = chats.chats; renderChatList();
      const chat = state.chats.find((c) => c.other_user && c.other_user.id === match.id);
      if (chat) { switchMode("gateway"); switchSubtab("gateway", "chats"); openChat(chat.id); }
    } catch (_) { /* non-fatal — the new account still works even if this fails */ }
  }
  $("#settings-logout-btn").addEventListener("click", () => {
    if (state.me) writeSavedAccounts(loadSavedAccounts().filter((x) => x.username !== state.me.username));
    localStorage.removeItem("gateway_token"); state.token = null;
    if (state.ws) state.ws.close();
    closeModal("settings-screen"); $("#settings-screen").classList.add("hidden");
    showAuth();
  });
  function onAuthed({ token, user }) {
    state.token = token; state.me = user;
    localStorage.setItem("gateway_token", token);
    bootApp();
  }

  // ============================================================ PARTICLE BACKGROUND
  if (window.GatewayParticles) {
    GatewayParticles.init($("#particle-canvas"));
    GatewayParticles.setMode("auth");
  }
  function bindScrollRatio(el) {
    if (!el || el._scrollBound) return;
    el._scrollBound = true;
    el.addEventListener("scroll", () => {
      const max = el.scrollHeight - el.clientHeight;
      GatewayParticles && GatewayParticles.notifyScrollRatio(max > 0 ? el.scrollTop / max : 0);
    });
  }
  function bindAllScrollables() {
    ["chat-list", "thread-messages", "status-list", "ig-explore-grid", "posts-list",
     "x-search-results", "x-notif-list", "settings-body"].forEach((id) => bindScrollRatio($(`#${id}`)));
    $$(".ig-feed-page, .x-home-page, .profile-page, #pulse-feed").forEach(bindScrollRatio);
  }

  // ============================================================ THEME
  const THEME_PREMIUM = { midnight:false, light:false, amoled:true, sunset:true, ocean:true };
  function applyTheme(theme) { document.documentElement.dataset.theme = theme || "midnight"; }
  function renderThemePicker() {
    $$("#theme-grid .theme-swatch").forEach((sw) => {
      const id = sw.dataset.themeId;
      const isPremiumTheme = THEME_PREMIUM[id];
      const locked = isPremiumTheme && !(state.me && state.me.is_premium);
      sw.classList.toggle("locked", locked);
      sw.classList.toggle("selected", state.me && state.me.theme === id);
    });
  }
  $("#theme-grid").addEventListener("click", async (e) => {
    const sw = e.target.closest(".theme-swatch"); if (!sw) return;
    const id = sw.dataset.themeId;
    if (THEME_PREMIUM[id] && !(state.me && state.me.is_premium)) {
      alert("This theme is part of Gateway Premium. Activate Premium in Settings to unlock it.");
      return;
    }
    applyTheme(id);
    const res = await api("/api/me", { method:"PATCH", body: JSON.stringify({ theme:id }) });
    state.me = res.user;
    renderThemePicker();
    saveAccountSnapshot();
  });

  // ============================================================ PREMIUM
  function renderPremiumUI() {
    const active = !!(state.me && state.me.is_premium);
    $("#premium-toggle").checked = active;
    $("#premium-toggle-label").textContent = active ? "Active" : "Not active";
    $("#premium-chip").classList.toggle("hidden", !active);
  }
  $("#premium-toggle").addEventListener("change", async (e) => {
    const res = await api("/api/me", { method:"PATCH", body: JSON.stringify({ is_premium: e.target.checked }) });
    state.me = res.user;
    renderPremiumUI(); renderThemePicker(); saveAccountSnapshot();
  });

  // ============================================================ MULTI-ACCOUNT SWITCHER
  function loadSavedAccounts() { try { return JSON.parse(localStorage.getItem("gateway_accounts") || "[]"); } catch(_) { return []; } }
  function writeSavedAccounts(list) { localStorage.setItem("gateway_accounts", JSON.stringify(list)); }
  function saveAccountSnapshot() {
    if (!state.me || !state.token) return;
    const list = loadSavedAccounts();
    const idx = list.findIndex((a) => a.username === state.me.username);
    const entry = { token: state.token, username: state.me.username, displayName: state.me.display_name,
                     avatarUrl: state.me.avatar_url, nickname: idx >= 0 ? list[idx].nickname : "" };
    if (idx >= 0) list[idx] = entry; else list.push(entry);
    writeSavedAccounts(list);
  }
  function renderAccountList() {
    const wrap = $("#account-list"); wrap.innerHTML = "";
    loadSavedAccounts().forEach((acc) => {
      const isCurrent = state.me && acc.username === state.me.username;
      const row = el("div", "account-row" + (isCurrent ? " current" : ""));
      row.innerHTML = `<img src="${esc(acc.avatarUrl)}">
        <div class="grow">
          <b>${esc(acc.displayName)} ${isCurrent ? "&middot; current" : ""}</b>
          <input class="account-nickname-input" placeholder="Add a label (e.g. Work)" value="${esc(acc.nickname||'')}">
        </div>
        ${isCurrent ? "" : '<button class="btn-ghost switch-account-btn">Switch</button>'}
        <button class="account-remove-btn" title="Forget this account">&times;</button>`;
      row.querySelector(".account-nickname-input").addEventListener("change", (e) => {
        const list = loadSavedAccounts();
        const a = list.find((x) => x.username === acc.username);
        if (a) { a.nickname = e.target.value; writeSavedAccounts(list); }
      });
      const switchBtn = row.querySelector(".switch-account-btn");
      if (switchBtn) switchBtn.addEventListener("click", () => switchToAccount(acc));
      row.querySelector(".account-remove-btn").addEventListener("click", () => {
        writeSavedAccounts(loadSavedAccounts().filter((x) => x.username !== acc.username));
        renderAccountList();
      });
      wrap.appendChild(row);
    });
  }
  async function switchToAccount(acc) {
    const prevToken = state.token;
    try {
      const res = await fetch("/api/me", { headers: { Authorization:`Bearer ${acc.token}` } });
      if (!res.ok) throw new Error("expired");
      const data = await res.json();
      state.token = acc.token; state.me = data.user;
      localStorage.setItem("gateway_token", acc.token);
      closeModal("settings-screen");
      if (state.ws) state.ws.close();
      state.chats = []; state.activeChatId = null; state.messagesByChat = {};
      bootApp();
    } catch (_) {
      alert("That account's session has expired — please log in again.");
      writeSavedAccounts(loadSavedAccounts().filter((x) => x.token !== acc.token));
      renderAccountList();
      state.token = prevToken;
    }
  }
  $("#add-account-btn").addEventListener("click", () => {
    closeModal("settings-screen");
    state.token = null; // keep localStorage accounts list, just clear the active session
    showAuth();
  });

  // ============================================================ WALLPAPER (Gateway mode)
  const WALLPAPER_IDS = ["default","dunes","botanical","circuit","aurora","noir"];
  function applyWallpaper(chat) {
    const box = $("#thread-messages");
    WALLPAPER_IDS.forEach((w) => box.classList.remove("wp-" + w));
    box.classList.remove("has-wallpaper"); box.style.backgroundImage = "";
    const wp = chat && chat.wallpaper;
    if (!wp) return;
    if (wp.startsWith("/media/")) { box.classList.add("has-wallpaper"); box.style.backgroundImage = `url(${wp})`; }
    else if (WALLPAPER_IDS.includes(wp)) { box.classList.add("wp-" + wp); }
  }
  $("#thread-wallpaper-btn").addEventListener("click", () => {
    if (!state.activeChatId) return;
    const chat = state.chats.find((c) => c.id === state.activeChatId);
    $$("#wallpaper-grid .wallpaper-swatch").forEach((sw) => sw.classList.toggle("selected", sw.dataset.wallpaperId === (chat && chat.wallpaper)));
    openModal("wallpaper-modal");
  });
  $("#close-wallpaper-modal").addEventListener("click", () => closeModal("wallpaper-modal"));
  $("#wallpaper-grid").addEventListener("click", async (e) => {
    const sw = e.target.closest(".wallpaper-swatch"); if (!sw || !state.activeChatId) return;
    const id = sw.dataset.wallpaperId === "default" ? "" : sw.dataset.wallpaperId;
    const res = await api(`/api/chats/${state.activeChatId}/wallpaper`, { method:"PATCH", body: JSON.stringify({ wallpaper:id }) });
    const chat = state.chats.find((c) => c.id === state.activeChatId);
    if (chat) chat.wallpaper = res.wallpaper;
    applyWallpaper(chat);
    closeModal("wallpaper-modal");
  });
  $("#wallpaper-upload-btn").addEventListener("click", () => $("#wallpaper-upload-input").click());
  $("#wallpaper-upload-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file || !state.activeChatId) return;
    try {
      const url = await uploadFile(file);
      const res = await api(`/api/chats/${state.activeChatId}/wallpaper`, { method:"PATCH", body: JSON.stringify({ wallpaper:url }) });
      const chat = state.chats.find((c) => c.id === state.activeChatId);
      if (chat) chat.wallpaper = res.wallpaper;
      applyWallpaper(chat);
      closeModal("wallpaper-modal");
    } catch (err) { alert(err.message); }
    e.target.value = "";
  });

  // ============================================================ PERMISSIONS (real getUserMedia)
  let grantedCameraStream = null, grantedMicStream = null;
  async function maybeShowPermissionPrompt() {
    const perms = (state.me && state.me.permissions) || {};
    if (perms.camera || perms.microphone) { renderPermissionStatuses(); return; }
    openModal("permission-prompt-screen");
  }
  function renderPermissionStatuses() {
    const perms = (state.me && state.me.permissions) || {};
    ["camera", "microphone"].forEach((k) => {
      const el2 = $(`#perm-status-${k}`);
      if (!el2) return;
      const v = perms[k] || "Not set";
      el2.textContent = v === "granted" ? "Granted" : v === "denied" ? "Denied" : v === "skipped" ? "Skipped" : "Not set";
      el2.className = "permission-status" + (v === "granted" ? " granted" : v === "denied" ? " denied" : "");
    });
  }
  async function requestMediaPermissions() {
    let camResult = "denied", micResult = "denied";
    try { grantedCameraStream = await navigator.mediaDevices.getUserMedia({ video:true }); camResult = "granted"; }
    catch (_) { camResult = "denied"; }
    try { grantedMicStream = await navigator.mediaDevices.getUserMedia({ audio:true }); micResult = "granted"; }
    catch (_) { micResult = "denied"; }
    const res = await api("/api/me/permissions", { method:"PATCH", body: JSON.stringify({ camera:camResult, microphone:micResult }) });
    state.me.permissions = res.permissions;
    renderPermissionStatuses();
  }
  $("#permission-allow-btn").addEventListener("click", async () => {
    await requestMediaPermissions();
    closeModal("permission-prompt-screen"); $("#permission-prompt-screen").classList.add("hidden");
  });
  $("#permission-skip-btn").addEventListener("click", async () => {
    const res = await api("/api/me/permissions", { method:"PATCH", body: JSON.stringify({ camera:"skipped", microphone:"skipped" }) });
    state.me.permissions = res.permissions;
    closeModal("permission-prompt-screen"); $("#permission-prompt-screen").classList.add("hidden");
  });
  // ---- reliable clipboard helper + visible toast feedback (fixes: clipboard API is
  // undefined outside secure contexts — e.g. a phone hitting the app via a LAN IP
  // instead of "localhost" — which the old code failed at silently) ----
  async function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try { await navigator.clipboard.writeText(text); return true; } catch (_) { /* fall through */ }
    }
    try {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.focus(); ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch (_) { return false; }
  }
  let toastTimer = null;
  function showToast(message, isError) {
    let toast = $("#gateway-toast");
    if (!toast) {
      toast = el("div", "gateway-toast");
      toast.id = "gateway-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.toggle("error", !!isError);
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 2600);
  }

  $("#request-permissions-btn").addEventListener("click", requestMediaPermissions);
  $("#copy-invite-link-btn").addEventListener("click", async () => {
    const link = `${location.origin}/?ref=${encodeURIComponent(state.me.username)}`;
    const ok = await copyToClipboard(link);
    if (ok) showToast("Invite link copied to clipboard");
    else { showToast("Couldn't access the clipboard — showing the link instead", true); prompt("Copy this invite link:", link); }
  });

  // ============================================================ CAMERA CAPTURE
  let cameraCaptureTarget = null; // 'status' | 'pulse'
  function openCameraCapture(target) {
    cameraCaptureTarget = target;
    const video = $("#camera-video");
    openModal("camera-modal");
    navigator.mediaDevices.getUserMedia({ video:true }).then((stream) => {
      grantedCameraStream = stream;
      video.srcObject = stream;
    }).catch((err) => { alert("Camera unavailable: " + err.message); closeModal("camera-modal"); });
  }
  $("#camera-close-btn").addEventListener("click", () => {
    const video = $("#camera-video");
    if (video.srcObject) video.srcObject.getTracks().forEach((t) => t.stop());
    closeModal("camera-modal");
  });
  $("#camera-shutter-btn").addEventListener("click", async () => {
    const video = $("#camera-video");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    const file = new File([blob], `capture_${Date.now()}.jpg`, { type:"image/jpeg" });
    video.srcObject.getTracks().forEach((t) => t.stop());
    closeModal("camera-modal");
    try {
      const url = await uploadFile(file);
      if (cameraCaptureTarget === "pulse") {
        const caption = prompt("Caption for your Pulse (optional):") || "";
        await api("/api/pulse", { method:"POST", body: JSON.stringify({ media_url:url, kind:"image", caption }) });
        loadAlpha(); loadIgFeed(); loadExplore();
      } else {
        await api("/api/stories", { method:"POST", body: JSON.stringify({ kind:"image", media_url:url, caption:"" }) });
        loadStatus(); loadIgStories();
      }
    } catch (err) { alert(err.message); }
  });

  // ============================================================ VOICE NOTES (mic)
  let mediaRecorder = null, recordedChunks = [];
  async function startVoiceRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data); };
      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(recordedChunks, { type:"audio/webm" });
        const file = new File([blob], `voice_${Date.now()}.webm`, { type:"audio/webm" });
        try {
          const url = await uploadFile(file);
          await api(`/api/chats/${state.activeChatId}/messages`, { method:"POST", body: JSON.stringify({ kind:"audio", media_url:url, content:"" }) });
        } catch (err) { alert(err.message); }
      };
      mediaRecorder.start();
      return true;
    } catch (err) { alert("Microphone unavailable: " + err.message); return false; }
  }
  function stopVoiceRecording() { if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop(); }
  let voiceRecordActive = false;
  const voiceBtn = $("#voice-record-btn");
  async function beginHold(e) {
    e.preventDefault();
    if (!state.activeChatId || voiceRecordActive) return;
    voiceRecordActive = true;
    voiceBtn.classList.add("recording");
    const ok = await startVoiceRecording();
    if (!ok) { voiceRecordActive = false; voiceBtn.classList.remove("recording"); }
  }
  function endHold() {
    if (!voiceRecordActive) return;
    voiceRecordActive = false;
    voiceBtn.classList.remove("recording");
    stopVoiceRecording();
  }
  voiceBtn.addEventListener("mousedown", beginHold);
  voiceBtn.addEventListener("touchstart", beginHold);
  voiceBtn.addEventListener("mouseup", endHold);
  voiceBtn.addEventListener("mouseleave", endHold);
  voiceBtn.addEventListener("touchend", endHold);

  // ============================================================ PER-PLATFORM SETTINGS
  async function openPlatformSettings(platform) {
    const res = await api(`/api/settings/${platform}`);
    $$(`#settings-${platform} .platform-setting`).forEach((input) => {
      input.checked = !!res.settings[input.dataset.key];
    });
    openModal(`settings-${platform}`);
  }
  $$(".platform-settings-open").forEach((btn) => btn.addEventListener("click", () => openPlatformSettings(btn.dataset.platform)));
  $$(".platform-settings-close").forEach((btn) => btn.addEventListener("click", () => {
    $$(".settings-screen").forEach((s) => { if (s.id.startsWith("settings-") && s.id !== "settings-screen") s.classList.add("hidden"); });
  }));
  $$(".platform-setting").forEach((input) => input.addEventListener("change", async (e) => {
    const { platform, key } = e.target.dataset;
    const res = await api(`/api/settings/${platform}`, { method:"PATCH", body: JSON.stringify({ [key]: e.target.checked }) });
    state.platformSettings[platform] = res.settings;
    applyPlatformSettingEffects(platform);
  }));
  function applyPlatformSettingEffects(platform) {
    const s = state.platformSettings[platform] || {};
    if (platform === "beta") {
      $$(".ig-post-likes").forEach((el2) => el2.classList.toggle("hidden", s.show_like_counts === false));
      $$(".ig-post-caption").forEach((el2) => el2.classList.toggle("hidden", s.show_captions === false));
      $$(".ig-post-media[data-kind=video], .ig-post-media").forEach((v) => { if (v.tagName === "VIDEO") v.autoplay = !!s.autoplay_videos; });
    } else if (platform === "epsilon") {
      $("#posts-list").classList.toggle("compact", !!s.compact_timeline);
      $$(".reply-count").forEach((el2) => el2.classList.toggle("hidden", s.show_reply_counts === false));
    } else if (platform === "alpha") {
      $$("#pulse-feed video").forEach((v) => { v.muted = !s.autoplay_sound; v.loop = s.loop_videos !== false; });
    }
  }
  async function loadAllPlatformSettings() {
    for (const platform of ["gateway", "beta", "epsilon", "alpha"]) {
      try { const res = await api(`/api/settings/${platform}`); state.platformSettings[platform] = res.settings; }
      catch (_) {}
    }
    // beta/epsilon/alpha effects apply themselves the moment their feed next
    // renders (loadIgFeed/loadPosts/loadAlpha each call this) — gateway has
    // no equivalent feed render to hook, so nothing extra needed here for it,
    // but this loop existing at all used to be the whole bug: settings were
    // fetched into state and then never applied to anything already on
    // screen until the user manually touched a toggle.
  }

  // ============================================================ SOUNDS LIBRARY
  $("#open-sounds-btn").addEventListener("click", () => { closeModal("settings-screen"); openModal("sounds-screen"); loadSounds(); });
  $("#sounds-close-btn").addEventListener("click", () => closeModal("sounds-screen"));
  async function loadSounds() {
    const res = await api("/api/sounds");
    const list = $("#sounds-list"); list.innerHTML = "";
    if (res.sounds.length === 0) { list.innerHTML = `<p style="padding:20px;color:var(--text-dim);text-align:center">No sounds uploaded yet — be the first.</p>`; return; }
    res.sounds.forEach((s) => {
      const row = el("div", "sound-row fade-in-item");
      const avgText = s.rating && s.rating.average != null ? `${s.rating.average}/5 (${s.rating.count})` : "Not yet rated";
      row.innerHTML = `<span class="sicon"><svg class="ic"><use href="#i-music"/></svg></span>
        <div class="grow"><b>${esc(s.title)}</b><span>${esc(s.artist || s.display_name)} &middot; used ${s.use_count}&times;</span>
          <div class="rating-summary" id="sound-rating-${s.id}"><span>${avgText}</span></div>
        </div>
        <div class="sound-row-actions">
          <audio src="${esc(s.file_url)}" controls style="height:32px;max-width:130px"></audio>
          <a class="icon-btn" href="${esc(s.file_url)}" download title="Download"><svg class="ic"><use href="#i-download"/></svg></a>
        </div>`;
      const ratingSlot = row.querySelector(`#sound-rating-${s.id}`);
      const mine = s.rating && s.rating.my_rating ? s.rating.my_rating.stars : 0;
      ratingSlot.appendChild(buildStarRating(mine, async (stars) => {
        const res2 = await api("/api/ratings", { method:"POST", body: JSON.stringify({ target_type:"sound", target_id: s.id, stars }) });
        s.rating = res2;
        loadSounds();
      }, false));
      list.appendChild(row);
    });
  }
  $("#sound-file-btn").addEventListener("click", () => $("#sound-file-input").click());
  let pendingSoundFile = null;
  $("#sound-file-input").addEventListener("change", (e) => { pendingSoundFile = e.target.files[0]; });
  $("#sound-upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = $("#sound-title-input").value.trim();
    if (!title || !pendingSoundFile) { alert("Pick an audio file and give it a title."); return; }
    try {
      const url = await uploadFile(pendingSoundFile);
      await api("/api/sounds", { method:"POST", body: JSON.stringify({ title, artist: $("#sound-artist-input").value.trim(), file_url:url }) });
      $("#sound-title-input").value = ""; $("#sound-artist-input").value = ""; pendingSoundFile = null;
      loadSounds();
    } catch (err) { alert(err.message); }
  });

  // ============================================================ SOUND PICKER (Alpha/Beta pulse composer)
  function pickSound() {
    return new Promise(async (resolve) => {
      let chosen = "original sound";
      const list = $("#sound-picker-list");
      list.innerHTML = `<div class="sound-picker-row selected" data-sound="original sound"><span class="grow"><b>Original sound</b><span>No background sound</span></span></div>`;
      try {
        const res = await api("/api/sounds");
        res.sounds.forEach((s) => {
          const row = el("div", "sound-picker-row");
          row.dataset.sound = s.title;
          row.innerHTML = `<span class="grow"><b>${esc(s.title)}</b><span>${esc(s.artist || s.display_name)}</span></span>`;
          list.appendChild(row);
        });
      } catch (_) { /* sounds library unreachable — original sound still works */ }
      $$(".sound-picker-row", list).forEach((row) => row.addEventListener("click", () => {
        $$(".sound-picker-row", list).forEach((r) => r.classList.remove("selected"));
        row.classList.add("selected");
        chosen = row.dataset.sound;
      }));
      const onClose = () => { closeModal("sound-picker-modal"); $("#close-sound-picker").removeEventListener("click", onClose); resolve(chosen); };
      $("#close-sound-picker").addEventListener("click", onClose);
      openModal("sound-picker-modal");
    });
  }

  // ============================================================ VIDEO TRIMMER (real trim, client-side re-encode via canvas + MediaRecorder)
  function maybeTrimVideo(file) {
    return new Promise((resolve) => {
      if (!file.type.startsWith("video/")) { resolve(file); return; }
      const video = $("#video-trim-preview");
      const startInput = $("#video-trim-start"), endInput = $("#video-trim-end");
      const startLabel = $("#video-trim-start-label"), endLabel = $("#video-trim-end-label");
      const objectUrl = URL.createObjectURL(file);
      video.src = objectUrl;
      const cleanupAndResolve = (result) => {
        URL.revokeObjectURL(objectUrl);
        closeModal("video-trim-modal");
        applyBtn.removeEventListener("click", onApply);
        skipBtn.removeEventListener("click", onSkip);
        resolve(result);
      };
      const onSkip = () => cleanupAndResolve(file);
      let trimStart = 0, trimEnd = 0;
      const updateLabels = () => {
        const dur = video.duration || 0;
        trimStart = (startInput.value / 100) * dur;
        trimEnd = (endInput.value / 100) * dur;
        if (trimEnd <= trimStart) trimEnd = Math.min(dur, trimStart + 0.5);
        startLabel.textContent = trimStart.toFixed(1) + "s";
        endLabel.textContent = trimEnd.toFixed(1) + "s";
      };
      video.addEventListener("loadedmetadata", () => { startInput.value = 0; endInput.value = 100; updateLabels(); }, { once:true });
      startInput.oninput = updateLabels; endInput.oninput = updateLabels;
      const onApply = async () => {
        applyBtn.disabled = true; applyBtn.textContent = "Rendering trimmed clip…";
        try {
          const canvas = document.createElement("canvas");
          canvas.width = video.videoWidth || 640; canvas.height = video.videoHeight || 360;
          const ctx = canvas.getContext("2d");
          const canvasStream = canvas.captureStream(30);
          // Pull the audio track in too via a second, hidden playback of the
          // same source so the trimmed export isn't silent.
          let audioTrack = null;
          try {
            const audioCtxSrc = video.captureStream ? video.captureStream() : null;
            if (audioCtxSrc) audioCtxSrc.getAudioTracks().forEach((t) => canvasStream.addTrack(t));
          } catch (_) { /* some browsers don't support captureStream audio — export will be video-only, not fatal */ }
          const chunks = [];
          const recorder = new MediaRecorder(canvasStream, { mimeType: "video/webm" });
          recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
          const stopped = new Promise((res2) => { recorder.onstop = res2; });
          video.currentTime = trimStart;
          await new Promise((res2) => { video.addEventListener("seeked", res2, { once:true }); });
          recorder.start();
          video.play();
          const drawFrame = () => {
            if (video.currentTime >= trimEnd || video.paused || video.ended) { video.pause(); recorder.stop(); return; }
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            requestAnimationFrame(drawFrame);
          };
          requestAnimationFrame(drawFrame);
          await stopped;
          const blob = new Blob(chunks, { type:"video/webm" });
          const trimmedFile = new File([blob], `trimmed_${Date.now()}.webm`, { type:"video/webm" });
          cleanupAndResolve(trimmedFile);
        } catch (err) {
          alert("Trimming failed (" + err.message + ") — using the full video instead.");
          cleanupAndResolve(file);
        } finally {
          applyBtn.disabled = false; applyBtn.textContent = "Use trimmed clip";
        }
      };
      const applyBtn = $("#video-trim-apply-btn"), skipBtn = $("#video-trim-skip-btn");
      applyBtn.addEventListener("click", onApply);
      skipBtn.addEventListener("click", onSkip);
      openModal("video-trim-modal");
    });
  }
  $("#close-video-trim").addEventListener("click", () => $("#video-trim-skip-btn").click());
  function renderDevKeyStatus() {
    const box = $("#dev-key-status");
    box.innerHTML = state.me.has_api_key
      ? `<p style="font-size:12px;color:var(--accent)">You have an active API key.</p>`
      : `<p style="font-size:12px;color:var(--text-dim)">No API key yet.</p>`;
  }
  $("#generate-api-key-btn").addEventListener("click", async () => {
    const res = await api("/api/dev/api-key", { method:"POST" });
    state.me.has_api_key = true;
    renderDevKeyStatus();
    $("#dev-snippet").textContent =
`curl ${location.origin}/api/me \\
  -H "X-Api-Key: ${res.api_key}"

# Save this key now — it will not be shown again.`;
  });
  $("#revoke-api-key-btn").addEventListener("click", async () => {
    await api("/api/dev/api-key", { method:"DELETE" });
    state.me.has_api_key = false;
    renderDevKeyStatus();
    $("#dev-snippet").textContent = "";
  });

  // ============================================================ SUBSCRIBE / SHARE (shared helpers)
  function deepLink(kind, id) { return `${location.origin}/#${kind}/${id}`; }
  function openShareSheet({ link, text, title }) {
    $("#share-sheet-title").textContent = title || "Share";
    const wrap = $("#share-sheet-options"); wrap.innerHTML = "";
    const addRow = (iconClass, iconHref, label, onClick) => {
      const row = el("div", "share-option-row");
      row.innerHTML = `<span class="sicon ${iconClass}"><svg class="ic"><use href="${iconHref}"/></svg></span><span>${esc(label)}</span>`;
      row.addEventListener("click", onClick);
      wrap.appendChild(row);
    };
    if (navigator.share) {
      addRow("share-icon-native", "#i-share", "Share via…", async () => {
        try { await navigator.share({ title: title || "Gateway Chat", text, url: link }); closeModal("share-sheet-modal"); }
        catch (_) { /* user cancelled the native sheet — leave our sheet open */ }
      });
    }
    addRow("share-icon-whatsapp", "#i-whatsapp", "WhatsApp", () => {
      window.open(`https://wa.me/?text=${encodeURIComponent(text + " " + link)}`, "_blank");
      closeModal("share-sheet-modal");
    });
    addRow("share-icon-x", "#i-x-logo", "X", () => {
      window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(link)}`, "_blank");
      closeModal("share-sheet-modal");
    });
    addRow("share-icon-gmail", "#i-mail", "Gmail", () => {
      const su = encodeURIComponent(title || "Check this out");
      const body = encodeURIComponent(text + "\n\n" + link);
      window.open(`https://mail.google.com/mail/?view=cm&fs=1&su=${su}&body=${body}`, "_blank");
      closeModal("share-sheet-modal");
    });
    addRow("share-icon-instagram", "#i-instagram-logo", "Instagram (copy link)", async () => {
      // Instagram has no web share/deep-link intent that accepts an arbitrary
      // link — there's genuinely no URL scheme for "open Instagram with this
      // pre-filled." Copying is the honest, actually-working option here.
      const ok = await copyToClipboard(`${text} ${link}`);
      showToast(ok ? "Copied — paste it into an Instagram DM or story" : "Couldn't copy — long-press to copy manually", !ok);
      closeModal("share-sheet-modal");
    });
    addRow("share-icon-copy", "#i-copy", "Copy link", async () => {
      const ok = await copyToClipboard(link);
      showToast(ok ? "Link copied to clipboard" : "Couldn't access the clipboard", !ok);
      if (!ok) prompt("Copy this link:", link);
      closeModal("share-sheet-modal");
    });
    openModal("share-sheet-modal");
  }
  async function copyShareLink(kind, id) {
    openShareSheet({ link: deepLink(kind, id), text: "Check this out on Gateway Chat", title: "Share" });
  }
  $("#close-share-sheet").addEventListener("click", () => closeModal("share-sheet-modal"));
  function spawnHeartBurst(originEl) {
    const rect = originEl.getBoundingClientRect();
    const fx = el("div", "heart-burst-fx");
    fx.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>`;
    fx.style.left = (rect.left + rect.width/2 - 32) + "px";
    fx.style.top = (rect.top + rect.height/2 - 32) + "px";
    fx.style.position = "fixed";
    document.body.appendChild(fx);
    setTimeout(() => fx.remove(), 700);
  }

  // ============================================================ BOOT
  async function bootApp() {
    showApp();
    $("#self-avatar").src = state.me.avatar_url;
    $("#profile-avatar").src = state.me.avatar_url;
    applyTheme(state.me.theme);
    renderPremiumUI();
    renderPermissionStatuses();
    renderDevKeyStatus();
    saveAccountSnapshot();
    renderAccountList();
    switchMode(state.me.default_mode || "gateway", { skipHistory:true });
    connectWebSocket();
    await Promise.all([loadChats(), loadProviders(), loadStatus(), loadIgFeed(), loadExplore(), loadPosts(), loadAllPlatformSettings()]);
    renderProfileForm();
    renderThemePicker();
    loadAlpha();
    bindAllScrollables();
    maybeShowPermissionPrompt();
  }
  async function tryResume() {
    if (!state.token) return showAuth();
    try { const res = await api("/api/me"); state.me = res.user; bootApp(); }
    catch (_) { localStorage.removeItem("gateway_token"); showAuth(); }
  }

  // ============================================================ SPACE SWITCHER (hamburger dropdown)
  const MODE_LABEL = { gateway:"Gateway", beta:"Beta", epsilon:"Epsilon", alpha:"Alpha" };
  function switchMode(mode) {
    state.currentMode = mode;
    $$(".mode-view").forEach((v) => v.classList.toggle("active", v.id === `mode-${mode}`));
    $("#topbar-mode-name").textContent = MODE_LABEL[mode];
    const markEl = $(`#space-menu-items .space-menu-item[data-mode="${mode}"] .mark-wrap`);
    if (markEl) $("#topbar-mark").innerHTML = markEl.innerHTML;
    if (window.GatewayParticles) GatewayParticles.setMode(mode);
    const createBtn = $("#topbar-create-btn");
    createBtn.classList.remove("hidden");
    createBtn.onclick = () => {
      if (mode === "gateway") $("#new-chat-btn").click();
      else if (mode === "beta" || mode === "alpha") $(mode === "beta" ? "#beta-post-input" : "#pulse-input").click();
      else if (mode === "epsilon") { switchSubtab("epsilon", "home"); $("#post-input").focus(); }
    };
    if (mode === "gateway") createBtn.classList.add("hidden"); // Gateway's own "+ New chat" button covers this
    renderSpaceMenuCurrent();
  }
  function renderSpaceMenuCurrent() {
    $$("#space-menu-items .space-menu-item").forEach((item) => {
      item.classList.toggle("current", item.dataset.mode === state.currentMode);
    });
  }
  function openSpaceMenu() {
    renderSpaceMenuCurrent();
    $("#space-menu-backdrop").classList.remove("hidden");
  }
  function closeSpaceMenu() { $("#space-menu-backdrop").classList.add("hidden"); }
  $("#space-menu-btn").addEventListener("click", openSpaceMenu);
  $("#space-menu-backdrop").addEventListener("click", (e) => { if (e.target.id === "space-menu-backdrop") closeSpaceMenu(); });
  $$("#space-menu-items .space-menu-item").forEach((item) => item.addEventListener("click", () => {
    switchMode(item.dataset.mode);
    closeSpaceMenu();
  }));
  $("#space-menu-settings-btn").addEventListener("click", () => {
    closeSpaceMenu();
    openModal("settings-screen");
    renderModePicker(); renderThemePicker(); renderAccountList(); renderPremiumUI();
  });

  function switchSubtab(mode, sub) {
    $$(`#${mode}-subtabs .subtab`).forEach((t) => t.classList.toggle("active", t.dataset.sub === sub));
    $$(`#mode-${mode} .subpage`).forEach((p) => p.classList.toggle("active", p.id === `${mode}-page-${sub}`));
    if (mode === "beta" && sub === "profile") renderProfileInto($("#beta-profile-page"), state.me, { isMe:true, kind:"grid" });
    if (mode === "epsilon" && sub === "profile") renderProfileInto($("#epsilon-profile-page"), state.me, { isMe:true, kind:"list" });
    if (mode === "epsilon" && sub === "notifications") loadNotifications();
  }
  $$(".subtabs").forEach((bar) => bar.addEventListener("click", (e) => {
    const btn = e.target.closest(".subtab"); if (!btn) return;
    const mode = bar.id.split("-")[0];
    switchSubtab(mode, btn.dataset.sub);
    if (mode === "alpha") { state.alphaScope = btn.dataset.sub === "following" ? "following" : "foryou"; loadAlpha(); }
  }));

  // ============================================================ SETTINGS
  $("#settings-close-btn").addEventListener("click", () => closeModal("settings-screen"));
  function renderModePicker() {
    $$("#mode-picker .mode-card").forEach((card) => {
      const mode = card.dataset.modeCard;
      const radio = card.querySelector("input[type=radio]");
      const selected = (state.me.default_mode || "gateway") === mode;
      radio.checked = selected;
      card.classList.toggle("selected", selected);
      card.onclick = async () => {
        $$("#mode-picker .mode-card").forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected"); radio.checked = true;
        const res = await api("/api/me", { method:"PATCH", body: JSON.stringify({ default_mode: mode }) });
        state.me = res.user;
      };
    });
  }
  function renderProfileForm() {
    $("#profile-avatar").src = state.me.avatar_url;
    $("#profile-display").value = state.me.display_name;
    $("#profile-status").value = state.me.status;
    $("#profile-bio").value = state.me.bio;
  }
  $("#profile-avatar-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const url = await uploadFile(file);
      const res = await api("/api/me", { method:"PATCH", body: JSON.stringify({ avatar_url:url }) });
      state.me = res.user;
      $("#profile-avatar").src = state.me.avatar_url;
      $("#self-avatar").src = state.me.avatar_url;
      showToast("Profile photo updated");
    } catch (err) { alert(err.message); }
    e.target.value = "";
  });
  $("#save-profile-btn").addEventListener("click", async () => {
    const res = await api("/api/me", { method:"PATCH", body: JSON.stringify({
      display_name: $("#profile-display").value, status: $("#profile-status").value, bio: $("#profile-bio").value }) });
    state.me = res.user;
    $("#self-avatar").src = state.me.avatar_url;
  });

  // ============================================================ WEBSOCKET
  function connectWebSocket() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(state.token)}`);
    state.ws = ws;
    ws.onopen = () => { state.wsRetryMs = 1000; };
    ws.onmessage = (evt) => { let d; try { d = JSON.parse(evt.data); } catch(_) { return; } handleWsEvent(d); };
    ws.onclose = () => { if (!state.token) return; setTimeout(connectWebSocket, state.wsRetryMs); state.wsRetryMs = Math.min(state.wsRetryMs*1.6, 15000); };
    ws.onerror = () => ws.close();
  }
  function handleWsEvent(data) {
    if (data.type === "message") {
      const msg = data.message;
      state.messagesByChat[msg.chat_id] = state.messagesByChat[msg.chat_id] || [];
      state.messagesByChat[msg.chat_id].push(msg);
      if (state.activeChatId === msg.chat_id) { appendMessageEl(msg); scrollThreadToBottom(); markRead(msg.chat_id); }
      loadChats();
    } else if (data.type === "typing") {
      if (state.activeChatId === data.chat_id) showTypingIndicator();
    } else if (data.type === "new_story") {
      loadStatus();
    }
  }
  function wsSend(obj) { if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify(obj)); }

  // ============================================================ GATEWAY: chats
  async function loadChats() {
    const res = await api("/api/chats"); state.chats = res.chats; renderChatList();
    const totalUnread = state.chats.reduce((n,c) => n + c.unread_count, 0);
    const badge = $("#badge-gateway");
    const hamburgerBadge = $("#badge-hamburger");
    if (totalUnread > 0) {
      badge.textContent = totalUnread > 99 ? "99+" : totalUnread; badge.classList.remove("hidden");
      hamburgerBadge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
      hamburgerBadge.classList.add("hidden");
    }
  }
  function renderChatList() {
    const list = $("#chat-list"); list.innerHTML = "";
    const q = ($("#chat-search").value || "").toLowerCase();
    state.chats.filter((c) => !q || c.name.toLowerCase().includes(q)).forEach((c) => {
      const item = el("div", "chat-item" + (c.id === state.activeChatId ? " active" : ""));
      const last = c.last_message;
      const preview = last ? (last.kind === "text" ? last.content : `Attachment (${last.kind})`) : "Say hi";
      item.innerHTML = `<img src="${esc(c.avatar_url)}">
        <div class="chat-item-main">
          <div class="chat-item-top"><span class="chat-item-name">${esc(c.name)}</span><span class="chat-item-time">${last?timeAgo(last.created_at):""}</span></div>
          <div class="chat-item-bottom"><span class="chat-item-preview">${esc(preview)}</span>${c.unread_count>0?`<span class="chat-item-unread">${c.unread_count}</span>`:""}</div>
        </div>`;
      item.addEventListener("click", () => openChat(c.id));
      list.appendChild(item);
    });
  }
  $("#chat-search").addEventListener("input", renderChatList);

  async function openChat(chatId) {
    state.activeChatId = chatId; renderChatList();
    const chat = state.chats.find((c) => c.id === chatId);
    $("#empty-thread").classList.add("hidden");
    $("#thread").classList.remove("hidden");
    $("#gateway-chats-layout").classList.add("thread-open");
    $("#thread-avatar").src = chat.avatar_url;
    $("#thread-name").textContent = chat.name;
    $("#thread-status").textContent = chat.is_group ? `${chat.members.length} members` : (chat.other_user && chat.other_user.is_online ? "online" : "offline");
    $("#gateway-provider").classList.toggle("hidden", !(chat.other_user && chat.other_user.username === "gateway"));
    applyWallpaper(chat);
    if (!state.messagesByChat[chatId]) { const res = await api(`/api/chats/${chatId}/messages`); state.messagesByChat[chatId] = res.messages; }
    renderThreadMessages(); scrollThreadToBottom(); markRead(chatId);
  }
  $("#thread-back-btn").addEventListener("click", () => { $("#gateway-chats-layout").classList.remove("thread-open"); state.activeChatId = null; });

  function renderThreadMessages() { const wrap = $("#thread-messages"); wrap.innerHTML = ""; (state.messagesByChat[state.activeChatId]||[]).forEach(appendMessageEl); }
  function appendMessageEl(msg) {
    const wrap = $("#thread-messages"); if (!wrap || state.activeChatId !== msg.chat_id) return;
    const mine = msg.sender_id === state.me.id;
    const row = el("div", `msg-row ${mine?"me":"them"}`);
    let mediaHtml = "";
    if (msg.media_url) {
      if (msg.kind === "video") mediaHtml = `<video class="msg-media" src="${esc(msg.media_url)}" controls></video>`;
      else if (msg.kind === "audio") mediaHtml = `<audio src="${esc(msg.media_url)}" controls></audio>`;
      else mediaHtml = `<img class="msg-media" src="${esc(msg.media_url)}">`;
    }
    row.innerHTML = `<div class="msg-bubble">${mediaHtml}${msg.content?esc(msg.content):""}<div class="msg-meta">${clockTime(msg.created_at)}</div></div>`;
    wrap.appendChild(row);
  }
  function scrollThreadToBottom() { const w = $("#thread-messages"); if (w) w.scrollTop = w.scrollHeight; }
  function showTypingIndicator() { $("#thread-status").textContent = "typing…"; setTimeout(() => openChat(state.activeChatId), 1800); }
  async function markRead(chatId) { try { await api(`/api/chats/${chatId}/read`, { method:"POST" }); } catch(_) {} }

  $("#composer-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#composer-input"); const text = input.value.trim();
    if (!text || !state.activeChatId) return;
    input.value = "";
    const chat = state.chats.find((c) => c.id === state.activeChatId);
    const isGateway = chat && chat.other_user && chat.other_user.username === "gateway";
    const body = { content:text, kind:"text" };
    if (isGateway) body.provider = $("#gateway-provider").value;
    try { await api(`/api/chats/${state.activeChatId}/messages`, { method:"POST", body: JSON.stringify(body) }); }
    catch (err) { alert(err.message); }
  });
  $("#composer-input").addEventListener("input", () => { if (state.activeChatId) wsSend({ type:"typing", chat_id:state.activeChatId }); });
  $("#attach-btn").addEventListener("click", () => $("#attach-input").click());
  $("#attach-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file || !state.activeChatId) return;
    try { const url = await uploadFile(file); await api(`/api/chats/${state.activeChatId}/messages`, { method:"POST", body: JSON.stringify({ kind:mediaKindOf(file), media_url:url, content:"" }) }); }
    catch (err) { alert(err.message); }
    e.target.value = "";
  });

  $("#new-chat-btn").addEventListener("click", () => { openModal("new-chat-modal"); $("#user-search-input").value=""; $("#user-search-input").focus(); searchUsers(""); });
  $("#close-new-chat").addEventListener("click", () => closeModal("new-chat-modal"));
  const contactsSupported = "contacts" in navigator && "ContactsManager" in window;
  if (!contactsSupported) $("#import-contacts-btn").title = "Not supported by this browser — Chrome for Android only";
  $("#import-contacts-btn").addEventListener("click", async () => {
    if (!contactsSupported) {
      showToast("Your browser doesn't support picking device contacts (only Chrome for Android does) — search by username instead, or share an invite link.", true);
      return;
    }
    try {
      const picked = await navigator.contacts.select(["name", "tel", "email"], { multiple:false });
      if (!picked.length) return;
      const contact = picked[0];
      const q = (contact.name && contact.name[0]) || (contact.email && contact.email[0]) || "";
      if (!q) { showToast("That contact has no name or email to search by", true); return; }
      $("#user-search-input").value = q;
      searchUsers(q);
    } catch (err) { showToast("Contact picker was cancelled or blocked: " + err.message, true); }
  });
  let searchDebounce;
  $("#user-search-input").addEventListener("input", (e) => { clearTimeout(searchDebounce); searchDebounce = setTimeout(() => searchUsers(e.target.value.trim()), 250); });
  async function searchUsers(q) {
    const res = await api(`/api/users?q=${encodeURIComponent(q)}`);
    const wrap = $("#user-search-results"); wrap.innerHTML = "";
    res.users.forEach((u) => {
      const row = el("div", "user-result");
      row.innerHTML = `<img src="${esc(u.avatar_url)}"><div><b>${esc(u.display_name)}</b><div style="font-size:11px;color:var(--text-dim)">@${esc(u.username)}</div></div>`;
      row.addEventListener("click", async () => {
        await api("/api/contacts", { method:"POST", body: JSON.stringify({ contact_id:u.id }) });
        const res2 = await api("/api/chats"); state.chats = res2.chats; renderChatList();
        const chat = state.chats.find((c) => c.other_user && c.other_user.id === u.id);
        closeModal("new-chat-modal"); switchMode("gateway"); switchSubtab("gateway", "chats");
        if (chat) openChat(chat.id);
      });
      wrap.appendChild(row);
    });
    // Not on Gateway yet? Real WhatsApp-style fallback: offer an invite link instead
    // of just showing an empty list.
    if (q.trim() && res.users.length === 0) {
      const inviteRow = el("div", "invite-fallback");
      inviteRow.innerHTML = `<p>No one found for "${esc(q)}" — they may not be on Gateway yet.</p>
        <button class="btn-primary small" id="invite-fallback-btn">Share an invite link</button>`;
      inviteRow.querySelector("#invite-fallback-btn").addEventListener("click", () => {
        const link = `${location.origin}/?ref=${encodeURIComponent(state.me.username)}`;
        openShareSheet({ link, text: `Join me on Gateway Chat — I'm @${state.me.username}`, title: "Invite to Gateway Chat" });
      });
      wrap.appendChild(inviteRow);
    }
  }

  // ============================================================ GATEWAY: Status (WhatsApp-style stories list)
  async function loadStatus() { const res = await api("/api/stories"); renderStatus(res.story_groups); }
  function renderStatus(groups) {
    const list = $("#status-list"); list.innerHTML = "";
    const mine = groups.find((g) => g.user_id === state.me.id);
    const myRow = el("div", "status-row status-my-row");
    myRow.innerHTML = `<div class="status-ring ${mine?'':'seen'}"><img src="${esc(state.me.avatar_url)}"><span class="status-plus">+</span></div>
      <div><b>My status</b><div style="font-size:12px;color:var(--text-dim)">${mine ? mine.stories.length + " update(s)" : "Tap to add a status update"}</div></div>`;
    myRow.addEventListener("click", () => mine ? openStoryViewer(mine) : openModal("status-composer-modal"));
    myRow.querySelector(".status-plus").addEventListener("click", (ev) => { ev.stopPropagation(); openModal("status-composer-modal"); });
    list.appendChild(myRow);
    const others = groups.filter((g) => g.user_id !== state.me.id);
    if (others.length) {
      list.appendChild(el("div", "status-section-label", "Recent updates"));
      others.forEach((g) => {
        const allSeen = g.stories.every((s) => s.viewed);
        const row = el("div", "status-row");
        row.innerHTML = `<div class="status-ring ${allSeen?'seen':''}"><img src="${esc(g.avatar_url)}"></div>
          <div><b>${esc(g.display_name)}</b><div style="font-size:12px;color:var(--text-dim)">${timeAgo(g.stories[0].created_at)}</div></div>`;
        row.addEventListener("click", () => openStoryViewer(g));
        list.appendChild(row);
      });
    }
  }
  $("#story-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try { const url = await uploadFile(file); await api("/api/stories", { method:"POST", body: JSON.stringify({ kind:mediaKindOf(file), media_url:url, caption:"" }) }); loadStatus(); loadIgStories(); }
    catch (err) { alert(err.message); }
    e.target.value = "";
  });

  // ---- status composer chooser + text/voice status ----
  $("#close-status-composer").addEventListener("click", () => closeModal("status-composer-modal"));
  $("#status-opt-media").addEventListener("click", () => { closeModal("status-composer-modal"); $("#story-input").click(); });
  const STATUS_BG_COLORS = ["#25D366","#1877F2","#E1306C","#7C3AED","#F97316","#0EA5E9","#111827"];
  let statusBgSelected = STATUS_BG_COLORS[0];
  $("#status-opt-text").addEventListener("click", () => {
    closeModal("status-composer-modal");
    $("#status-text-input").value = "";
    const sw = $("#status-bg-swatches"); sw.innerHTML = "";
    STATUS_BG_COLORS.forEach((color) => {
      const dot = el("div", "status-bg-swatch" + (color === statusBgSelected ? " selected" : ""));
      dot.style.background = color;
      dot.addEventListener("click", () => { statusBgSelected = color; $$(".status-bg-swatch", sw).forEach((d) => d.classList.toggle("selected", d === dot)); });
      sw.appendChild(dot);
    });
    openModal("status-text-modal");
  });
  $("#close-status-text").addEventListener("click", () => closeModal("status-text-modal"));
  $("#status-text-post-btn").addEventListener("click", async () => {
    const text = $("#status-text-input").value.trim();
    if (!text) return;
    try {
      await api("/api/stories", { method:"POST", body: JSON.stringify({ kind:"text", caption:text, bg_color:statusBgSelected }) });
      closeModal("status-text-modal"); loadStatus(); loadIgStories();
    } catch (err) { alert(err.message); }
  });
  $("#status-opt-voice").addEventListener("click", () => { closeModal("status-composer-modal"); openModal("status-voice-modal"); });
  $("#close-status-voice").addEventListener("click", () => { stopStatusVoiceRecording(true); closeModal("status-voice-modal"); });
  let statusVoiceRecorder = null, statusVoiceChunks = [], statusVoiceActive = false;
  $("#status-voice-record-btn").addEventListener("click", async () => {
    if (statusVoiceActive) { stopStatusVoiceRecording(false); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
      statusVoiceChunks = [];
      statusVoiceRecorder = new MediaRecorder(stream);
      statusVoiceRecorder.ondataavailable = (e) => { if (e.data.size > 0) statusVoiceChunks.push(e.data); };
      statusVoiceRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (statusVoiceChunks.length === 0) return;
        const blob = new Blob(statusVoiceChunks, { type:"audio/webm" });
        const file = new File([blob], `status_voice_${Date.now()}.webm`, { type:"audio/webm" });
        try {
          const url = await uploadFile(file);
          await api("/api/stories", { method:"POST", body: JSON.stringify({ kind:"audio", media_url:url, caption:"" }) });
          closeModal("status-voice-modal"); loadStatus(); loadIgStories();
        } catch (err) { alert(err.message); }
      };
      statusVoiceRecorder.start();
      statusVoiceActive = true;
      $("#status-voice-record-btn").classList.add("recording");
      $("#status-voice-hint").textContent = "Recording — tap again to stop and post.";
    } catch (err) { alert("Microphone unavailable: " + err.message); }
  });
  function stopStatusVoiceRecording(discard) {
    if (discard && statusVoiceRecorder) statusVoiceChunks = [];
    if (statusVoiceRecorder && statusVoiceRecorder.state !== "inactive") statusVoiceRecorder.stop();
    statusVoiceActive = false;
    $("#status-voice-record-btn").classList.remove("recording");
    $("#status-voice-hint").textContent = "Tap to start recording, tap again to stop and post.";
  }

  let storyViewerState = null;
  function openStoryViewer(group) {
    storyViewerState = { stories: group.stories, index: 0 };
    $("#story-viewer").classList.remove("hidden");
    $("#story-progress").innerHTML = "";
    group.stories.forEach(() => $("#story-progress").appendChild(el("span", "", "<i></i>")));
    showStoryFrame();
  }
  function showStoryFrame() {
    const { stories, index } = storyViewerState;
    if (index >= stories.length) { closeStoryViewer(); return; }
    const s = stories[index];
    api(`/api/stories/${s.id}/view`, { method:"POST" }).catch(()=>{});
    const content = $("#story-content");
    if (s.kind === "video") { content.className = "story-content"; content.innerHTML = `<video src="${esc(s.media_url)}" autoplay muted></video>`; }
    else if (s.kind === "audio") {
      content.className = "story-content text-story"; content.style.background = "#111827";
      content.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;gap:14px;width:100%">
        <svg class="ic" style="width:48px;height:48px"><use href="#i-mic"/></svg>
        <audio id="story-audio-player" src="${esc(s.media_url)}" autoplay controls style="width:80%"></audio></div>`;
    }
    else if (s.media_url) { content.className = "story-content"; content.innerHTML = `<img src="${esc(s.media_url)}">`; }
    else { content.className = "story-content text-story"; content.style.background = s.bg_color; content.textContent = s.caption; }
    $("#story-caption").textContent = (s.media_url && s.kind !== "audio") ? s.caption : "";
    $$("#story-progress span i").forEach((bar,i) => { bar.style.transition="none"; bar.style.width = i<index?"100%":"0%"; });
    void $("#story-progress").offsetWidth;
    const activeBar = $$("#story-progress span i")[index];
    clearTimeout(showStoryFrame._t);
    if (s.kind === "audio") {
      // audio can run longer than the usual 5s story beat — advance on
      // playback end instead of a fixed timer, with a generous fallback
      // in case the file fails to load at all.
      activeBar.style.transition = "width 30s linear"; activeBar.style.width = "100%";
      const player = $("#story-audio-player");
      player.addEventListener("ended", () => { storyViewerState.index++; showStoryFrame(); }, { once:true });
      showStoryFrame._t = setTimeout(() => { storyViewerState.index++; showStoryFrame(); }, 30000);
    } else {
      activeBar.style.transition = "width 5s linear"; activeBar.style.width = "100%";
      showStoryFrame._t = setTimeout(() => { storyViewerState.index++; showStoryFrame(); }, 5000);
    }
  }
  function closeStoryViewer() { clearTimeout(showStoryFrame._t); $("#story-viewer").classList.add("hidden"); loadStatus(); loadIgStories(); }
  $("#story-close").addEventListener("click", closeStoryViewer);
  $("#story-viewer").addEventListener("click", (e) => { if (e.target.id !== "story-close") { storyViewerState.index++; showStoryFrame(); } });

  // ============================================================ BETA (Instagram-style)
  async function loadIgStories() {
    const res = await api("/api/stories");
    const bar = $("#ig-stories-bar"); bar.innerHTML = "";
    res.story_groups.forEach((g) => {
      const allSeen = g.stories.every((s) => s.viewed);
      const item = el("div", "ig-story-item");
      item.innerHTML = `<div class="status-ring ${allSeen?'seen':''}" style="width:58px;height:58px"><img src="${esc(g.avatar_url)}"></div><span>${g.user_id===state.me.id?"Your story":esc(g.display_name)}</span>`;
      item.addEventListener("click", () => openStoryViewer(g));
      bar.appendChild(item);
    });
  }
  async function loadIgFeed() {
    await loadIgStories();
    const res = await api("/api/pulse?limit=30");
    const list = $("#ig-feed-list"); list.innerHTML = "";
    if (res.pulses.length === 0) { list.innerHTML = `<p style="padding:20px;color:var(--text-dim);text-align:center">No posts yet. Be the first.</p>`; return; }
    res.pulses.forEach((p) => list.appendChild(renderIgPost(p)));
    applyPlatformSettingEffects("beta");
  }
  function renderIgPost(p) {
    const post = el("div", "ig-post");
    let media = p.media_url ? (p.kind === "video" ? `<video class="ig-post-media" src="${esc(p.media_url)}" controls></video>` : `<img class="ig-post-media" src="${esc(p.media_url)}">`) : "";
    post.innerHTML = `
      <div class="ig-post-head" data-user="${p.user_id}"><img src="${esc(p.avatar_url)}"><b>${esc(p.username)}</b></div>
      ${media}
      <div class="ig-post-actions">
        <button class="like-btn ${p.liked_by_me?'liked':''}"><svg class="ic"><use href="#i-heart"/></svg></button>
        <button class="comment-btn"><svg class="ic"><use href="#i-comment"/></svg></button>
        <button class="share-btn"><svg class="ic"><use href="#i-share"/></svg></button>
        <span class="spacer"></span>
        <button><svg class="ic"><use href="#i-bookmark"/></svg></button>
      </div>
      <div class="ig-post-likes">${p.likes} like${p.likes===1?'':'s'}</div>
      ${p.caption ? `<div class="ig-post-caption"><b>${esc(p.username)}</b>${esc(p.caption)}</div>` : ""}
      <div class="ig-post-comments-link">${p.comment_count ? `View all ${p.comment_count} comments` : "Add a comment…"}</div>`;
    post.querySelector(".like-btn").addEventListener("click", async (ev) => {
      const res = await api(`/api/pulse/${p.id}/like`, { method:"POST" });
      const btn = ev.currentTarget; btn.classList.toggle("liked", res.liked);
      if (res.liked) spawnHeartBurst(btn);
      p.likes += res.liked ? 1 : -1; post.querySelector(".ig-post-likes").textContent = `${p.likes} like${p.likes===1?'':'s'}`;
    });
    post.querySelector(".comment-btn").addEventListener("click", () => openCommentsDrawer(p.id));
    post.querySelector(".ig-post-comments-link").addEventListener("click", () => openCommentsDrawer(p.id));
    post.querySelector(".share-btn").addEventListener("click", (ev) => copyShareLink("pulse", p.id, ev.currentTarget));
    post.querySelector(".ig-post-head").addEventListener("click", () => openProfileViewer(p.user_id));
    return post;
  }
  $("#beta-post-input").addEventListener("change", async (e) => {
    let file = e.target.files[0]; if (!file) return;
    if (file.type.startsWith("video/")) file = await maybeTrimVideo(file);
    const soundName = await pickSound();
    const caption = prompt("Write a caption (optional):") || "";
    try { const url = await uploadFile(file); await api("/api/pulse", { method:"POST", body: JSON.stringify({ media_url:url, kind:mediaKindOf(file), caption, sound_name:soundName }) }); loadIgFeed(); loadExplore(); loadAlpha(); }
    catch (err) { alert(err.message); }
    e.target.value = "";
  });

  async function loadExplore() {
    const res = await api("/api/pulse?limit=30");
    const grid = $("#ig-explore-grid"); grid.innerHTML = "";
    res.pulses.forEach((p) => {
      const cell = el("div", "grid-cell");
      cell.innerHTML = p.media_url ? (p.kind === "video" ? `<video src="${esc(p.media_url)}" muted></video>` : `<img src="${esc(p.media_url)}">`) : `<div class="empty-cell">${esc(p.caption||'')}</div>`;
      cell.addEventListener("click", () => openCommentsDrawer(p.id));
      grid.appendChild(cell);
    });
  }

  // ---- generic profile renderer, used by Beta/Epsilon subtabs + the profile viewer modal ----
  // ---- reusable 5-star rating widget ----
  function buildStarRating(currentStars, onRate, readonly) {
    const wrap = el("div", "star-rating" + (readonly ? " readonly" : ""));
    for (let i = 1; i <= 5; i++) {
      const star = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      star.setAttribute("viewBox", "0 0 24 24");
      star.setAttribute("class", "star" + (i <= Math.round(currentStars || 0) ? " filled" : ""));
      star.innerHTML = `<polygon points="12 2 15 9 22 9.5 17 14.5 18.5 22 12 18 5.5 22 7 14.5 2 9.5 9 9"/>`;
      if (!readonly) star.addEventListener("click", () => onRate(i));
      wrap.appendChild(star);
    }
    return wrap;
  }

  async function renderProfileInto(container, userStub, opts) {
    const profile = opts.isMe ? await api("/api/me").then(r=>r.user).then(async u => { const full = await api(`/api/users/${u.id}`); return full.user; }) : (await api(`/api/users/${userStub.id}`)).user;
    container.innerHTML = `
      <div class="profile-hero">
        <img src="${esc(profile.avatar_url)}">
        <div class="profile-stats">
          <div class="profile-stat"><b id="pv-posts">-</b><span>Posts</span></div>
          <div class="profile-stat"><b>${profile.followers}</b><span>Followers</span></div>
          <div class="profile-stat"><b>${profile.following}</b><span>Following</span></div>
        </div>
      </div>
      <div class="profile-bio"><div class="dn">${esc(profile.display_name)} ${profile.is_bot?'&middot; AI':''}${profile.is_admin?' &middot; staff':''}</div>
        <div class="st">@${esc(profile.username)} — ${esc(profile.status||'')}</div>
        ${profile.bio ? `<div class="st">${esc(profile.bio)}</div>` : ""}
        <div id="pv-rating"></div>
      </div>
      <div class="profile-actions" id="pv-actions"></div>
      <div id="pv-content"></div>`;

    // ---- rating: readonly average for everyone, interactive widget for others' profiles ----
    const ratingBox = container.querySelector("#pv-rating");
    if (profile.rating) {
      const line = el("div", "rating-summary");
      const avgText = profile.rating.average != null ? `<b>${profile.rating.average}</b>/5 (${profile.rating.count})` : "No ratings yet";
      line.innerHTML = `<span>${avgText}</span>`;
      ratingBox.appendChild(line);
      if (!opts.isMe) {
        const mine = profile.rating.my_rating ? profile.rating.my_rating.stars : 0;
        const interactive = buildStarRating(mine, async (stars) => {
          const res = await api("/api/ratings", { method:"POST", body: JSON.stringify({ target_type:"user", target_id: profile.id, stars }) });
          profile.rating = res;
          renderProfileInto(container, userStub, opts);
        }, false);
        ratingBox.appendChild(interactive);
      }
    }

    const actions = container.querySelector("#pv-actions");
    if (opts.isMe) {
      const btn = el("button", "btn-ghost", "Edit profile");
      btn.addEventListener("click", () => openModal("settings-screen"));
      actions.appendChild(btn);
    } else {
      const followBtn = el("button", "btn-primary small" + (profile.is_following ? " " : ""), profile.is_following ? "Following" : "Follow");
      followBtn.className = profile.is_following ? "btn-ghost" : "btn-primary small";
      followBtn.addEventListener("click", async () => {
        if (profile.is_following) { await api("/api/unfollow", { method:"POST", body: JSON.stringify({ user_id: profile.id }) }); profile.is_following = false; followBtn.textContent = "Follow"; followBtn.className = "btn-primary small"; }
        else { await api("/api/follow", { method:"POST", body: JSON.stringify({ user_id: profile.id }) }); profile.is_following = true; followBtn.textContent = "Following"; followBtn.className = "btn-ghost"; }
      });
      const msgBtn = el("button", "btn-ghost", "Message");
      msgBtn.addEventListener("click", async () => {
        await api("/api/contacts", { method:"POST", body: JSON.stringify({ contact_id: profile.id }) });
        const res2 = await api("/api/chats"); state.chats = res2.chats;
        const chat = state.chats.find((c) => c.other_user && c.other_user.id === profile.id);
        closeModal("profile-viewer-modal");
        switchMode("gateway"); switchSubtab("gateway", "chats");
        if (chat) openChat(chat.id);
      });
      const bellBtn = el("button", "subscribe-bell-btn" + (profile.is_subscribed ? " subscribed" : ""));
      bellBtn.title = profile.is_subscribed ? "Subscribed to notifications" : "Subscribe to notifications";
      bellBtn.innerHTML = `<svg class="ic"><use href="#i-bell"/></svg>`;
      bellBtn.addEventListener("click", async () => {
        if (!profile.is_following) { alert("Follow this account first, then you can subscribe to their notifications."); return; }
        const res = await api("/api/follow/notify", { method:"PATCH", body: JSON.stringify({ user_id: profile.id }) });
        profile.is_subscribed = res.notify;
        bellBtn.classList.toggle("subscribed", res.notify);
        bellBtn.classList.add("just-subscribed"); setTimeout(() => bellBtn.classList.remove("just-subscribed"), 700);
      });
      const shareBtn = el("button", "btn-ghost pop-on-click");
      shareBtn.innerHTML = `<svg class="ic" style="width:14px;height:14px;vertical-align:-2px"><use href="#i-share"/></svg>`;
      shareBtn.title = "Copy share link";
      shareBtn.addEventListener("click", () => copyShareLink("profile", profile.id, shareBtn));
      actions.appendChild(followBtn); actions.appendChild(msgBtn); actions.appendChild(bellBtn); actions.appendChild(shareBtn);
    }
    const contentEl = container.querySelector("#pv-content");
    if (opts.kind === "list") {
      const posts = (await api(`/api/users/${profile.id}/posts`)).posts;
      container.querySelector("#pv-posts").textContent = posts.length;
      contentEl.className = "posts-list";
      posts.forEach((p) => {
        const item = el("div", "post-item");
        item.innerHTML = `<img class="post-avatar" src="${esc(p.avatar_url)}"><div class="post-body">
          <div class="post-head"><b>${esc(p.display_name)}</b><span>@${esc(p.username)} &middot; ${timeAgo(p.created_at)}</span></div>
          <div class="post-text">${esc(p.content)}</div>${p.media_url && p.media_kind === 'audio' ? `<div class="post-audio-attachment"><audio src="${esc(p.media_url)}" controls></audio></div>` : ''}</div>`;
        contentEl.appendChild(item);
      });
    } else {
      const pulses = (await api(`/api/users/${profile.id}/pulses`)).pulses;
      container.querySelector("#pv-posts").textContent = pulses.length;
      contentEl.className = "profile-grid";
      pulses.forEach((p) => {
        const cell = el("div", "grid-cell");
        cell.innerHTML = p.media_url ? (p.kind === "video" ? `<video src="${esc(p.media_url)}" muted></video>` : `<img src="${esc(p.media_url)}">`) : `<div class="empty-cell">${esc(p.caption||'')}</div>`;
        cell.addEventListener("click", () => openCommentsDrawer(p.id));
        contentEl.appendChild(cell);
      });
    }
  }
  async function openProfileViewer(userId) {
    openModal("profile-viewer-modal");
    const isMe = userId === state.me.id;
    await renderProfileInto($("#profile-viewer-body"), { id:userId }, { isMe, kind:"grid" });
    $("#profile-overflow-btn").classList.toggle("hidden", isMe);
    $("#profile-overflow-btn").onclick = () => openProfileOverflowMenu(userId);
  }
  $("#close-profile-viewer").addEventListener("click", () => { closeModal("profile-viewer-modal"); $("#profile-overflow-menu").classList.add("hidden"); });

  async function openProfileOverflowMenu(userId) {
    const menu = $("#profile-overflow-menu");
    if (!menu.classList.contains("hidden")) { menu.classList.add("hidden"); return; }
    const blocked = (await api("/api/blocks")).blocked.some((u) => u.id === userId);
    menu.innerHTML = "";
    const blockBtn = el("button", blocked ? "" : "danger", blocked ? "Unblock" : "Block");
    blockBtn.addEventListener("click", async () => {
      await api(blocked ? "/api/unblock" : "/api/block", { method:"POST", body: JSON.stringify({ user_id:userId }) });
      menu.classList.add("hidden");
      openProfileViewer(userId);
    });
    const reportBtn = el("button", "danger", "Report");
    reportBtn.addEventListener("click", async () => {
      menu.classList.add("hidden");
      const reason = prompt("Why are you reporting this account? (required)");
      if (!reason || !reason.trim()) return;
      try {
        await api("/api/report", { method:"POST", body: JSON.stringify({ target_type:"user", target_id:userId, reason: reason.trim() }) });
        alert("Report submitted. Thank you.");
      } catch (err) { alert(err.message); }
    });
    menu.appendChild(blockBtn); menu.appendChild(reportBtn);
    menu.classList.remove("hidden");
  }
  document.addEventListener("click", (e) => {
    const menu = $("#profile-overflow-menu");
    if (!menu.classList.contains("hidden") && !menu.contains(e.target) && e.target.id !== "profile-overflow-btn" && !e.target.closest("#profile-overflow-btn")) {
      menu.classList.add("hidden");
    }
  });

  // ============================================================ EPSILON (X-style)
  async function loadPosts() {
    const res = await api("/api/posts");
    $("#post-avatar").src = state.me.avatar_url;
    const list = $("#posts-list"); list.innerHTML = "";
    res.posts.forEach((p) => list.appendChild(renderPostItem(p)));
    applyPlatformSettingEffects("epsilon");
  }
  function renderPostItem(p) {
    const item = el("div", "post-item");
    item.innerHTML = `
      <img class="post-avatar" src="${esc(p.avatar_url)}" data-user="${p.user_id}">
      <div class="post-body">
        <div class="post-head" data-user="${p.user_id}"><b>${esc(p.display_name)}</b><span>@${esc(p.username)} &middot; ${timeAgo(p.created_at)}</span></div>
        <div class="post-text">${esc(p.content)}</div>
        ${p.media_url && p.media_kind === 'audio' ? `<div class="post-audio-attachment"><audio src="${esc(p.media_url)}" controls></audio></div>` : ''}
        <div class="post-actions">
          <button class="post-action reply-btn"><svg class="ic"><use href="#i-comment"/></svg><span class="reply-count">${p.replies}</span></button>
          <button class="post-action repost-btn ${p.reposted_by_me?'reposted':''}"><svg class="ic"><use href="#i-repost"/></svg>${p.reposts}</button>
          <button class="post-action like-btn ${p.liked_by_me?'liked':''}"><svg class="ic"><use href="#i-heart"/></svg>${p.likes}</button>
          <button class="post-action share-btn"><svg class="ic"><use href="#i-share"/></svg></button>
        </div>
      </div>`;
    item.querySelector(".like-btn").addEventListener("click", async (ev) => {
      const r = await api(`/api/posts/${p.id}/like`,{method:"POST"});
      if (r.liked) spawnHeartBurst(ev.currentTarget);
      loadPosts();
    });
    item.querySelector(".repost-btn").addEventListener("click", async () => { await api(`/api/posts/${p.id}/repost`,{method:"POST"}); loadPosts(); });
    item.querySelector(".share-btn").addEventListener("click", (ev) => copyShareLink("post", p.id, ev.currentTarget));
    item.querySelectorAll("[data-user]").forEach((n) => n.addEventListener("click", () => openProfileViewer(p.user_id)));
    return item;
  }
  $("#post-input").addEventListener("input", (e) => { $("#post-counter").textContent = 280 - e.target.value.length; });
  let pendingPostAudioUrl = null;
  $("#post-attach-audio-btn").addEventListener("click", () => $("#post-audio-input").click());
  $("#post-audio-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try {
      pendingPostAudioUrl = await uploadFile(file);
      const preview = $("#post-audio-preview");
      preview.classList.remove("hidden");
      preview.innerHTML = `<audio src="${esc(pendingPostAudioUrl)}" controls></audio>`;
    } catch (err) { alert(err.message); }
    e.target.value = "";
  });
  $("#post-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#post-input"); const content = input.value.trim(); if (!content) return;
    input.value = ""; $("#post-counter").textContent = "280";
    const body = { content };
    if (pendingPostAudioUrl) { body.media_url = pendingPostAudioUrl; body.media_kind = "audio"; }
    pendingPostAudioUrl = null; $("#post-audio-preview").classList.add("hidden"); $("#post-audio-preview").innerHTML = "";
    await api("/api/posts", { method:"POST", body: JSON.stringify(body) });
    loadPosts();
  });

  let xSearchDebounce;
  $("#x-search-input").addEventListener("input", (e) => { clearTimeout(xSearchDebounce); xSearchDebounce = setTimeout(() => runXSearch(e.target.value.trim()), 250); });
  async function runXSearch(q) {
    const wrap = $("#x-search-results"); wrap.innerHTML = "";
    if (!q) return;
    const res = await api(`/api/search?q=${encodeURIComponent(q)}`);
    res.users.forEach((u) => {
      const row = el("div", "x-user-row");
      row.innerHTML = `<img src="${esc(u.avatar_url)}"><div class="grow"><b>${esc(u.display_name)}</b><span>@${esc(u.username)}</span></div>`;
      row.addEventListener("click", () => openProfileViewer(u.id));
      wrap.appendChild(row);
    });
    res.posts.forEach((p) => wrap.appendChild(renderPostItem(p)));
  }

  async function loadNotifications() {
    const res = await api("/api/notifications");
    const list = $("#x-notif-list"); list.innerHTML = "";
    if (res.notifications.length === 0) { list.innerHTML = `<p style="padding:20px;color:var(--text-dim);text-align:center">No notifications yet.</p>`; return; }
    const KIND_TEXT = { like:"liked", repost:"reposted", reply:"replied to", pulse_like:"liked", pulse_comment:"commented on", follow:"" };
    const KIND_ICON = { like:"heart", repost:"repost", reply:"comment", pulse_like:"heart", pulse_comment:"comment", follow:"user" };
    const KIND_CLASS = { like:"like", repost:"repost", reply:"reply", pulse_like:"like", pulse_comment:"reply", follow:"reply" };
    res.notifications.forEach((n) => {
      const row = el("div", "notif-row");
      row.innerHTML = `<span class="notif-icon ${KIND_CLASS[n.kind]}"><svg class="ic"><use href="#i-${KIND_ICON[n.kind]}"/></svg></span>
        <div><div class="notif-text"><b>${esc(n.actor.display_name)}</b> ${KIND_TEXT[n.kind]} ${esc(n.target)}</div>
        <div class="notif-time">${timeAgo(n.ts)}</div></div>`;
      row.addEventListener("click", () => openProfileViewer(n.actor.id));
      list.appendChild(row);
    });
  }

  // ============================================================ ALPHA (TikTok-style)
  async function loadAlpha() {
    const res = await api(`/api/pulse?limit=30&scope=${state.alphaScope}`);
    state.alphaItems = res.pulses;
    renderAlphaFeed(res.pulses);
    applyPlatformSettingEffects("alpha");
  }
  function renderAlphaFeed(items) {
    const feed = $("#pulse-feed"); feed.innerHTML = "";
    if (items.length === 0) { feed.innerHTML = `<div class="pulse-item text-only"><div class="pulse-overlay"><div class="pulse-user">Nothing here yet</div><div class="pulse-caption">Tap + to post the first Pulse.</div></div></div>`; return; }
    items.forEach((p) => {
      const item = el("div", "pulse-item" + (p.media_url?"":" text-only"));
      let mediaHtml = "";
      if (p.media_url) mediaHtml = p.kind === "video" ? `<video class="pulse-video" src="${esc(p.media_url)}" loop muted playsinline></video>` : `<img src="${esc(p.media_url)}">`;
      item.innerHTML = `${mediaHtml}
        <div class="pulse-overlay" data-user="${p.user_id}">
          <div class="pulse-user">@${esc(p.username)}</div>
          <div class="pulse-caption">${esc(p.caption||"")}</div>
          <div class="pulse-sound">&#9834; ${esc(p.sound_name)}</div>
        </div>
        <div class="pulse-actions">
          <button class="pulse-action-btn like-btn ${p.liked_by_me?'liked':''}"><svg class="ic" style="width:28px;height:28px"><use href="#i-heart"/></svg><span>${p.likes}</span></button>
          <button class="pulse-action-btn comment-btn"><svg class="ic" style="width:28px;height:28px"><use href="#i-comment"/></svg><span>${p.comment_count}</span></button>
          <button class="pulse-action-btn share-btn"><svg class="ic" style="width:28px;height:28px"><use href="#i-share"/></svg><span>Share</span></button>
        </div>`;
      item.querySelector(".like-btn").addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const res = await api(`/api/pulse/${p.id}/like`, { method:"POST" });
        const btn = ev.currentTarget; btn.classList.toggle("liked", res.liked);
        if (res.liked) spawnHeartBurst(btn);
        btn.querySelector("span").textContent = Number(btn.querySelector("span").textContent) + (res.liked?1:-1);
      });
      item.querySelector(".comment-btn").addEventListener("click", (ev) => { ev.stopPropagation(); openCommentsDrawer(p.id); });
      item.querySelector(".share-btn").addEventListener("click", (ev) => { ev.stopPropagation(); copyShareLink("pulse", p.id, ev.currentTarget); });
      item.querySelector(".pulse-overlay").addEventListener("click", () => openProfileViewer(p.user_id));
      const video = item.querySelector("video");
      if (video) { const obs = new IntersectionObserver((entries) => entries.forEach((e) => e.isIntersecting ? video.play().catch(()=>{}) : video.pause()), { threshold:0.6 }); obs.observe(item); }
      feed.appendChild(item);
    });
  }
  $("#new-pulse-btn").addEventListener("click", () => $("#pulse-input").click());
  $("#new-pulse-camera-btn").addEventListener("click", () => openCameraCapture("pulse"));
  $("#pulse-input").addEventListener("change", async (e) => {
    let file = e.target.files[0]; if (!file) return;
    if (file.type.startsWith("video/")) file = await maybeTrimVideo(file);
    const soundName = await pickSound();
    const caption = prompt("Caption for your Pulse (optional):") || "";
    try { const url = await uploadFile(file); await api("/api/pulse", { method:"POST", body: JSON.stringify({ media_url:url, kind:mediaKindOf(file), caption, sound_name:soundName }) }); loadAlpha(); loadIgFeed(); loadExplore(); }
    catch (err) { alert(err.message); }
    e.target.value = "";
  });

  // ---- comments drawer (used by Alpha + Beta) ----
  async function openCommentsDrawer(pulseId) {
    state.activeDrawerPulseId = pulseId;
    openModal("comments-drawer"); $("#comments-drawer").classList.remove("hidden");
    await refreshDrawerComments();
  }
  async function refreshDrawerComments() {
    const res = await api(`/api/pulse/${state.activeDrawerPulseId}/comments`);
    const body = $("#drawer-body"); body.innerHTML = "";
    if (res.comments.length === 0) body.innerHTML = `<p style="color:var(--text-dim);text-align:center;padding:20px">No comments yet.</p>`;
    res.comments.forEach((c) => {
      const row = el("div", "drawer-comment");
      row.innerHTML = `<img src="${esc(c.avatar_url)}"><div><b>${esc(c.username)}</b><span>${esc(c.content)}</span></div>`;
      body.appendChild(row);
    });
  }
  $("#drawer-close").addEventListener("click", () => $("#comments-drawer").classList.add("hidden"));
  $("#comments-drawer").addEventListener("click", (e) => { if (e.target.id === "comments-drawer") $("#comments-drawer").classList.add("hidden"); });
  $("#drawer-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#drawer-input"); const content = input.value.trim(); if (!content) return;
    input.value = "";
    await api(`/api/pulse/${state.activeDrawerPulseId}/comments`, { method:"POST", body: JSON.stringify({ content }) });
    refreshDrawerComments();
  });

  // ============================================================ AI providers (Gateway)
  async function loadProviders() {
    const res = await api("/api/ai/providers"); state.providers = res.providers;
    const sel = $("#gateway-provider"); sel.innerHTML = "";
    res.providers.forEach((p) => { const opt = el("option"); opt.value = p.id; opt.textContent = p.label; if (p.id === res.default) opt.selected = true; sel.appendChild(opt); });
  }

  tryResume();
})();
"""
