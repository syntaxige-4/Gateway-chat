"""
particles.py — the ambient background animation. Each platform gets a
genuinely different rendering style (not just a recolor of the same shapes):

  - gateway  : drifting star-cloud that morphs into atomic rings, an infinity
               curve, and the Gateway mark, driven by scroll + slow autonomous drift.
  - beta     : soft blurred aurora blobs, drifting in slow Lissajous paths,
               blended with additive glow.
  - epsilon  : a sparse constellation — particles connected by thin lines when
               close together, monochrome, minimal.
  - alpha    : deep teal/crimson flowing waveform ribbons (a "mature" duotone,
               replacing a flat pink-purple gradient) — fits Alpha's
               sound-driven identity.
  - settings : a calmer, dimmer variant of the Gateway scene.

Pure Canvas 2D, no WebGL, no CDN dependency — runs offline.
"""

PARTICLES_JS = r"""
window.GatewayParticles = (function () {
  "use strict";

  const SHAPES = ["cloud", "atom", "infinity", "mark"];
  const MARK_POLY = [[50,16],[58,42],[84,50],[58,58],[50,84],[42,58],[16,50],[42,42]]
    .map(([x, y]) => [(x - 50) / 42, (y - 50) / 42]);

  let canvas, ctx, W = 0, H = 0, DPR = 1;
  let starParticles = [], N = 1600;
  let progress = 0, targetProgress = 0, idleDrift = 0;
  let mode = "auth";
  let raf = null;
  let lastT = performance.now();

  let blobs = [];
  let constellation = [];
  let ribbons = [];

  function rand(a, b) { return a + Math.random() * (b - a); }

  function buildStarParticles() {
    N = window.innerWidth < 700 ? 900 : 1800;
    starParticles = [];
    const edges = MARK_POLY.map((p, i) => {
      const q = MARK_POLY[(i + 1) % MARK_POLY.length];
      return { p, q, len: Math.hypot(q[0]-p[0], q[1]-p[1]) };
    });
    const totalLen = edges.reduce((s,e) => s + e.len, 0);
    for (let i = 0; i < N; i++) {
      const ang = rand(0, Math.PI*2), rad = Math.pow(Math.random(), 0.5) * 0.9;
      const cloud = { x: Math.cos(ang)*rad, y: Math.sin(ang)*rad*0.85, driftPhase: rand(0, Math.PI*2), driftAmt: rand(0.01,0.05) };
      const isNucleus = Math.random() < 0.08;
      const ring = Math.floor(Math.random()*3);
      const atom = { isNucleus, ring, radius: isNucleus ? rand(0,0.06) : [0.35,0.55,0.75][ring],
                     incline: [0.15, 0.9, -0.6][ring], angleOffset: rand(0, Math.PI*2),
                     speed: (isNucleus?0.15:[0.35,-0.25,0.5][ring]) };
      const t = rand(0, Math.PI*2);
      const denom = 1 + Math.sin(t)*Math.sin(t);
      const infinity = { bx: (Math.cos(t))/denom, by: (Math.sin(t)*Math.cos(t))/denom };
      let d = Math.random()*totalLen, chosen = edges[0], localT = 0;
      for (const e of edges) { if (d <= e.len) { chosen = e; localT = d/e.len; break; } d -= e.len; }
      const mx = chosen.p[0] + (chosen.q[0]-chosen.p[0])*localT;
      const my = chosen.p[1] + (chosen.q[1]-chosen.p[1])*localT;
      const inward = rand(0.75, 1.0);
      const mark = { x: mx*inward, y: my*inward, pulsePhase: rand(0, Math.PI*2) };
      starParticles.push({ cloud, atom, infinity, mark, size: rand(0.9, 2.4),
        twinklePhase: rand(0, Math.PI*2), twinkleSpeed: rand(0.5, 1.8), colorMix: Math.random() });
    }
  }
  function evalShape(name, p, t) {
    switch (name) {
      case "cloud": {
        const d = Math.sin(t*0.6 + p.cloud.driftPhase) * p.cloud.driftAmt;
        return [p.cloud.x + d, p.cloud.y + Math.cos(t*0.5 + p.cloud.driftPhase)*p.cloud.driftAmt];
      }
      case "atom": {
        const a = p.atom.angleOffset + t*p.atom.speed, r = p.atom.radius;
        return [Math.cos(a)*r, Math.sin(a)*r*Math.cos(p.atom.incline)];
      }
      case "infinity": {
        const rot = t*0.12, cos = Math.cos(rot), sin = Math.sin(rot);
        const x = p.infinity.bx, y = p.infinity.by*0.75;
        return [x*cos - y*sin, x*sin + y*cos];
      }
      case "mark": {
        const pulse = 1 + Math.sin(t*1.2 + p.mark.pulsePhase)*0.02;
        return [p.mark.x*pulse, p.mark.y*pulse];
      }
    }
    return [0, 0];
  }
  function smoothstep(t) { return t*t*(3 - 2*t); }

  function renderGatewayScene(t, dim) {
    idleDrift += 0.05/60;
    progress += (targetProgress + idleDrift - progress) * 0.05;
    const segF = ((progress % SHAPES.length) + SHAPES.length) % SHAPES.length;
    const segIdx = Math.floor(segF), localT = smoothstep(segF - segIdx);
    const shapeA = SHAPES[segIdx], shapeB = SHAPES[(segIdx + 1) % SHAPES.length];
    const cx = W/2, cy = H*0.42, scale = Math.min(W, H) * 0.42;
    const palette = dim ? ["#3a5a52", "#2f4a44", "#5a5a5a"] : ["#3ee6b0", "#29c99a", "#ffffff"];
    for (let i = 0; i < starParticles.length; i++) {
      const p = starParticles[i];
      const [ax, ay] = evalShape(shapeA, p, t), [bx, by] = evalShape(shapeB, p, t);
      const x = ax + (bx-ax)*localT, y = ay + (by-ay)*localT;
      const px = cx + x*scale, py = cy + y*scale;
      if (px < -10 || px > W+10 || py < -10 || py > H+10) continue;
      const twinkle = 0.35 + 0.65*Math.max(0, Math.sin(t*p.twinkleSpeed + p.twinklePhase));
      ctx.globalAlpha = twinkle * (dim ? 0.35 : 0.85);
      ctx.fillStyle = palette[p.colorMix < 0.5 ? 0 : (p.colorMix < 0.85 ? 1 : 2)];
      const s = p.size;
      ctx.fillRect(px - s/2, py - s/2, s, s);
    }
    ctx.globalAlpha = 1;
  }

  function buildBlobs() {
    blobs = [];
    const n = window.innerWidth < 700 ? 4 : 6;
    const colors = ["#ff5c8a", "#ffb84d", "#7c5cff", "#ff8fb3", "#c99bff", "#ffcf8a"];
    for (let i = 0; i < n; i++) {
      blobs.push({ color: colors[i % colors.length], r: rand(0.18, 0.32),
        ax: rand(0.15, 0.35), ay: rand(0.15, 0.35), fx: rand(0.15, 0.3), fy: rand(0.12, 0.27),
        phx: rand(0, Math.PI*2), phy: rand(0, Math.PI*2), ox: rand(0.3,0.7), oy: rand(0.3,0.7) });
    }
  }
  function renderBetaScene(t) {
    ctx.globalCompositeOperation = "lighter";
    for (const b of blobs) {
      const cx = (b.ox + Math.sin(t*b.fx + b.phx)*b.ax) * W;
      const cy = (b.oy + Math.cos(t*b.fy + b.phy)*b.ay) * H;
      const r = Math.min(W, H) * b.r;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
      g.addColorStop(0, b.color + "33");
      g.addColorStop(1, b.color + "00");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2); ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
  }

  function buildConstellation() {
    const n = window.innerWidth < 700 ? 55 : 100;
    constellation = [];
    for (let i = 0; i < n; i++) {
      constellation.push({ x: rand(0,1), y: rand(0,1), vx: rand(-0.02,0.02), vy: rand(-0.015,0.015),
        phase: rand(0, Math.PI*2) });
    }
  }
  function renderEpsilonScene(t, dt) {
    const pts = [];
    for (const p of constellation) {
      p.x += p.vx*dt; p.y += p.vy*dt;
      if (p.x < 0) p.x = 1; if (p.x > 1) p.x = 0;
      if (p.y < 0) p.y = 1; if (p.y > 1) p.y = 0;
      const px = p.x*W, py = p.y*H;
      pts.push([px, py]);
      const twinkle = 0.3 + 0.5*Math.max(0, Math.sin(t*0.8 + p.phase));
      ctx.globalAlpha = twinkle;
      ctx.fillStyle = "#e9eef3";
      ctx.fillRect(px-1, py-1, 2, 2);
    }
    ctx.strokeStyle = "#8ba0b4";
    ctx.lineWidth = 1;
    const maxDist = Math.min(W,H) * 0.14;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i+1; j < pts.length; j++) {
        const dx = pts[i][0]-pts[j][0], dy = pts[i][1]-pts[j][1];
        const dist = Math.hypot(dx, dy);
        if (dist < maxDist) {
          ctx.globalAlpha = 0.12 * (1 - dist/maxDist);
          ctx.beginPath(); ctx.moveTo(pts[i][0], pts[i][1]); ctx.lineTo(pts[j][0], pts[j][1]); ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
  }

  function buildRibbons() {
    ribbons = [];
    const n = 4;
    const colors = ["#0d5c56", "#7a1230", "#0f3a52", "#5c1030"];
    for (let i = 0; i < n; i++) {
      ribbons.push({ color: colors[i % colors.length], amp: rand(0.06, 0.14), freq: rand(1.2, 2.4),
        speed: rand(0.15, 0.35), yOffset: 0.2 + i*0.2, phase: rand(0, Math.PI*2), width: rand(1.5, 3) });
    }
  }
  function renderAlphaScene(t) {
    ctx.fillStyle = "#05070a";
    ctx.fillRect(0, 0, W, H);
    for (const r of ribbons) {
      ctx.beginPath();
      ctx.strokeStyle = r.color;
      ctx.lineWidth = r.width;
      ctx.globalAlpha = 0.55;
      for (let x = 0; x <= W; x += 6) {
        const nx = x / W;
        const y = (r.yOffset + Math.sin(nx*Math.PI*2*r.freq + t*r.speed + r.phase) * r.amp) * H;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function frame(now) {
    const dt = Math.min((now - lastT)/1000, 0.05);
    lastT = now;
    const t = now / 1000;
    ctx.clearRect(0, 0, W, H);
    if (mode === "beta") renderBetaScene(t);
    else if (mode === "epsilon") renderEpsilonScene(t, dt);
    else if (mode === "alpha") renderAlphaScene(t);
    else if (mode === "settings") renderGatewayScene(t, true);
    else renderGatewayScene(t, false);
    raf = requestAnimationFrame(frame);
  }

  function resize() {
    if (!canvas) return;
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * DPR; canvas.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function init(canvasEl) {
    canvas = canvasEl; ctx = canvas.getContext("2d");
    buildStarParticles(); buildBlobs(); buildConstellation(); buildRibbons();
    resize();
    window.addEventListener("resize", resize);
    if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(frame); }
  }

  function setMode(m) { mode = m; }
  function notifyScrollRatio(ratio) { targetProgress = Math.max(0, Math.min(1, ratio)) * SHAPES.length; }

  return { init, setMode, notifyScrollRatio };
})();
"""
