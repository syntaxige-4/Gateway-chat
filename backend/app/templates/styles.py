"""
styles.py — the entire stylesheet lives here as a Python string. There is no
separate .css file anywhere in this project; Python owns and serves it.
"""

CSS = """
:root {
  --bg: #0b0f14; --panel: #121821; --panel-2: #161e29; --border: #223041;
  --text: #e9eef3; --text-dim: #8ba0b4; --accent: #3ee6b0; --accent-2: #7c5cff;
  --accent-3: #ff5c8a; --bubble-me: #1f6f5c; --bubble-them: #1a2330; --radius: 16px; --danger: #ff5c5c;
  --tiktok-cyan: #25f4ee; --tiktok-pink: #fe2c55;
  --panel-glass: rgba(18,24,33,.72); --gold: #f4c95d;
}

/* ============================== THEMES ============================== */
[data-theme="light"] {
  --bg: #f3f5f8; --panel: #ffffff; --panel-2: #eef1f5; --border: #dde3ea;
  --text: #12181f; --text-dim: #61717f; --bubble-me: #bdeee0; --bubble-them: #eef1f5;
  --panel-glass: rgba(255,255,255,.72);
}
[data-theme="light"] .msg-row.me .msg-bubble { color:#0b2b21; }
[data-theme="amoled"] {
  --bg: #000000; --panel: #060606; --panel-2: #0d0d0d; --border: #1c1c1c;
  --panel-glass: rgba(0,0,0,.7);
}
[data-theme="sunset"] {
  --bg: #180b13; --panel: #23121c; --panel-2: #2b1622; --border: #3a1d2c;
  --accent: #ff8a3d; --bubble-me: #6e3418; --panel-glass: rgba(35,18,28,.72);
}
[data-theme="ocean"] {
  --bg: #061622; --panel: #0c2334; --panel-2: #103049; --border: #163f5c;
  --accent: #3ec9e6; --bubble-me: #0f5570; --panel-glass: rgba(12,35,52,.72);
}

/* ============================== PARTICLE BACKGROUND ============================== */
#particle-canvas { position:fixed; inset:0; width:100%; height:100%; z-index:0; pointer-events:none; display:block; }
.glass { background:var(--panel-glass) !important; backdrop-filter:blur(16px) saturate(150%); -webkit-backdrop-filter:blur(16px) saturate(150%); }

* { box-sizing: border-box; }
html, body { margin:0; padding:0; height:100%; background:var(--bg); color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; overflow:hidden; }
button { font-family:inherit; cursor:pointer; }
input, textarea, select { font-family:inherit; }
.hidden { display:none !important; }
svg.ic { width:20px; height:20px; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
a { color: inherit; }

/* ============================== AUTH ============================== */
.auth-screen { height:100vh; display:flex; align-items:center; justify-content:center; position:relative; z-index:1; }
.auth-card { width:360px; max-width:90vw; background:var(--panel-glass); backdrop-filter:blur(18px) saturate(150%); -webkit-backdrop-filter:blur(18px) saturate(150%); border:1px solid var(--border); border-radius:20px; padding:32px 28px; box-shadow:0 20px 60px rgba(0,0,0,.5); position:relative; z-index:1; }
.auth-brand { text-align:center; margin-bottom:20px; }
.auth-brand .mark-wrap { width:56px; height:56px; margin:0 auto 10px; border-radius:18px; overflow:hidden; }
.auth-brand h1 { margin:0; font-size:22px; }
.auth-brand p { margin:4px 0 0; color:var(--text-dim); font-size:13px; }
.auth-tabs { display:flex; gap:6px; background:var(--panel-2); border-radius:12px; padding:4px; margin-bottom:18px; }
.auth-tab { flex:1; border:none; background:transparent; color:var(--text-dim); padding:9px 0; border-radius:9px; font-weight:600; font-size:13px; }
.auth-tab.active { background:var(--accent); color:#06110d; }
.auth-form { display:flex; flex-direction:column; gap:10px; }
.auth-form.hidden { display:none; }
.auth-form input { background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:12px 14px; border-radius:10px; font-size:14px; outline:none; }
.auth-form input:focus { border-color:var(--accent); }
.btn-primary { background:linear-gradient(135deg,var(--accent),#29c99a); border:none; color:#06110d; padding:12px 16px; border-radius:10px; font-weight:700; font-size:14px; margin-top:4px; }
.btn-primary.small { padding:8px 14px; font-size:13px; margin-top:0; }
.btn-primary:active { transform:scale(.98); }
.btn-ghost { background: var(--panel-2); border:1px solid var(--border); color: var(--text); padding:7px 13px; border-radius:10px; font-weight:600; font-size:12px; }
.auth-error { color:var(--danger); font-size:12px; min-height:14px; margin:2px 0 0; }

/* ============================== APP SHELL ============================== */
.app { display:flex; flex-direction:column; height:100vh; position:relative; z-index:1; }

/* ---- persistent top bar ---- */
.topbar { height:54px; flex-shrink:0; display:flex; align-items:center; justify-content:space-between;
  padding:0 14px; border-bottom:1px solid var(--border); }
.topbar-brand { display:flex; align-items:center; gap:10px; }
.topbar-brand .mark-wrap { width:30px; height:30px; border-radius:9px; overflow:hidden; }
.topbar-brand .mode-name { font-weight:800; font-size:15px; letter-spacing:.2px; display:flex; align-items:center; gap:6px; }
.topbar-actions { display:flex; align-items:center; gap:8px; }
.topbar-btn { width:34px; height:34px; border-radius:10px; background:var(--panel-2); border:1px solid var(--border); color:var(--text); display:flex; align-items:center; justify-content:center; }
.topbar-btn:hover { border-color: var(--accent); }
.topbar-avatar { width:32px; height:32px; border-radius:50%; object-fit:cover; border:2px solid var(--accent); cursor:pointer; }
.premium-chip { display:inline-flex; align-items:center; gap:3px; background:linear-gradient(135deg,var(--gold),#c9962e); color:#2a1c00; font-size:9.5px; font-weight:800; padding:2px 6px; border-radius:7px; letter-spacing:.3px; }

/* ---- mode content area ---- */
.mode-area { flex:1; min-height:0; display:flex; flex-direction:column; }
.mode-view { display:none; flex:1; min-height:0; flex-direction:column; }
.mode-view.active { display:flex; }

/* ---- segmented sub-tabs, used inside every mode ---- */
.subtabs { display:flex; gap:6px; padding:8px 14px; border-bottom:1px solid var(--border); flex-shrink:0; overflow-x:auto; }
.subtab { border:none; background:var(--panel-2); color:var(--text-dim); padding:7px 14px; border-radius:999px; font-size:12.5px; font-weight:700; white-space:nowrap; }
.subtab.active { background:var(--accent); color:#06110d; }
.subpage { display:none; flex:1; min-height:0; flex-direction:column; }
.subpage.active { display:flex; }

/* ---- space-switcher dropdown (hamburger menu — replaces the old bottom nav) ---- */
.orbit-badge { background:var(--accent-3); color:#fff; font-size:9px; font-weight:800; min-width:14px; height:14px; border-radius:7px; display:flex; align-items:center; justify-content:center; padding:0 3px; }
#badge-hamburger { position:absolute; top:2px; right:2px; width:9px; height:9px; min-width:0; border-radius:50%; padding:0; }
.topbar-brand .topbar-btn { position:relative; }
.space-menu-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:70; display:flex; align-items:flex-start; justify-content:flex-start; padding-top:54px; }
.space-menu { width:300px; max-width:88vw; background:var(--panel); border:1px solid var(--border); border-right:none; border-radius:0 0 18px 0; box-shadow:10px 20px 40px rgba(0,0,0,.5); padding:8px; max-height:calc(100vh - 54px); overflow-y:auto; }
.space-menu-header { font-size:11px; text-transform:uppercase; letter-spacing:.6px; color:var(--text-dim); font-weight:700; padding:10px 12px 6px; }
.space-menu-item { display:flex; align-items:center; gap:12px; width:100%; text-align:left; background:transparent; border:none; padding:10px 12px; border-radius:12px; position:relative; }
.space-menu-item:hover { background:var(--panel-2); }
.space-menu-item.current { background:rgba(62,230,176,.08); }
.space-menu-item .mark-wrap { width:34px; height:34px; border-radius:10px; overflow:hidden; flex-shrink:0; }
.space-menu-item .mark-wrap.settings-mark { background:var(--panel-2); display:flex; align-items:center; justify-content:center; color:var(--text); }
.space-menu-item .grow { flex:1; min-width:0; }
.space-menu-item .grow b { display:block; font-size:14px; }
.space-menu-item .grow span { font-size:11.5px; color:var(--text-dim); }
.space-menu-item .orbit-badge { position:absolute; top:6px; right:10px; }
.space-menu-divider { height:1px; background:var(--border); margin:8px 4px; }

/* ============================== GATEWAY (chat) ============================== */
.gateway-chats-layout { flex:1; display:flex; min-height:0; }
.chat-list-pane { width:320px; flex-shrink:0; background:var(--panel); border-right:1px solid var(--border); display:flex; flex-direction:column; }
.search-box { padding:10px 14px; }
.search-box input { width:100%; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:9px 12px; border-radius:10px; font-size:13px; outline:none; }
.chat-list { flex:1; overflow-y:auto; }
.chat-item { display:flex; gap:10px; padding:10px 14px; align-items:center; cursor:pointer; border-bottom:1px solid rgba(255,255,255,.03); }
.chat-item:hover, .chat-item.active { background:var(--panel-2); }
.chat-item img { width:46px; height:46px; border-radius:50%; object-fit:cover; flex-shrink:0; }
.chat-item-main { flex:1; min-width:0; }
.chat-item-top { display:flex; justify-content:space-between; align-items:baseline; }
.chat-item-name { font-weight:600; font-size:14px; }
.chat-item-time { font-size:11px; color:var(--text-dim); }
.chat-item-bottom { display:flex; justify-content:space-between; align-items:center; margin-top:2px; }
.chat-item-preview { font-size:12px; color:var(--text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:190px; }
.chat-item-unread { background:var(--accent); color:#06110d; font-size:10px; font-weight:800; min-width:18px; height:18px; border-radius:9px; display:flex; align-items:center; justify-content:center; padding:0 5px; }

.chat-thread-pane { flex:1; min-width:0; display:flex; flex-direction:column; position:relative;
  background: radial-gradient(circle at 100% 0%, rgba(124,92,255,.05), transparent 40%), var(--bg); }
.empty-thread { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--text-dim); gap:10px; }
.empty-badge { width:64px; height:64px; border-radius:50%; background:var(--panel-2); display:flex; align-items:center; justify-content:center; font-size:26px; font-weight:800; color:var(--accent); }
.thread { flex:1; display:flex; flex-direction:column; min-height:0; }
.thread-header { display:flex; align-items:center; gap:12px; padding:12px 18px; border-bottom:1px solid var(--border); background:var(--panel-glass); backdrop-filter:blur(16px) saturate(150%); -webkit-backdrop-filter:blur(16px) saturate(150%); }
.thread-back { display:none; }
.thread-avatar { width:40px; height:40px; border-radius:50%; object-fit:cover; }
.thread-title { flex:1; min-width:0; }
.thread-name { font-weight:700; font-size:14px; }
.thread-status { font-size:12px; color:var(--text-dim); }
.provider-select { background:var(--panel-2); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:6px 8px; font-size:12px; }
.thread-messages { flex:1; overflow-y:auto; padding:18px; display:flex; flex-direction:column; gap:8px; }
.msg-row { display:flex; }
.msg-row.me { justify-content:flex-end; }
.msg-bubble { max-width:62%; padding:9px 13px; border-radius:var(--radius); font-size:14px; line-height:1.4; position:relative; }
.msg-row.me .msg-bubble { background:var(--bubble-me); border-bottom-right-radius:4px; }
.msg-row.them .msg-bubble { background:var(--bubble-them); border-bottom-left-radius:4px; }
.msg-media { max-width:260px; border-radius:10px; margin-bottom:6px; display:block; }
.msg-meta { font-size:10px; color:var(--text-dim); margin-top:3px; text-align:right; }
.msg-row.them .msg-meta { text-align:left; }
.thread-composer { display:flex; align-items:center; gap:8px; padding:12px 16px; border-top:1px solid var(--border); background:var(--panel-glass); backdrop-filter:blur(16px) saturate(150%); -webkit-backdrop-filter:blur(16px) saturate(150%); }
.thread-composer input[type=text] { flex:1; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:11px 14px; border-radius:20px; outline:none; font-size:14px; }
.thread-composer input[type=text]:focus { border-color:var(--accent); }
.icon-btn { background:var(--panel-2); border:1px solid var(--border); color:var(--text); width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center; }
.icon-btn:hover { border-color:var(--accent); }
.send-btn { background:var(--accent); color:#06110d; border:none; }

/* ---- Status (WhatsApp-style story list, inside Gateway mode) ---- */
.status-list { flex:1; overflow-y:auto; }
.status-row { display:flex; gap:12px; align-items:center; padding:12px 16px; border-bottom:1px solid rgba(255,255,255,.03); cursor:pointer; }
.status-row:hover { background:var(--panel-2); }
.status-ring { width:52px; height:52px; border-radius:50%; padding:3px; background:conic-gradient(var(--accent),var(--accent-2),var(--accent-3),var(--accent)); flex-shrink:0; }
.status-ring.seen { background:var(--border); }
.status-ring img { width:100%; height:100%; border-radius:50%; object-fit:cover; border:2px solid var(--bg); }
.status-section-label { padding:10px 16px 4px; font-size:12px; color:var(--text-dim); font-weight:700; text-transform:uppercase; letter-spacing:.5px; }
.status-my-row .status-ring { background:var(--border); position:relative; }
.status-my-row .status-plus { position:absolute; bottom:-2px; right:-2px; width:18px; height:18px; border-radius:50%; background:var(--accent); color:#06110d; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:13px; border:2px solid var(--bg); }

/* story viewer, shared by Gateway/Beta */
.story-viewer { position:fixed; inset:0; background:#000; z-index:50; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.story-progress { position:absolute; top:10px; left:10px; right:10px; display:flex; gap:4px; }
.story-progress span { flex:1; height:3px; background:rgba(255,255,255,.3); border-radius:2px; overflow:hidden; }
.story-progress span i { display:block; height:100%; width:0; background:#fff; }
.story-close { position:absolute; top:16px; right:16px; background:transparent; border:none; color:#fff; font-size:26px; }
.story-content { max-width:420px; width:90vw; max-height:78vh; display:flex; align-items:center; justify-content:center; border-radius:14px; overflow:hidden; }
.story-content img, .story-content video { width:100%; max-height:78vh; object-fit:contain; border-radius:14px; }
.story-content.text-story { aspect-ratio:9/16; width:340px; display:flex; align-items:center; justify-content:center; padding:30px; text-align:center; font-size:22px; font-weight:700; color:#fff; }
.story-caption { color:#fff; margin-top:12px; font-size:14px; }

/* ============================== BETA (Instagram) ============================== */
.ig-feed-page { flex:1; overflow-y:auto; }
.ig-stories-bar { display:flex; gap:14px; padding:14px 16px; overflow-x:auto; border-bottom:1px solid var(--border); }
.ig-story-item { display:flex; flex-direction:column; align-items:center; gap:5px; flex-shrink:0; cursor:pointer; }
.ig-story-item span { font-size:10.5px; color:var(--text-dim); max-width:64px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ig-post { border-bottom:1px solid var(--border); padding-bottom:10px; margin-bottom:6px; }
.ig-post-head { display:flex; align-items:center; gap:10px; padding:10px 14px; }
.ig-post-head img { width:34px; height:34px; border-radius:50%; object-fit:cover; }
.ig-post-head b { font-size:13.5px; }
.ig-post-media { width:100%; max-height:600px; object-fit:contain; background:#05070a; display:block; }
.ig-post-actions { display:flex; align-items:center; gap:14px; padding:10px 14px 2px; }
.ig-post-actions button { background:transparent; border:none; color:var(--text); }
.ig-post-actions button.liked { color:var(--accent-3); }
.ig-post-actions .spacer { flex:1; }
.ig-post-likes { padding:2px 14px; font-size:13px; font-weight:700; }
.ig-post-caption { padding:2px 14px 4px; font-size:13.5px; }
.ig-post-caption b { margin-right:6px; }
.ig-post-comments-link { padding:0 14px; font-size:12.5px; color:var(--text-dim); }

.ig-explore-grid, .profile-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:2px; padding:2px; overflow-y:auto; flex:1; }
.grid-cell { aspect-ratio:1/1; background:#05070a; overflow:hidden; cursor:pointer; position:relative; }
.grid-cell img, .grid-cell video { width:100%; height:100%; object-fit:cover; }
.grid-cell.empty-cell { display:flex; align-items:center; justify-content:center; color:var(--text-dim); font-size:11px; background:var(--panel-2); }

.profile-page { flex:1; overflow-y:auto; }
.profile-hero { display:flex; gap:20px; padding:20px 16px; align-items:center; }
.profile-hero img { width:84px; height:84px; border-radius:50%; object-fit:cover; flex-shrink:0; }
.profile-stats { display:flex; gap:22px; flex:1; }
.profile-stat { text-align:center; }
.profile-stat b { display:block; font-size:16px; }
.profile-stat span { font-size:11.5px; color:var(--text-dim); }
.profile-bio { padding:0 16px 14px; }
.profile-bio .dn { font-weight:700; font-size:14px; }
.profile-bio .st { font-size:12.5px; color:var(--text-dim); margin-top:2px; }
.profile-actions { display:flex; gap:8px; padding:0 16px 14px; }
.profile-actions button { flex:1; }

/* ============================== EPSILON (X) ============================== */
.x-home-page { flex:1; overflow-y:auto; }
.composer-post { display:flex; gap:12px; padding:16px 18px; border-bottom:1px solid var(--border); }
.post-avatar { width:42px; height:42px; border-radius:50%; object-fit:cover; flex-shrink:0; }
.post-form-main { flex:1; }
.post-form-main textarea { width:100%; background:transparent; border:none; color:var(--text); resize:none; font-size:15px; outline:none; min-height:50px; font-family:inherit; }
.post-form-footer { display:flex; justify-content:flex-end; align-items:center; gap:12px; }
.post-counter { font-size:12px; color:var(--text-dim); }
.posts-list { display:flex; flex-direction:column; }
.post-item { display:flex; gap:12px; padding:14px 18px; border-bottom:1px solid var(--border); }
.post-body { flex:1; min-width:0; }
.post-head { font-size:14px; }
.post-head b { margin-right:6px; }
.post-head span { color:var(--text-dim); font-size:13px; }
.post-text { font-size:14px; margin:4px 0 8px; line-height:1.4; white-space:pre-wrap; word-break:break-word; }
.post-actions { display:flex; gap:28px; color:var(--text-dim); }
.post-action { display:flex; align-items:center; gap:6px; background:transparent; border:none; color:inherit; font-size:13px; }
.post-action.liked { color:var(--accent-3); }
.post-action.reposted { color:var(--accent); }

.x-search-page { flex:1; display:flex; flex-direction:column; min-height:0; }
.x-search-box { padding:12px 16px; }
.x-search-box input { width:100%; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:10px 14px; border-radius:20px; outline:none; font-size:14px; }
.x-search-results { flex:1; overflow-y:auto; }
.x-user-row { display:flex; align-items:center; gap:10px; padding:10px 16px; border-bottom:1px solid rgba(255,255,255,.03); }
.x-user-row img { width:38px; height:38px; border-radius:50%; object-fit:cover; }
.x-user-row .grow { flex:1; }
.x-user-row .grow b { font-size:13.5px; display:block; }
.x-user-row .grow span { font-size:12px; color:var(--text-dim); }

.x-notif-page { flex:1; overflow-y:auto; }
.notif-row { display:flex; gap:12px; padding:12px 16px; border-bottom:1px solid rgba(255,255,255,.03); align-items:flex-start; }
.notif-row img { width:34px; height:34px; border-radius:50%; object-fit:cover; }
.notif-icon { width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.notif-icon.like { background:rgba(255,92,138,.15); color:var(--accent-3); }
.notif-icon.repost { background:rgba(62,230,176,.15); color:var(--accent); }
.notif-icon.reply { background:rgba(124,92,255,.15); color:var(--accent-2); }
.notif-text { font-size:13.5px; }
.notif-time { font-size:11.5px; color:var(--text-dim); margin-top:2px; }
.follow-btn { background:var(--accent); color:#06110d; border:none; padding:6px 14px; border-radius:16px; font-weight:700; font-size:12px; }
.follow-btn.following { background:transparent; border:1px solid var(--border); color:var(--text); }

/* ============================== ALPHA (TikTok) ============================== */
.alpha-page { flex:1; position:relative; background:#000; min-height:0; }
.pulse-feed { height:100%; overflow-y:scroll; scroll-snap-type:y mandatory; }
.pulse-item { height:100%; scroll-snap-align:start; position:relative; display:flex; align-items:center; justify-content:center; background:#05070a; }
.pulse-item img, .pulse-item video { max-height:100%; max-width:100%; object-fit:contain; }
.pulse-item.text-only { background:linear-gradient(160deg,#0d1f22,#0f3a52 55%,#0d5c56); }
.pulse-overlay { position:absolute; left:16px; bottom:26px; right:90px; color:#fff; }
.pulse-user { font-weight:700; font-size:14px; margin-bottom:4px; }
.pulse-caption { font-size:13px; opacity:.92; }
.pulse-sound { font-size:12px; opacity:.7; margin-top:4px; }
.pulse-actions { position:absolute; right:12px; bottom:30px; display:flex; flex-direction:column; align-items:center; gap:18px; color:#fff; }
.pulse-action-btn { display:flex; flex-direction:column; align-items:center; gap:3px; background:transparent; border:none; color:#fff; }
.pulse-action-btn svg { width:28px; height:28px; }
.pulse-action-btn span { font-size:11px; font-weight:600; }
.pulse-action-btn.liked svg { fill:var(--tiktok-pink); stroke:var(--tiktok-pink); }
.fab { position:absolute; right:14px; top:10px; width:38px; height:38px; border-radius:50%; background:rgba(255,255,255,.12); color:#fff; border:none; font-size:20px; font-weight:800; z-index:5; backdrop-filter:blur(4px); }

/* comments drawer, used by Alpha */
.drawer-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:55; display:flex; align-items:flex-end; }
.drawer { width:100%; max-height:65vh; background:var(--panel); border-radius:18px 18px 0 0; display:flex; flex-direction:column; }
.drawer-header { padding:14px 16px; border-bottom:1px solid var(--border); font-weight:700; font-size:14px; text-align:center; position:relative; }
.drawer-close { position:absolute; right:12px; top:10px; background:transparent; border:none; color:var(--text-dim); font-size:20px; }
.drawer-body { flex:1; overflow-y:auto; padding:8px 16px; }
.drawer-comment { display:flex; gap:10px; padding:8px 0; }
.drawer-comment img { width:30px; height:30px; border-radius:50%; object-fit:cover; }
.drawer-comment b { font-size:12.5px; margin-right:6px; }
.drawer-comment span { font-size:13px; }
.drawer-input-row { display:flex; gap:8px; padding:10px 14px; border-top:1px solid var(--border); }
.drawer-input-row input { flex:1; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:9px 12px; border-radius:18px; outline:none; font-size:13px; }

/* ============================== SETTINGS SCREEN ============================== */
.settings-screen { position:fixed; inset:0; background:var(--bg); z-index:70; display:flex; flex-direction:column; }
.settings-screen.hidden { display:none; }
.settings-header { display:flex; align-items:center; gap:12px; padding:14px 16px; border-bottom:1px solid var(--border); background:var(--panel); }
.settings-header h2 { margin:0; font-size:16px; flex:1; }
.settings-body { flex:1; overflow-y:auto; padding:18px 16px 40px; }
.settings-section { margin-bottom:26px; }
.settings-section h3 { font-size:12px; text-transform:uppercase; letter-spacing:.6px; color:var(--text-dim); margin:0 0 10px; }
.mode-picker { display:flex; flex-direction:column; gap:10px; }
.mode-card { display:flex; align-items:center; gap:14px; background:var(--panel); border:1.5px solid var(--border); border-radius:14px; padding:12px 14px; }
.mode-card .mark-wrap { width:42px; height:42px; border-radius:12px; overflow:hidden; flex-shrink:0; }
.mode-card .grow { flex:1; }
.mode-card .grow b { display:block; font-size:14.5px; }
.mode-card .grow span { font-size:12px; color:var(--text-dim); }
.mode-card.selected { border-color:var(--accent); background:rgba(62,230,176,.06); }
.mode-card input[type=radio] { width:18px; height:18px; accent-color:var(--accent); }
.profile-edit-form { display:flex; flex-direction:column; align-items:center; gap:8px; }
.profile-edit-form img { width:84px; height:84px; border-radius:50%; object-fit:cover; margin-bottom:6px; }
.avatar-edit-wrap { position:relative; width:84px; height:84px; cursor:pointer; margin-bottom:6px; }
.avatar-edit-wrap img { width:84px; height:84px; border-radius:50%; object-fit:cover; margin-bottom:0; display:block; }
.avatar-edit-badge { position:absolute; right:-2px; bottom:-2px; width:28px; height:28px; border-radius:50%; background:var(--accent); color:#04120b; display:flex; align-items:center; justify-content:center; border:2px solid var(--panel); }
.avatar-edit-badge svg { width:14px; height:14px; }
.profile-edit-form input, .profile-edit-form textarea { width:100%; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:10px 12px; border-radius:10px; font-size:13px; outline:none; font-family:inherit; }
.profile-edit-form textarea { min-height:60px; resize:vertical; }
.permission-row { display:flex; align-items:center; gap:12px; background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:12px 14px; margin-bottom:8px; }
.permission-row .picon { width:36px; height:36px; border-radius:10px; background:var(--panel-2); display:flex; align-items:center; justify-content:center; color:var(--accent); flex-shrink:0; }
.permission-row .grow b { display:block; font-size:13.5px; }
.permission-row .grow span { font-size:11.5px; color:var(--text-dim); }
.permission-status { font-size:11px; color:var(--text-dim); background:var(--panel-2); padding:4px 9px; border-radius:8px; white-space:nowrap; }

/* ---- appearance / theme picker ---- */
.theme-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(84px,1fr)); gap:10px; }
.theme-swatch { border:1.5px solid var(--border); border-radius:14px; padding:10px; cursor:pointer; text-align:center; background:var(--panel); }
.theme-swatch.selected { border-color:var(--accent); box-shadow:0 0 0 2px rgba(62,230,176,.25); }
.theme-swatch .swatch-preview { height:38px; border-radius:9px; margin-bottom:7px; position:relative; }
.theme-swatch .theme-lock { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:15px; background:rgba(0,0,0,.35); border-radius:9px; }
.theme-swatch.locked { opacity:.55; }
.theme-swatch span { font-size:11.5px; font-weight:700; }

/* ---- accounts switcher ---- */
.account-row { display:flex; align-items:center; gap:12px; background:var(--panel); border:1.5px solid var(--border); border-radius:14px; padding:10px 12px; margin-bottom:8px; }
.account-row.current { border-color:var(--accent); }
.account-row img { width:38px; height:38px; border-radius:50%; object-fit:cover; flex-shrink:0; }
.account-row .grow { flex:1; min-width:0; }
.account-row .grow b { display:block; font-size:13.5px; }
.account-row .grow span { font-size:11.5px; color:var(--text-dim); }
.account-nickname-input { background:transparent; border:none; color:var(--text-dim); font-size:11px; padding:0; outline:none; border-bottom:1px dashed transparent; width:100%; }
.account-nickname-input:focus { border-bottom-color:var(--accent); }
.account-remove-btn { background:transparent; border:none; color:var(--text-dim); font-size:18px; padding:4px; }
.add-account-btn { width:100%; padding:11px; border-radius:12px; border:1.5px dashed var(--border); background:transparent; color:var(--text-dim); font-weight:700; font-size:13px; }
.add-account-btn:hover { border-color:var(--accent); color:var(--text); }

/* ---- premium ---- */
.premium-card { background:linear-gradient(135deg, rgba(244,201,93,.14), rgba(124,92,255,.10)); border:1.5px solid var(--gold); border-radius:16px; padding:16px; }
.premium-card h4 { margin:0 0 4px; font-size:15px; display:flex; align-items:center; gap:6px; }
.premium-card p { margin:0 0 12px; font-size:12.5px; color:var(--text-dim); }
.premium-perks { margin:0 0 14px; padding-left:18px; font-size:12.5px; color:var(--text); }
.premium-perks li { margin-bottom:4px; }
.toggle-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.toggle-switch { position:relative; width:46px; height:26px; flex-shrink:0; }
.toggle-switch input { opacity:0; width:0; height:0; }
.toggle-slider { position:absolute; inset:0; background:var(--panel-2); border:1px solid var(--border); border-radius:14px; cursor:pointer; transition:.2s; }
.toggle-slider::before { content:""; position:absolute; width:18px; height:18px; left:3px; top:2.5px; background:var(--text-dim); border-radius:50%; transition:.2s; }
.toggle-switch input:checked + .toggle-slider { background:linear-gradient(135deg,var(--gold),#c9962e); border-color:var(--gold); }
.toggle-switch input:checked + .toggle-slider::before { transform:translateX(20px); background:#2a1c00; }
.demo-note { font-size:10.5px; color:var(--text-dim); margin-top:10px; font-style:italic; }

/* ---- wallpaper picker ---- */
.wallpaper-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:10px; }
.wallpaper-swatch { aspect-ratio:9/16; border-radius:12px; border:2px solid var(--border); cursor:pointer; position:relative; overflow:hidden; }
.wallpaper-swatch.selected { border-color:var(--accent); }
.wallpaper-swatch span { position:absolute; bottom:4px; left:0; right:0; text-align:center; font-size:9.5px; color:#fff; text-shadow:0 1px 2px rgba(0,0,0,.6); font-weight:700; }
.wp-default { background:var(--bg); }
.wp-dunes { background:linear-gradient(160deg,#4a2f1e,#a8703b 45%,#e8b874); }
.wp-botanical { background:radial-gradient(circle at 30% 20%, #1f4d34, #0c1f16 70%), radial-gradient(circle at 75% 65%, #2b6b46, transparent 60%); }
.wp-circuit { background:repeating-linear-gradient(0deg,#0c1824,#0c1824 18px,#123049 19px,#123049 20px), repeating-linear-gradient(90deg,transparent,transparent 18px,rgba(62,230,176,.15) 19px,rgba(62,230,176,.15) 20px); }
.wp-aurora { background:linear-gradient(135deg,#0a1f2b,#1a3a5c 30%,#2f6a55 60%,#3ee6b0 100%); }
.wp-noir { background:#0a0a0a; }
.thread-messages.has-wallpaper { background-size:cover; background-position:center; }

/* ============================== MICRO-ANIMATIONS ============================== */
#gateway-toast {
  position:fixed; left:50%; bottom:90px; transform:translateX(-50%) translateY(20px);
  background:var(--panel); border:1px solid var(--border); color:var(--text);
  padding:11px 18px; border-radius:12px; font-size:13px; font-weight:600;
  box-shadow:0 10px 30px rgba(0,0,0,.4); z-index:90; opacity:0; pointer-events:none;
  transition:opacity .2s ease, transform .2s ease; max-width:85vw; text-align:center;
}
#gateway-toast.visible { opacity:1; transform:translateX(-50%) translateY(0); }
#gateway-toast.error { border-color:var(--danger); color:#ffb3b3; }

@keyframes heart-burst {
  0% { transform:scale(0.4); opacity:0; }
  35% { transform:scale(1.35); opacity:1; }
  60% { transform:scale(0.95); }
  100% { transform:scale(1); opacity:0; }
}
.heart-burst-fx {
  position:absolute; pointer-events:none; z-index:6; color:#ff5c8a;
  animation:heart-burst .65s cubic-bezier(.2,.9,.3,1.3) forwards;
}
.heart-burst-fx svg { width:64px; height:64px; fill:#ff5c8a; stroke:#ff5c8a; filter:drop-shadow(0 2px 8px rgba(255,92,138,.5)); }

@keyframes press-pop { 0% { transform:scale(1); } 40% { transform:scale(.86); } 100% { transform:scale(1); } }
.pop-on-click:active { animation:press-pop .22s ease; }
.icon-btn:active, .btn-primary:active, .btn-ghost:active, .subtab:active, .space-menu-item:active,
.pulse-action-btn:active, .post-action:active, .like-btn:active, .comment-btn:active,
.share-btn:active, .follow-btn:active, .subscribe-bell-btn:active, .theme-swatch:active,
.wallpaper-swatch:active, .mode-card:active, .story-avatar-wrap:active, .status-row:active,
.grid-cell:active { animation:press-pop .22s ease; }

@keyframes subscribe-pulse {
  0% { box-shadow:0 0 0 0 rgba(62,230,176,.55); }
  70% { box-shadow:0 0 0 10px rgba(62,230,176,0); }
  100% { box-shadow:0 0 0 0 rgba(62,230,176,0); }
}
.subscribe-btn.just-subscribed { animation:subscribe-pulse .7s ease-out; }

@keyframes fade-slide-in { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
.fade-in-item { animation:fade-slide-in .28s ease both; }

.subscribe-bell-btn { background:var(--panel-2); border:1px solid var(--border); color:var(--text-dim); width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center; }
.subscribe-bell-btn.subscribed { color:var(--accent); border-color:var(--accent); }

/* ============================== PERMISSION PROMPT ============================== */
.permission-prompt-screen { position:fixed; inset:0; background:rgba(5,7,10,.88); backdrop-filter:blur(6px); z-index:80; display:flex; align-items:center; justify-content:center; }
.permission-prompt-card { width:360px; max-width:88vw; background:var(--panel); border:1px solid var(--border); border-radius:20px; padding:26px 24px; text-align:center; }
.permission-prompt-card .picon-big { width:56px; height:56px; border-radius:16px; background:var(--panel-2); display:flex; align-items:center; justify-content:center; margin:0 auto 14px; color:var(--accent); }
.permission-prompt-card h3 { margin:0 0 8px; font-size:17px; }
.permission-prompt-card p { margin:0 0 18px; font-size:13px; color:var(--text-dim); line-height:1.5; }
.permission-prompt-actions { display:flex; gap:10px; }
.permission-prompt-actions button { flex:1; }
.permission-status.granted { color:var(--accent); background:rgba(62,230,176,.12); }
.permission-status.denied { color:var(--danger); background:rgba(255,92,92,.12); }

/* ============================== CAMERA CAPTURE ============================== */
.camera-modal { position:fixed; inset:0; background:#000; z-index:75; display:flex; flex-direction:column; }
.camera-modal video { flex:1; width:100%; object-fit:cover; background:#000; }
.camera-controls { display:flex; align-items:center; justify-content:center; gap:24px; padding:20px; background:rgba(0,0,0,.5); }
.camera-shutter { width:64px; height:64px; border-radius:50%; background:#fff; border:4px solid rgba(255,255,255,.4); }
.camera-close-btn { position:absolute; top:16px; left:16px; z-index:2; background:rgba(0,0,0,.5); border:none; color:#fff; width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center; }
.voice-record-btn.recording { background:var(--danger); color:#fff; animation:subscribe-pulse 1s infinite; }

/* ============================== SOUNDS LIBRARY ============================== */
.sounds-page { flex:1; overflow-y:auto; }
.sound-row { display:flex; align-items:center; gap:12px; padding:12px 16px; border-bottom:1px solid rgba(255,255,255,.03); }
.sound-row .sicon { width:40px; height:40px; border-radius:10px; background:linear-gradient(135deg,var(--tiktok-cyan),var(--tiktok-pink)); display:flex; align-items:center; justify-content:center; color:#06110d; flex-shrink:0; }
.sound-row .grow { flex:1; min-width:0; }
.sound-row .grow b { display:block; font-size:13.5px; }
.sound-row .grow span { font-size:11.5px; color:var(--text-dim); }
.sound-row-actions { display:flex; gap:6px; }
.sound-upload-form { display:flex; flex-direction:column; gap:8px; padding:14px 16px; border-bottom:1px solid var(--border); }
.sound-upload-form input { background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:9px 12px; border-radius:10px; font-size:13px; outline:none; }

/* ============================== DEVELOPER OPTIONS ============================== */
.dev-key-box { background:var(--panel-2); border:1px solid var(--border); border-radius:10px; padding:10px 12px; font-family:monospace; font-size:12px; word-break:break-all; margin:10px 0; }
.dev-snippet { background:#05070a; border:1px solid var(--border); border-radius:10px; padding:12px; font-family:monospace; font-size:11.5px; color:#9fe8c8; overflow-x:auto; white-space:pre; margin-top:10px; }

/* ============================== RATINGS & PROFILE MENU ============================== */
.star-rating { display:inline-flex; gap:2px; }
.star-rating .star { width:20px; height:20px; cursor:pointer; fill:none; stroke:var(--text-dim); stroke-width:1.6; transition:transform .1s; }
.star-rating .star:hover { transform:scale(1.15); }
.star-rating.readonly .star { cursor:default; }
.star-rating.readonly .star:hover { transform:none; }
.star-rating .star.filled { fill:var(--gold); stroke:var(--gold); }
.rating-summary { display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--text-dim); margin-top:4px; }
.rating-summary b { color:var(--text); }
.sound-row .rating-summary { margin-top:2px; }

.profile-menu-btn { background:transparent; border:none; color:var(--text-dim); padding:4px; }
.profile-menu { position:absolute; background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:6px; box-shadow:0 10px 30px rgba(0,0,0,.4); z-index:65; min-width:160px; }
.profile-menu button { display:block; width:100%; text-align:left; background:transparent; border:none; color:var(--text); padding:9px 10px; border-radius:8px; font-size:13px; }
.profile-menu button:hover { background:var(--panel-2); }
.profile-menu button.danger { color:var(--danger); }


/* ============================== SHARED MODALS ============================== */
.modal { position:fixed; inset:0; background:rgba(0,0,0,.6); display:flex; align-items:center; justify-content:center; z-index:60; }
.modal-card { width:380px; max-width:90vw; background:var(--panel); border:1px solid var(--border); border-radius:16px; padding:18px; max-height:80vh; display:flex; flex-direction:column; }
.modal-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
.modal-header h3 { margin:0; font-size:16px; }
#user-search-input { width:100%; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:10px 12px; border-radius:10px; font-size:13px; outline:none; margin-bottom:8px; }
.user-search-results { overflow-y:auto; }
.user-result { display:flex; align-items:center; gap:10px; padding:8px; border-radius:10px; cursor:pointer; }
.user-result:hover { background:var(--panel-2); }
.user-result img { width:36px; height:36px; border-radius:50%; object-fit:cover; }
.invite-fallback { padding:16px 8px; text-align:center; }
.invite-fallback p { font-size:12.5px; color:var(--text-dim); margin:0 0 10px; }
.contacts-import-btn { display:flex; align-items:center; justify-content:center; gap:8px; width:100%; background:var(--panel-2); border:1px solid var(--border); color:var(--text); padding:10px 12px; border-radius:10px; font-size:13px; cursor:pointer; margin-bottom:10px; }
.contacts-import-btn svg { width:16px; height:16px; }

/* ---- share sheet ---- */
.share-sheet-options { display:flex; flex-direction:column; gap:8px; }
.share-option-row { display:flex; align-items:center; gap:12px; background:var(--panel-2); border:1px solid var(--border); border-radius:12px; padding:11px 14px; cursor:pointer; font-size:13.5px; }
.share-option-row:hover { border-color:var(--accent); }
.share-option-row .sicon { width:32px; height:32px; border-radius:9px; display:flex; align-items:center; justify-content:center; flex-shrink:0; color:#fff; }
.share-option-row .sicon svg { width:16px; height:16px; }
.share-icon-whatsapp { background:#25D366; }
.share-icon-x { background:#000; }
.share-icon-gmail { background:#EA4335; }
.share-icon-instagram { background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888); }
.share-icon-native { background:var(--accent); color:#04120b; }
.share-icon-copy { background:var(--panel); color:var(--text); border:1px solid var(--border); }

/* ---- status composer chooser ---- */
.status-composer-sheet { display:flex; flex-direction:column; gap:8px; }
.status-option-row { display:flex; align-items:center; gap:12px; background:var(--panel-2); border:1px solid var(--border); border-radius:12px; padding:12px 14px; cursor:pointer; font-size:13.5px; }
.status-option-row:hover { border-color:var(--accent); }
.status-option-row svg { width:18px; height:18px; color:var(--accent); }
.status-text-editor { display:flex; flex-direction:column; gap:10px; }
.status-text-editor textarea { min-height:110px; background:var(--panel-2); border:1px solid var(--border); color:var(--text); border-radius:12px; padding:12px; font-size:15px; resize:vertical; outline:none; font-family:inherit; }
.status-bg-swatches { display:flex; gap:8px; flex-wrap:wrap; }
.status-bg-swatch { width:28px; height:28px; border-radius:50%; cursor:pointer; border:2px solid transparent; }
.status-bg-swatch.selected { border-color:var(--text); }
.status-voice-row { display:flex; align-items:center; gap:12px; }
.status-voice-record-btn { width:56px; height:56px; border-radius:50%; background:var(--accent); color:#04120b; display:flex; align-items:center; justify-content:center; border:none; cursor:pointer; }
.status-voice-record-btn.recording { background:#e5484d; color:#fff; animation:pulseRec 1s infinite; }
@keyframes pulseRec { 0%,100%{ box-shadow:0 0 0 0 rgba(229,72,77,.5);} 50%{ box-shadow:0 0 0 10px rgba(229,72,77,0);} }

/* ---- sound picker (Alpha/Beta post composer) ---- */
.sound-picker-list { overflow-y:auto; max-height:320px; }
.sound-picker-row { display:flex; align-items:center; gap:10px; padding:9px 8px; border-radius:10px; cursor:pointer; }
.sound-picker-row:hover, .sound-picker-row.selected { background:var(--panel-2); }
.sound-picker-row .grow { flex:1; min-width:0; }
.sound-picker-row .grow b { display:block; font-size:13px; }
.sound-picker-row .grow span { font-size:11px; color:var(--text-dim); }

/* ---- inline audio attachment (Epsilon posts) ---- */
.post-audio-attachment { margin-top:8px; }
.post-audio-attachment audio { width:100%; height:34px; }
.attach-audio-btn { background:none; border:none; color:var(--accent); cursor:pointer; display:flex; align-items:center; gap:4px; font-size:12px; padding:4px 0; }
.attach-audio-btn svg { width:15px; height:15px; }

/* ---- video trimmer ---- */
.video-trim-modal .modal-card { width:460px; }
.video-trim-preview { width:100%; max-height:320px; background:#000; border-radius:10px; margin-bottom:12px; }
.video-trim-range { position:relative; height:34px; background:var(--panel-2); border-radius:8px; margin-bottom:14px; }
.video-trim-range input[type=range] { position:absolute; top:0; left:0; width:100%; height:34px; -webkit-appearance:none; background:transparent; pointer-events:none; }
.video-trim-range input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; pointer-events:auto; width:14px; height:34px; border-radius:4px; background:var(--accent); cursor:pointer; }
.video-trim-labels { display:flex; justify-content:space-between; font-size:11px; color:var(--text-dim); margin-bottom:14px; }

/* ============================== SCROLLBARS ============================== */
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:4px; }
::-webkit-scrollbar-track { background:transparent; }

/* ============================== RESPONSIVE ============================== */
@media (max-width: 860px) {
  .chat-list-pane { width:100%; }
  .gateway-chats-layout.thread-open .chat-list-pane { display:none; }
  .chat-thread-pane { display:none; }
  .gateway-chats-layout.thread-open .chat-thread-pane { display:flex; }
  .thread-back { display:flex; }
  .msg-bubble { max-width:80%; }
}
"""
