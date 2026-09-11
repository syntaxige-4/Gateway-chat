"""
page.py — assembles the entire single-page app as one HTML document, generated
by Python at request time. There is no index.html on disk anywhere in this
project; render_page() below IS the page.
"""
from .styles import CSS
from .script import JS
from .particles import PARTICLES_JS
from .icons import gateway_mark, beta_mark, epsilon_mark, alpha_mark, SPRITE_SYMBOLS

THEME_META = [
    {"id": "midnight", "label": "Midnight", "preview": "linear-gradient(135deg,#0b0f14,#3ee6b0)", "premium": False},
    {"id": "light", "label": "Light", "preview": "linear-gradient(135deg,#f3f5f8,#3ee6b0)", "premium": False},
    {"id": "amoled", "label": "AMOLED", "preview": "linear-gradient(135deg,#000000,#3ee6b0)", "premium": True},
    {"id": "sunset", "label": "Sunset", "preview": "linear-gradient(135deg,#180b13,#ff8a3d)", "premium": True},
    {"id": "ocean", "label": "Ocean", "preview": "linear-gradient(135deg,#061622,#3ec9e6)", "premium": True},
]
WALLPAPER_META = [
    {"id": "default", "label": "Default"}, {"id": "dunes", "label": "Dunes"},
    {"id": "botanical", "label": "Botanical"}, {"id": "circuit", "label": "Circuit"},
    {"id": "aurora", "label": "Aurora"}, {"id": "noir", "label": "Noir"},
]

MODE_META = {
    "gateway": {"mark": gateway_mark(120), "label": "Gateway", "tagline": "Chats, calls & status"},
    "beta": {"mark": beta_mark(120), "label": "Beta", "tagline": "Photos, stories & reels"},
    "epsilon": {"mark": epsilon_mark(120), "label": "Epsilon", "tagline": "Posts & the public timeline"},
    "alpha": {"mark": alpha_mark(120), "label": "Alpha", "tagline": "Short vertical video"},
}
MODE_ORDER = ["gateway", "beta", "epsilon", "alpha"]


def _space_menu_items():
    items = []
    for mid in MODE_ORDER:
        meta = MODE_META[mid]
        mark = meta["mark"].replace('width="120" height="120"', 'width="34" height="34"')
        badge = f'<span class="orbit-badge hidden" id="badge-{mid}"></span>' if mid == "gateway" else ""
        items.append(f'''
        <button class="space-menu-item" data-mode="{mid}">
          <span class="mark-wrap">{mark}</span>
          <span class="grow"><b>{meta['label']}</b><span>{meta['tagline']}</span></span>
          {badge}
        </button>''')
    return "".join(items)


def _mode_picker_cards():
    cards = []
    for mid in MODE_ORDER:
        meta = MODE_META[mid]
        mark = meta["mark"].replace('width="120" height="120"', 'width="42" height="42"')
        cards.append(f'''
        <label class="mode-card" data-mode-card="{mid}">
          <span class="mark-wrap">{mark}</span>
          <span class="grow"><b>{meta['label']}</b><span>{meta['tagline']}</span></span>
          <input type="radio" name="default_mode" value="{mid}">
        </label>''')
    return "".join(cards)


def _theme_swatches():
    cards = []
    for t in THEME_META:
        lock = '<span class="theme-lock">&#128274;</span>' if t["premium"] else ""
        cards.append(f'''
        <div class="theme-swatch" data-theme-id="{t['id']}" data-premium="{1 if t['premium'] else 0}">
          <div class="swatch-preview" style="background:{t['preview']}">{lock}</div>
          <span>{t['label']}</span>
        </div>''')
    return "".join(cards)


def _wallpaper_swatches():
    cells = []
    for w in WALLPAPER_META:
        cells.append(f'<div class="wallpaper-swatch wp-{w["id"]}" data-wallpaper-id="{w["id"]}"><span>{w["label"]}</span></div>')
    return "".join(cells)


