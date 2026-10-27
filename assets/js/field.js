/* Site-wide background: a quantization field.
   Free "weights" drift on a smooth flow over a faint lattice of quantization
   levels. Every few seconds a calibration sweep crosses the page; each weight
   it passes snaps to its nearest level (the rounding error is drawn as a short
   tick), holds, and is released back to full precision. A few weights are
   pruned at each pass and regrow elsewhere. The lattice is coarser on one side
   of the page than the other, like mixed-precision bit-widths.
   Decorative only: the canvas is aria-hidden, sits behind the content and
   never takes pointer events. It pauses while the tab is hidden and draws a
   single still frame under reduced motion. */
(function () {
  "use strict";

  var canvas = document.getElementById("field");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var SWEEP_EVERY = 9000;   // ms between calibration sweeps
  var SWEEP_TIME = 3200;    // ms for a sweep to cross the page
  var HOLD = 2600;          // ms a weight stays quantized
  var SNAP_TIME = 420;      // ms to glide onto its level
  var PRUNE = 0.06;         // share of weights pruned per sweep

  var W = 0, H = 0, DPR = 1, step = 40;
  var weights = [], colors = {}, sweepStart = 0, lastSweep = -SWEEP_EVERY + 1500;
  var running = false, raf = 0, t0 = performance.now();

  function readColors() {
    var s = getComputedStyle(document.documentElement);
    colors = {
      grid: s.getPropertyValue("--field-grid").trim() || "rgba(255,255,255,0.07)",
      free: s.getPropertyValue("--field-free").trim() || "rgba(111,179,232,0.55)",
      snap: s.getPropertyValue("--field-snap").trim() || "rgba(255,92,102,0.9)",
      err:  s.getPropertyValue("--field-err").trim()  || "rgba(255,92,102,0.28)"
    };
  }

  // Lattice spacing: fine (8-bit) on the left, coarse (4-bit) on the right
  function spacingAt(x) { return x < W * 0.5 ? step : step * 2; }
  function nearestLevel(x, y) {
    var s = spacingAt(x);
    return { x: Math.round(x / s) * s, y: Math.round(y / s) * s };
  }

  function spawn(w) {
    w.x = Math.random() * W;
    w.y = Math.random() * H;
    w.r = 0.9 + Math.random() * 1.3;
    w.phase = Math.random() * Math.PI * 2;
    w.state = "free";     // free | snapping | held | releasing | pruned
    w.t = 0;
    w.alpha = 0;          // fades in on (re)spawn
    return w;
  }

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    step = W < 640 ? 34 : 42;
    var n = Math.round(Math.min(150, Math.max(45, (W * H) / 11000)));
    while (weights.length < n) weights.push(spawn({}));
    weights.length = n;
  }

  // Smooth, cheap flow field: a sum of a few sines
  function flow(x, y, t) {
    var a = Math.sin(x * 0.0021 + t * 0.00011) + Math.cos(y * 0.0027 - t * 0.00009);
    var b = Math.cos(x * 0.0017 - t * 0.00007) - Math.sin(y * 0.0023 + t * 0.00012);
    return { x: a * 0.16, y: b * 0.16 };
  }

  function ease(t) { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); }

  function drawLattice() {
    ctx.fillStyle = colors.grid;
    var half = W * 0.5;
    var s, x, y;
    for (s = step, x = 0; x <= half; x += s) for (y = 0; y <= H + s; y += s) ctx.fillRect(x - 0.75, y - 0.75, 1.5, 1.5);
    for (s = step * 2, x = Math.ceil(half / s) * s; x <= W + s; x += s) for (y = 0; y <= H + s; y += s) ctx.fillRect(x - 1, y - 1, 2, 2);
  }

  function frame(now) {
    var t = now - t0;
    ctx.clearRect(0, 0, W, H);
    drawLattice();

    // calibration sweep: a soft vertical front moving left to right
    if (t - lastSweep > SWEEP_EVERY) { lastSweep = t; sweepStart = t; }
    var sp = (t - sweepStart) / SWEEP_TIME;
    var front = sp >= 0 && sp <= 1 ? ease(sp) * (W + 160) - 80 : -1;
    if (front >= 0) {
      var g = ctx.createLinearGradient(front - 70, 0, front + 6, 0);
      g.addColorStop(0, "rgba(0,0,0,0)");
      g.addColorStop(1, colors.err);
      ctx.fillStyle = g;
      ctx.globalAlpha = 0.35;
      ctx.fillRect(front - 70, 0, 76, H);
      ctx.globalAlpha = 1;
    }

    var held = [];
    for (var i = 0; i < weights.length; i++) {
      var w = weights[i];
      w.alpha = Math.min(1, w.alpha + 0.012);

      if (w.state === "free") {
        var f = flow(w.x, w.y, t);
        w.x += f.x + Math.sin(t * 0.0006 + w.phase) * 0.05;
        w.y += f.y + Math.cos(t * 0.0005 + w.phase) * 0.05;
        if (w.x < -20 || w.x > W + 20 || w.y < -20 || w.y > H + 20) spawn(w);
        if (front >= 0 && Math.abs(w.x - front) < 6) {
          if (Math.random() < PRUNE) { w.state = "pruned"; w.t = t; }
          else { var q = nearestLevel(w.x, w.y); w.fx = w.x; w.fy = w.y; w.qx = q.x; w.qy = q.y; w.state = "snapping"; w.t = t; }
        }
      } else if (w.state === "snapping" || w.state === "held" || w.state === "releasing") {
        var k;
        if (w.state === "snapping") { k = ease((t - w.t) / SNAP_TIME); if (k >= 1) { w.state = "held"; w.t = t; } }
        else if (w.state === "held") { k = 1; if (t - w.t > HOLD) { w.state = "releasing"; w.t = t; } }
        else { k = 1 - ease((t - w.t) / SNAP_TIME); if (k <= 0) { w.state = "free"; w.x = w.fx; w.y = w.fy; } }
        if (w.state !== "free") {
          w.x = w.fx + (w.qx - w.fx) * k;
          w.y = w.fy + (w.qy - w.fy) * k;
          // rounding error: tick from the full-precision value to its level
          ctx.strokeStyle = colors.err;
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(w.fx, w.fy); ctx.lineTo(w.x, w.y); ctx.stroke();
          if (k > 0.98) held.push(w);
        }
      } else if (w.state === "pruned") {
        w.alpha = Math.max(0, 1 - (t - w.t) / 700);
        if (w.alpha <= 0) spawn(w);
      }

      var snapped = w.state === "held" || (w.state === "snapping" && t - w.t > SNAP_TIME * 0.6);
      ctx.globalAlpha = w.alpha;
      ctx.fillStyle = snapped ? colors.snap : colors.free;
      ctx.beginPath();
      ctx.arc(w.x, w.y, snapped ? w.r + 0.8 : w.r, 0, Math.PI * 2);
      ctx.fill();
      if (w.state === "pruned") {
        ctx.strokeStyle = colors.free;
        ctx.beginPath(); ctx.moveTo(w.x - 3, w.y - 3); ctx.lineTo(w.x + 3, w.y + 3); ctx.moveTo(w.x + 3, w.y - 3); ctx.lineTo(w.x - 3, w.y + 3); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;

    // quantized neighbours on adjacent levels form a sparse weight matrix
    ctx.strokeStyle = colors.err;
    ctx.lineWidth = 1;
    for (var a = 0; a < held.length; a++) {
      for (var b = a + 1; b < held.length; b++) {
        var dx = Math.abs(held[a].qx - held[b].qx), dy = Math.abs(held[a].qy - held[b].qy);
        var s = spacingAt(held[a].qx);
        if ((dx === 0 && dy > 0 && dy <= s * 2) || (dy === 0 && dx > 0 && dx <= s * 2)) {
          ctx.beginPath(); ctx.moveTo(held[a].qx, held[a].qy); ctx.lineTo(held[b].qx, held[b].qy); ctx.stroke();
        }
      }
    }

    if (running) raf = requestAnimationFrame(frame);
  }

  function stillFrame() {
    // a sweep caught halfway: the left half quantized, the right half free
    weights.forEach(function (w) {
      w.alpha = 1;
      if (w.x < W * 0.45) { var q = nearestLevel(w.x, w.y); w.fx = w.x; w.fy = w.y; w.qx = q.x; w.qy = q.y; w.state = "held"; w.t = 0; }
    });
    t0 = performance.now();
    running = false;
    frame(t0 + 1);
  }

  function start() { if (!running && !reduced) { running = true; raf = requestAnimationFrame(frame); } }
  function stop() { running = false; cancelAnimationFrame(raf); }

  readColors();
  resize();
  window.addEventListener("resize", function () { resize(); if (reduced) stillFrame(); });
  document.addEventListener("visibilitychange", function () { document.hidden ? stop() : start(); });
  document.addEventListener("themechange", function () { readColors(); if (reduced) stillFrame(); });

  if (reduced) stillFrame(); else start();
})();
