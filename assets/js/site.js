/* Page behaviour: theme toggle, mobile menu, header state, active nav link,
   reveal-on-scroll, stat counters, rotating roles, publication filter,
   dialogs, footer year and the desktop-only Live2D cat. Every part is
   optional: the page reads fine without JavaScript. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ----- Theme -----------------------------------------------------------------
  // The inline script in <head> sets data-theme before first paint; this wires
  // the toggle and remembers the choice.
  var toggle = document.querySelector(".theme-toggle");
  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) { /* private mode */ }
    if (toggle) toggle.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0e0f11" : "#f6f5f2");
    document.dispatchEvent(new CustomEvent("themechange"));
  }
  if (toggle) {
    setTheme(root.getAttribute("data-theme") || "dark");
    toggle.addEventListener("click", function () {
      setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  }

  // ----- Header: mobile menu, scrolled state, active link ----------------------
  var header = document.querySelector(".site-header");
  var navToggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("primary-nav");
  function closeMenu() {
    if (!nav) return;
    nav.classList.remove("open");
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.setAttribute("aria-label", "Open menu");
  }
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) closeMenu(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenu(); });
    document.addEventListener("click", function (e) { if (!header.contains(e.target)) closeMenu(); });
  }
  if (header) {
    var onScroll = function () { header.classList.toggle("scrolled", window.scrollY > 8); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-list a[href^="#"]'));
  if ("IntersectionObserver" in window && navLinks.length) {
    var byId = {};
    navLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        navLinks.forEach(function (a) { a.removeAttribute("aria-current"); });
        var link = byId[entry.target.id];
        if (link) link.setAttribute("aria-current", "true");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(byId).forEach(function (id) { var s = document.getElementById(id); if (s) spy.observe(s); });
  }

  // ----- Reveal on scroll ------------------------------------------------------
  var reveals = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || reduced) {
    reveals.forEach(function (n) { n.classList.add("is-visible"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("is-visible"); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (n) { io.observe(n); });
  }

  // ----- Stat counters ---------------------------------------------------------
  // data-count is the source of truth (scripts/update_citations.py rewrites it)
  var counters = document.querySelectorAll("[data-count]");
  function show(el, n) { el.textContent = Math.round(n).toLocaleString("en-US"); }
  counters.forEach(function (el) { show(el, +el.getAttribute("data-count")); });
  if (!reduced && "IntersectionObserver" in window) {
    var countIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        countIO.unobserve(entry.target);
        var el = entry.target, target = +el.getAttribute("data-count"), start = performance.now();
        (function tick(now) {
          var k = Math.min(1, (now - start) / 1200);
          show(el, target * (1 - Math.pow(1 - k, 3)));
          if (k < 1) requestAnimationFrame(tick);
        })(start);
      });
    }, { threshold: 0.6 });
    counters.forEach(function (el) { countIO.observe(el); });
  }

  // ----- Rotating roles ---------------------------------------------------------
  var rotator = document.querySelector("[data-rotate]");
  if (rotator && !reduced) {
    var words = rotator.getAttribute("data-rotate").split("|");
    var word = rotator.querySelector(".word"), i = 0;
    setInterval(function () {
      if (document.hidden) return;
      word.classList.add("out");
      setTimeout(function () {
        i = (i + 1) % words.length;
        word.textContent = words[i];
        word.classList.remove("out");
      }, 350);
    }, 2800);
  }

  // ----- Publication filter ------------------------------------------------------
  var filterBar = document.querySelector(".filters");
  if (filterBar) {
    filterBar.hidden = false;
    var pubs = document.querySelectorAll(".pub");
    var years = document.querySelectorAll(".year");
    var status = document.getElementById("filter-status");
    var applyFilter = function (area) {
      filterBar.querySelectorAll("button").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-filter") === area));
      });
      var shown = 0;
      pubs.forEach(function (p) {
        var match = area === "all" || (" " + p.getAttribute("data-areas") + " ").indexOf(" " + area + " ") !== -1;
        p.hidden = !match;
        if (match) shown++;
      });
      years.forEach(function (y) {
        var any = false, n = y.nextElementSibling;
        while (n && !n.classList.contains("year")) { if (n.classList.contains("pub") && !n.hidden) any = true; n = n.nextElementSibling; }
        y.hidden = !any;
      });
      if (status) status.textContent = shown + (shown === 1 ? " paper" : " papers") + " shown";
    };
    filterBar.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-filter]");
      if (b) applyFilter(b.getAttribute("data-filter"));
    });
    // research-area chips jump to the list pre-filtered
    document.querySelectorAll("[data-show-area]").forEach(function (a) {
      a.addEventListener("click", function () { applyFilter(a.getAttribute("data-show-area")); });
    });
  }

  // ----- Dialogs (contact QR, work location) ----------------------------------------
  document.querySelectorAll("[data-dialog]").forEach(function (btn) {
    var dlg = document.getElementById(btn.getAttribute("data-dialog"));
    if (!dlg || typeof dlg.showModal !== "function") return;
    btn.addEventListener("click", function () {
      var frame = dlg.querySelector("iframe[data-src]");
      if (frame && !frame.src) frame.src = frame.getAttribute("data-src");
      dlg.showModal();
    });
    dlg.addEventListener("click", function (e) {
      if (e.target === dlg || e.target.closest("[data-close]")) dlg.close();
    });
  });

  // ----- Footer year -------------------------------------------------------------
  var year = document.getElementById("current-year");
  if (year) year.textContent = new Date().getFullYear();

  // ----- Live2D cat: desktops and laptops only (not phones or tablets), loaded when idle --
  var bigScreen = window.matchMedia("(min-width: 992px) and (any-hover: hover) and (any-pointer: fine)");
  if (bigScreen.matches) {
    var loadCat = function () {
      var s = document.createElement("script");
      s.src = "live2dw/lib/L2Dwidget.min.js";
      s.onload = function () {
        if (!window.L2Dwidget) return;
        window.L2Dwidget.init({
          model: { scale: 1, hHeadPos: 0.5, vHeadPos: 0.618, jsonPath: "live2dw/assets/oliver.model.json" },
          display: { superSample: 2, width: 150, height: 300, position: "right", hOffset: 0, vOffset: -20 },
          mobile: { show: false },
          react: { opacityDefault: 0.7, opacityOnHover: 0.2 },
          log: false, pluginJsPath: "lib/", pluginModelPath: "assets/", pluginRootPath: "live2dw/", tagMode: false
        });
      };
      document.body.appendChild(s);
    };
    if ("requestIdleCallback" in window) window.requestIdleCallback(loadCat, { timeout: 4000 });
    else window.addEventListener("load", function () { setTimeout(loadCat, 1500); });
  }
})();