def render_page():
    gateway_mark_sm = MODE_META["gateway"]["mark"].replace('width="120" height="120"', 'width="30" height="30"')
    gateway_mark_auth = MODE_META["gateway"]["mark"].replace('width="120" height="120"', 'width="56" height="56"')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0" />
<title>Gateway</title>
<style>{CSS}</style>
</head>
<body>
<canvas id="particle-canvas"></canvas>
<svg style="display:none">{SPRITE_SYMBOLS}</svg>

<!-- ============================== AUTH SCREEN ============================== -->
<div id="auth-screen" class="auth-screen">
  <div class="auth-card">
    <div class="auth-brand">
      <div class="mark-wrap">{gateway_mark_auth}</div>
      <h1>Gateway</h1>
      <p>Gateway &middot; Beta &middot; Epsilon &middot; Alpha — one account, four worlds.</p>
    </div>
    <div class="auth-tabs">
      <button class="auth-tab active" data-tab="login">Log in</button>
      <button class="auth-tab" data-tab="register">Sign up</button>
    </div>
    <p class="auth-referral-banner hidden" id="auth-referral-banner"></p>
    <form id="login-form" class="auth-form">
      <input type="text" id="login-username" placeholder="Username" autocomplete="username" required />
      <input type="password" id="login-password" placeholder="Password" autocomplete="current-password" required />
      <button type="submit" class="btn-primary">Log in</button>
      <p class="auth-error" id="login-error"></p>
    </form>
    <form id="register-form" class="auth-form hidden">
      <input type="text" id="reg-username" placeholder="Choose a username" required />
      <input type="text" id="reg-display" placeholder="Display name" required />
      <input type="password" id="reg-password" placeholder="Password (6+ characters)" required />
      <button type="submit" class="btn-primary">Create account</button>
      <p class="auth-error" id="register-error"></p>
    </form>
  </div>
</div>

<!-- ============================== APP SHELL ============================== -->
<div id="app" class="app hidden">

  <header class="topbar">
    <div class="topbar-brand">
      <button class="topbar-btn" id="space-menu-btn" title="Switch space">
        <svg class="ic"><use href="#i-menu"/></svg>
        <span class="orbit-badge hidden" id="badge-hamburger"></span>
      </button>
      <span class="mark-wrap" id="topbar-mark">{gateway_mark_sm}</span>
      <span class="mode-name"><span id="topbar-mode-name">Gateway</span><span class="premium-chip hidden" id="premium-chip">&#9733; PREMIUM</span></span>
    </div>
    <div class="topbar-actions">
      <button class="topbar-btn hidden" id="topbar-create-btn" title="Create">
        <svg class="ic"><use href="#i-plus"/></svg>
      </button>
      <img class="topbar-avatar" id="self-avatar" src="" alt="me" />
    </div>
  </header>

  <!-- ---------------- SPACE-SWITCHER DROPDOWN (the hamburger menu) ---------------- -->
  <div id="space-menu-backdrop" class="space-menu-backdrop hidden">
    <div class="space-menu" id="space-menu">
      <div class="space-menu-header">Switch space</div>
      <div id="space-menu-items">{_space_menu_items()}</div>
      <div class="space-menu-divider"></div>
      <button class="space-menu-item" id="space-menu-settings-btn">
        <span class="mark-wrap settings-mark"><svg class="ic"><use href="#i-gear"/></svg></span>
        <span class="grow"><b>General Settings</b><span>Account, appearance, permissions &amp; more</span></span>
      </button>
    </div>
  </div>

  <div class="mode-area">

    <!-- ---------------- GATEWAY (WhatsApp-style) ---------------- -->
    <section class="mode-view active" id="mode-gateway">
      <div class="subtabs" id="gateway-subtabs">
        <button class="subtab active" data-sub="chats">Chats</button>
        <button class="subtab" data-sub="status">Status</button>
        <button class="icon-btn platform-settings-open" data-platform="gateway" style="margin-left:auto;flex-shrink:0" title="Gateway settings"><svg class="ic"><use href="#i-gear"/></svg></button>
      </div>

      <div class="subpage active" id="gateway-page-chats">
        <div class="gateway-chats-layout" id="gateway-chats-layout">
          <aside class="chat-list-pane">
            <div class="search-box"><input type="text" id="chat-search" placeholder="Search people or chats" /></div>
            <div class="chat-list" id="chat-list"></div>
          </aside>
          <main class="chat-thread-pane" id="chat-thread-pane">
            <div class="empty-thread" id="empty-thread">
              <div class="empty-badge">T</div>
              <p>Pick a conversation, or start a new one.</p>
              <button class="btn-primary small" id="new-chat-btn">+ New chat</button>
            </div>
            <div class="thread hidden" id="thread">
              <header class="thread-header">
                <button class="icon-btn thread-back" id="thread-back-btn"><svg class="ic"><use href="#i-back"/></svg></button>
                <img id="thread-avatar" class="thread-avatar" src="" alt="" />
                <div class="thread-title">
                  <div id="thread-name" class="thread-name"></div>
                  <div id="thread-status" class="thread-status"></div>
                </div>
                <select id="gateway-provider" class="provider-select hidden" title="AI provider"></select>
                <button class="icon-btn" id="thread-wallpaper-btn" title="Change wallpaper"><svg class="ic"><use href="#i-image"/></svg></button>
              </header>
              <div class="thread-messages" id="thread-messages"></div>
              <form class="thread-composer" id="composer-form">
                <button type="button" class="icon-btn" id="attach-btn" title="Attach media"><svg class="ic"><use href="#i-attach"/></svg></button>
                <input type="file" id="attach-input" accept="image/*,video/*" hidden />
                <input type="text" id="composer-input" placeholder="Message" autocomplete="off" />
                <button type="button" class="icon-btn voice-record-btn" id="voice-record-btn" title="Hold to record a voice note"><svg class="ic"><use href="#i-mic"/></svg></button>
                <button type="submit" class="icon-btn send-btn" title="Send"><svg class="ic"><use href="#i-send"/></svg></button>
              </form>
            </div>
          </main>
        </div>
      </div>

      <div class="subpage" id="gateway-page-status">
        <div class="status-list" id="status-list"></div>
        <input type="file" id="story-input" accept="image/*,video/*" hidden />
      </div>
    </section>

    <!-- ---------------- BETA (Instagram-style) ---------------- -->
    <section class="mode-view" id="mode-beta">
      <div class="subtabs" id="beta-subtabs">
        <button class="subtab active" data-sub="feed">Feed</button>
        <button class="subtab" data-sub="explore">Explore</button>
        <button class="subtab" data-sub="profile">Profile</button>
        <button class="icon-btn platform-settings-open" data-platform="beta" style="margin-left:auto;flex-shrink:0" title="Beta settings"><svg class="ic"><use href="#i-gear"/></svg></button>
      </div>
      <div class="subpage active" id="beta-page-feed">
        <div class="ig-feed-page">
          <div class="ig-stories-bar" id="ig-stories-bar"></div>
          <div id="ig-feed-list"></div>
        </div>
      </div>
      <div class="subpage" id="beta-page-explore">
        <div class="ig-explore-grid" id="ig-explore-grid"></div>
      </div>
      <div class="subpage" id="beta-page-profile">
        <div class="profile-page" id="beta-profile-page"></div>
      </div>
      <input type="file" id="beta-post-input" accept="image/*,video/*" hidden />
    </section>

    <!-- ---------------- EPSILON (X-style) ---------------- -->
    <section class="mode-view" id="mode-epsilon">
      <div class="subtabs" id="epsilon-subtabs">
        <button class="subtab active" data-sub="home">Home</button>
        <button class="subtab" data-sub="search">Explore</button>
        <button class="subtab" data-sub="notifications">Notifications</button>
        <button class="subtab" data-sub="profile">Profile</button>
        <button class="icon-btn platform-settings-open" data-platform="epsilon" style="margin-left:auto;flex-shrink:0" title="Epsilon settings"><svg class="ic"><use href="#i-gear"/></svg></button>
      </div>
      <div class="subpage active" id="epsilon-page-home">
        <div class="x-home-page">
          <form class="composer-post" id="post-form">
            <img id="post-avatar" class="post-avatar" src="" alt="" />
            <div class="post-form-main">
              <textarea id="post-input" placeholder="What's happening on the network?" maxlength="280"></textarea>
              <div id="post-audio-preview" class="post-audio-attachment hidden"></div>
              <div class="post-form-footer">
                <button type="button" class="attach-audio-btn" id="post-attach-audio-btn"><svg class="ic"><use href="#i-music"/></svg> Add sound</button>
                <span id="post-counter" class="post-counter">280</span>
                <button type="submit" class="btn-primary small">Post</button>
              </div>
            </div>
          </form>
          <input type="file" id="post-audio-input" accept="audio/*" hidden />
          <div class="posts-list" id="posts-list"></div>
        </div>
      </div>
      <div class="subpage" id="epsilon-page-search">
        <div class="x-search-page">
          <div class="x-search-box"><input type="text" id="x-search-input" placeholder="Search Epsilon" /></div>
          <div class="x-search-results" id="x-search-results"></div>
        </div>
      </div>
      <div class="subpage" id="epsilon-page-notifications">
        <div class="x-notif-page" id="x-notif-list"></div>
      </div>
      <div class="subpage" id="epsilon-page-profile">
        <div class="profile-page" id="epsilon-profile-page"></div>
      </div>
    </section>

    <!-- ---------------- ALPHA (TikTok-style) ---------------- -->
    <section class="mode-view" id="mode-alpha">
      <div class="subtabs" id="alpha-subtabs">
        <button class="subtab active" data-sub="foryou">For You</button>
        <button class="subtab" data-sub="following">Following</button>
        <button class="icon-btn platform-settings-open" data-platform="alpha" style="margin-left:auto;flex-shrink:0" title="Alpha settings"><svg class="ic"><use href="#i-gear"/></svg></button>
      </div>
      <div class="subpage active" id="alpha-page">
        <div class="alpha-page">
          <div class="pulse-feed" id="pulse-feed"></div>
          <button class="fab" id="new-pulse-btn" title="Post a Pulse" style="top:10px"><svg class="ic"><use href="#i-plus"/></svg></button>
          <button class="fab" id="new-pulse-camera-btn" title="Record with camera" style="top:56px"><svg class="ic"><use href="#i-cam"/></svg></button>
        </div>
      </div>
      <input type="file" id="pulse-input" accept="image/*,video/*" hidden />
    </section>

  </div>


  <!-- ---------------- STORY VIEWER (shared by Gateway + Beta) ---------------- -->
  <div id="story-viewer" class="story-viewer hidden">
    <div class="story-progress" id="story-progress"></div>
    <button class="story-close" id="story-close">&times;</button>
    <div class="story-content" id="story-content"></div>
    <div class="story-caption" id="story-caption"></div>
  </div>

  <!-- ---------------- COMMENTS DRAWER (Alpha) ---------------- -->
  <div id="comments-drawer" class="drawer-backdrop hidden">
    <div class="drawer">
      <div class="drawer-header">Comments<button class="drawer-close" id="drawer-close">&times;</button></div>
      <div class="drawer-body" id="drawer-body"></div>
      <form class="drawer-input-row" id="drawer-form">
        <input type="text" id="drawer-input" placeholder="Add a comment…" autocomplete="off" />
        <button type="submit" class="icon-btn send-btn"><svg class="ic"><use href="#i-send"/></svg></button>
      </form>
    </div>
  </div>

  <!-- ---------------- NEW CHAT MODAL ---------------- -->
  <div id="new-chat-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Start a chat</h3><button class="icon-btn" id="close-new-chat">&times;</button></div>
      <button type="button" class="contacts-import-btn" id="import-contacts-btn"><svg class="ic"><use href="#i-contacts"/></svg> Add from Contacts</button>
      <input type="text" id="user-search-input" placeholder="Search by username or name" />
      <div class="user-search-results" id="user-search-results"></div>
    </div>
  </div>

  <!-- ---------------- PROFILE VIEWER MODAL (any user, from anywhere) ---------------- -->
  <div id="profile-viewer-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header" style="position:relative">
        <h3>Profile</h3>
        <div style="display:flex;gap:4px">
          <button class="profile-menu-btn" id="profile-overflow-btn" title="More"><svg class="ic"><use href="#i-more"/></svg></button>
          <button class="icon-btn" id="close-profile-viewer">&times;</button>
        </div>
        <div class="profile-menu hidden" id="profile-overflow-menu" style="top:40px;right:16px"></div>
      </div>
      <div id="profile-viewer-body" style="overflow-y:auto"></div>
    </div>
  </div>

  <!-- ---------------- GENERAL SETTINGS SCREEN ---------------- -->
  <div id="settings-screen" class="settings-screen hidden">
    <div class="settings-header">
      <button class="icon-btn" id="settings-close-btn"><svg class="ic"><use href="#i-back"/></svg></button>
      <h2>General Settings</h2>
      <button class="icon-btn" id="settings-logout-btn" title="Log out"><svg class="ic"><use href="#i-logout"/></svg></button>
    </div>
    <div class="settings-body">
      <div class="settings-section">
        <h3>Your profile</h3>
        <div class="profile-edit-form">
          <label class="avatar-edit-wrap" for="profile-avatar-input">
            <img id="profile-avatar" src="" alt="" />
            <span class="avatar-edit-badge"><svg class="ic"><use href="#i-cam"/></svg></span>
          </label>
          <input type="file" id="profile-avatar-input" accept="image/*" hidden />
          <input type="text" id="profile-display" placeholder="Display name" />
          <input type="text" id="profile-status" placeholder="Status" />
          <textarea id="profile-bio" placeholder="Bio"></textarea>
          <button class="btn-primary" id="save-profile-btn" style="width:100%">Save profile</button>
        </div>
      </div>
      <div class="settings-section">
        <h3>Accounts</h3>
        <div id="account-list"></div>
        <button class="add-account-btn" id="add-account-btn">+ Add account</button>
      </div>
      <div class="settings-section">
        <h3>Premium</h3>
        <div class="premium-card">
          <h4><svg class="ic" style="width:16px;height:16px;color:var(--gold)"><use href="#i-star"/></svg> Gateway Premium</h4>
          <p>Unlock a verified-style badge, extra appearance themes, and priority AI replies.</p>
          <ul class="premium-perks">
            <li>Premium badge next to your name everywhere</li>
            <li>All appearance themes unlocked</li>
            <li>Pin more chats &amp; larger uploads (coming soon)</li>
          </ul>
          <div class="toggle-row">
            <span id="premium-toggle-label">Not active</span>
            <label class="toggle-switch">
              <input type="checkbox" id="premium-toggle" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <p class="demo-note">This is a local demo toggle — no real payment is processed. A production version would connect a real payment provider here.</p>
        </div>
      </div>
      <div class="settings-section">
        <h3>Appearance</h3>
        <div class="theme-grid" id="theme-grid">{_theme_swatches()}</div>
      </div>
      <div class="settings-section">
        <h3>Default app on launch</h3>
        <div class="mode-picker" id="mode-picker">{_mode_picker_cards()}</div>
      </div>
      <div class="settings-section">
        <h3>Permissions</h3>
        <div class="permission-row">
          <span class="picon"><svg class="ic"><use href="#i-cam"/></svg></span>
          <span class="grow"><b>Camera</b><span>Capture photos for Status &amp; Pulse</span></span>
          <span class="permission-status" id="perm-status-camera">Not set</span>
        </div>
        <div class="permission-row">
          <span class="picon"><svg class="ic"><use href="#i-mic"/></svg></span>
          <span class="grow"><b>Microphone</b><span>Record voice notes in Gateway chats</span></span>
          <span class="permission-status" id="perm-status-microphone">Not set</span>
        </div>
        <div class="permission-row">
          <span class="picon"><svg class="ic"><use href="#i-contacts"/></svg></span>
          <span class="grow"><b>Contacts</b><span>No cross-browser API exists for reading a phone's contacts from a website — use Invite Link below instead</span></span>
        </div>
        <button class="btn-ghost" id="request-permissions-btn" style="width:100%;margin-top:6px">Request camera &amp; microphone access</button>
        <button class="btn-ghost" id="copy-invite-link-btn" style="width:100%;margin-top:8px">Copy your invite link</button>
      </div>
      <div class="settings-section">
        <h3>Sounds</h3>
        <p style="font-size:12px;color:var(--text-dim);margin:-4px 0 10px">Original, user-uploaded audio for Alpha Pulses — not a licensed music catalog.</p>
        <button class="btn-ghost" id="open-sounds-btn" style="width:100%">Browse &amp; upload sounds</button>
      </div>
      <div class="settings-section">
        <h3>Developer Options</h3>
        <p style="font-size:12px;color:var(--text-dim);margin:-4px 0 10px">A personal API key to call this server's own API programmatically (header: <code>X-Api-Key</code>).</p>
        <div id="dev-key-status"></div>
        <button class="btn-primary small" id="generate-api-key-btn">Generate new API key</button>
        <button class="btn-ghost" id="revoke-api-key-btn" style="margin-left:8px">Revoke</button>
        <div class="dev-snippet" id="dev-snippet"></div>
      </div>
    </div>
  </div>

  <!-- ---------------- PER-PLATFORM SETTINGS SCREENS ---------------- -->
  <div id="settings-gateway" class="settings-screen hidden">
    <div class="settings-header">
      <button class="icon-btn platform-settings-close"><svg class="ic"><use href="#i-back"/></svg></button>
      <h2>Gateway Settings</h2><span style="width:34px"></span>
    </div>
    <div class="settings-body">
      <div class="settings-section">
        <div class="toggle-row" style="margin-bottom:14px"><span>Read receipts (let others see when you've read their messages)</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="gateway" data-key="read_receipts"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row" style="margin-bottom:14px"><span>Enter key sends message</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="gateway" data-key="enter_to_send"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row" style="margin-bottom:14px"><span>Show typing indicators to others</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="gateway" data-key="typing_indicators"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row"><span>Show my online status and last seen</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="gateway" data-key="online_status_visible"><span class="toggle-slider"></span></label></div>
      </div>
    </div>
  </div>
  <div id="settings-beta" class="settings-screen hidden">
    <div class="settings-header">
      <button class="icon-btn platform-settings-close"><svg class="ic"><use href="#i-back"/></svg></button>
      <h2>Beta Settings</h2><span style="width:34px"></span>
    </div>
    <div class="settings-body">
      <div class="settings-section">
        <div class="toggle-row" style="margin-bottom:14px"><span>Show like counts on posts</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="beta" data-key="show_like_counts"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row" style="margin-bottom:14px"><span>Autoplay videos in feed</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="beta" data-key="autoplay_videos"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row"><span>Show captions on posts</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="beta" data-key="show_captions"><span class="toggle-slider"></span></label></div>
      </div>
    </div>
  </div>
  <div id="settings-epsilon" class="settings-screen hidden">
    <div class="settings-header">
      <button class="icon-btn platform-settings-close"><svg class="ic"><use href="#i-back"/></svg></button>
      <h2>Epsilon Settings</h2><span style="width:34px"></span>
    </div>
    <div class="settings-body">
      <div class="settings-section">
        <div class="toggle-row" style="margin-bottom:14px"><span>Compact timeline</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="epsilon" data-key="compact_timeline"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row" style="margin-bottom:14px"><span>Autoplay media in timeline</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="epsilon" data-key="autoplay_media"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row"><span>Show reply counts</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="epsilon" data-key="show_reply_counts"><span class="toggle-slider"></span></label></div>
      </div>
    </div>
  </div>
  <div id="settings-alpha" class="settings-screen hidden">
    <div class="settings-header">
      <button class="icon-btn platform-settings-close"><svg class="ic"><use href="#i-back"/></svg></button>
      <h2>Alpha Settings</h2><span style="width:34px"></span>
    </div>
    <div class="settings-body">
      <div class="settings-section">
        <div class="toggle-row" style="margin-bottom:14px"><span>Sound on by default</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="alpha" data-key="autoplay_sound"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row" style="margin-bottom:14px"><span>Data saver (loads fewer Pulses at once)</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="alpha" data-key="data_saver"><span class="toggle-slider"></span></label></div>
        <div class="toggle-row"><span>Loop videos</span>
          <label class="toggle-switch"><input type="checkbox" class="platform-setting" data-platform="alpha" data-key="loop_videos"><span class="toggle-slider"></span></label></div>
      </div>
    </div>
  </div>

  <!-- ---------------- SOUNDS LIBRARY ---------------- -->
  <div id="sounds-screen" class="settings-screen hidden">
    <div class="settings-header">
      <button class="icon-btn" id="sounds-close-btn"><svg class="ic"><use href="#i-back"/></svg></button>
      <h2>Sounds</h2><span style="width:34px"></span>
    </div>
    <form class="sound-upload-form" id="sound-upload-form">
      <input type="text" id="sound-title-input" placeholder="Sound title" required />
      <input type="text" id="sound-artist-input" placeholder="Artist / creator (optional)" />
      <button type="button" class="btn-ghost" id="sound-file-btn">Choose audio file</button>
      <input type="file" id="sound-file-input" accept="audio/*" hidden />
      <button type="submit" class="btn-primary small">Upload sound</button>
    </form>
    <div class="sounds-page" id="sounds-list"></div>
  </div>

  <!-- ---------------- PERMISSION PROMPT (shown once after login) ---------------- -->
  <div id="permission-prompt-screen" class="permission-prompt-screen hidden">
    <div class="permission-prompt-card">
      <div class="picon-big"><svg class="ic" style="width:28px;height:28px"><use href="#i-cam"/></svg></div>
      <h3>Enable camera &amp; microphone?</h3>
      <p>Gateway uses these for capturing Status/Pulse photos &amp; videos and recording voice notes in chat. You can change this anytime in General Settings.</p>
      <div class="permission-prompt-actions">
        <button class="btn-ghost" id="permission-skip-btn">Not now</button>
        <button class="btn-primary" id="permission-allow-btn">Allow access</button>
      </div>
    </div>
  </div>

  <!-- ---------------- CAMERA CAPTURE ---------------- -->
  <div id="camera-modal" class="camera-modal hidden">
    <button class="camera-close-btn" id="camera-close-btn">&times;</button>
    <video id="camera-video" autoplay playsinline muted></video>
    <div class="camera-controls"><button class="camera-shutter pop-on-click" id="camera-shutter-btn"></button></div>
  </div>

  <!-- ---------------- SHARE SHEET (used by post/pulse share buttons + invite links) ---------------- -->
  <div id="share-sheet-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3 id="share-sheet-title">Share</h3><button class="icon-btn" id="close-share-sheet">&times;</button></div>
      <div class="share-sheet-options" id="share-sheet-options"></div>
    </div>
  </div>

  <!-- ---------------- STATUS COMPOSER: choose photo/video/text/voice ---------------- -->
  <div id="status-composer-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Add status update</h3><button class="icon-btn" id="close-status-composer">&times;</button></div>
      <div class="status-composer-sheet">
        <div class="status-option-row" id="status-opt-media"><svg class="ic"><use href="#i-image"/></svg> Photo or video</div>
        <div class="status-option-row" id="status-opt-text"><svg class="ic"><use href="#i-edit"/></svg> Text status</div>
        <div class="status-option-row" id="status-opt-voice"><svg class="ic"><use href="#i-mic"/></svg> Voice status</div>
      </div>
    </div>
  </div>

  <!-- ---------------- STATUS: text editor ---------------- -->
  <div id="status-text-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Text status</h3><button class="icon-btn" id="close-status-text">&times;</button></div>
      <div class="status-text-editor">
        <textarea id="status-text-input" maxlength="200" placeholder="What's on your mind?"></textarea>
        <div class="status-bg-swatches" id="status-bg-swatches"></div>
        <button class="btn-primary" id="status-text-post-btn" style="width:100%">Post status</button>
      </div>
    </div>
  </div>

  <!-- ---------------- STATUS: voice recorder ---------------- -->
  <div id="status-voice-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Voice status</h3><button class="icon-btn" id="close-status-voice">&times;</button></div>
      <div class="status-voice-row">
        <button class="status-voice-record-btn" id="status-voice-record-btn"><svg class="ic"><use href="#i-mic"/></svg></button>
        <span id="status-voice-hint">Tap to start recording, tap again to stop and post.</span>
      </div>
    </div>
  </div>

  <!-- ---------------- SOUND PICKER (Alpha/Beta post composer) ---------------- -->
  <div id="sound-picker-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Choose a sound</h3><button class="icon-btn" id="close-sound-picker">&times;</button></div>
      <div class="sound-picker-list" id="sound-picker-list">
        <div class="sound-picker-row selected" data-sound="original sound"><span class="grow"><b>Original sound</b><span>No background sound</span></span></div>
      </div>
    </div>
  </div>

  <!-- ---------------- VIDEO TRIMMER ---------------- -->
  <div id="video-trim-modal" class="modal video-trim-modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Trim video</h3><button class="icon-btn" id="close-video-trim">&times;</button></div>
      <video id="video-trim-preview" class="video-trim-preview" muted playsinline controls></video>
      <div class="video-trim-range">
        <input type="range" id="video-trim-start" min="0" max="100" value="0" />
        <input type="range" id="video-trim-end" min="0" max="100" value="100" />
      </div>
      <div class="video-trim-labels"><span id="video-trim-start-label">0.0s</span><span id="video-trim-end-label">0.0s</span></div>
      <button class="btn-primary" id="video-trim-apply-btn" style="width:100%">Use trimmed clip</button>
      <button class="btn-ghost" id="video-trim-skip-btn" style="width:100%;margin-top:8px">Use full video instead</button>
    </div>
  </div>

  <!-- ---------------- WALLPAPER PICKER MODAL (Gateway mode, per chat) ---------------- -->
  <div id="wallpaper-modal" class="modal hidden">
    <div class="modal-card">
      <div class="modal-header"><h3>Chat wallpaper</h3><button class="icon-btn" id="close-wallpaper-modal">&times;</button></div>
      <div class="wallpaper-grid" id="wallpaper-grid">{_wallpaper_swatches()}</div>
      <button class="btn-ghost" id="wallpaper-upload-btn" style="width:100%">Upload your own image</button>
      <input type="file" id="wallpaper-upload-input" accept="image/*" hidden />
    </div>
  </div>

</div>

<script>{PARTICLES_JS}</script>
<script>{JS}</script>
</body>
</html>'''
