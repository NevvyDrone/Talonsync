const OWL_SVG = "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 640 512\" width=\"640\" height=\"512\"> <g transform=\"translate(64.0,0)\"> <mask id=\"cut\"> <rect x=\"0\" y=\"0\" width=\"512\" height=\"512\" fill=\"white\"/> <!-- eyes: a goggle visor with two pupils looking ahead (2.17.2) --> <rect x=\"146\" y=\"176\" width=\"220\" height=\"70\" rx=\"35\" fill=\"black\"/> <circle cx=\"208\" cy=\"211\" r=\"21\" fill=\"white\"/> <circle cx=\"304\" cy=\"211\" r=\"21\" fill=\"white\"/> <circle cx=\"208\" cy=\"211\" r=\"8\" fill=\"black\"/> <circle cx=\"304\" cy=\"211\" r=\"8\" fill=\"black\"/> <!-- beak --> <path d=\"M240 262 Q256 256 272 262 L256 292 Z\" fill=\"black\"/> <!-- wing lines --> <path d=\"M150 262 C 136 300 138 344 160 382\" fill=\"none\" stroke=\"black\" stroke-width=\"12\" stroke-linecap=\"round\"/> <path d=\"M362 262 C 376 300 374 344 352 382\" fill=\"none\" stroke=\"black\" stroke-width=\"12\" stroke-linecap=\"round\"/> <!-- belly chevrons --> <g fill=\"none\" stroke=\"black\" stroke-width=\"10\" stroke-linecap=\"round\" stroke-linejoin=\"round\"> <path d=\"M216 336 l14 12 l14 -12\"/><path d=\"M268 336 l14 12 l14 -12\"/> <path d=\"M242 368 l14 12 l14 -12\"/> </g> </mask> <g mask=\"url(#cut)\" fill=\"#FFFFFF\"> <!-- body with ear tufts, one shape --> <path d=\"M256 112 C 300 112 330 120 352 134 L 384 74 L 392 160 C 416 196 424 236 424 280 C 424 372 352 432 256 432 C 160 432 88 372 88 280 C 88 236 96 196 120 160 L 128 74 L 160 134 C 182 120 212 112 256 112 Z\"/> <!-- feet --> <path d=\"M214 426 l -10 24 h 12 l 6 -14 l 6 14 h 12 l -10 -24 Z\"/> <path d=\"M276 426 l -10 24 h 12 l 6 -14 l 6 14 h 12 l -10 -24 Z\"/> </g> <!-- 2.17.3: the visor is an 8-bit rainbow wave (six bands in pixel steps from a retro fantasy-console palette), pupils on top --> <clipPath id=\"visor\"><rect x=\"146\" y=\"176\" width=\"220\" height=\"70\" rx=\"35\"/></clipPath> <g clip-path=\"url(#visor)\"><rect x=\"145.80\" y=\"159.50\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"145.80\" y=\"191.17\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"145.80\" y=\"202.83\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"145.80\" y=\"214.50\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"145.80\" y=\"226.17\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"145.80\" y=\"237.83\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"159.55\" y=\"163.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"159.55\" y=\"194.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"159.55\" y=\"206.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"159.55\" y=\"218.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"159.55\" y=\"229.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"159.55\" y=\"241.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"173.30\" y=\"163.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"173.30\" y=\"194.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"173.30\" y=\"206.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"173.30\" y=\"218.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"173.30\" y=\"229.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"173.30\" y=\"241.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"187.05\" y=\"163.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"187.05\" y=\"194.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"187.05\" y=\"206.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"187.05\" y=\"218.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"187.05\" y=\"229.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"187.05\" y=\"241.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"200.80\" y=\"159.50\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"200.80\" y=\"191.17\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"200.80\" y=\"202.83\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"200.80\" y=\"214.50\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"200.80\" y=\"226.17\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"200.80\" y=\"237.83\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"214.55\" y=\"156.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"214.55\" y=\"187.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"214.55\" y=\"199.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"214.55\" y=\"211.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"214.55\" y=\"222.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"214.55\" y=\"234.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"228.30\" y=\"152.50\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"228.30\" y=\"184.17\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"228.30\" y=\"195.83\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"228.30\" y=\"207.50\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"228.30\" y=\"219.17\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"228.30\" y=\"230.83\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"242.05\" y=\"149.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"242.05\" y=\"180.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"242.05\" y=\"192.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"242.05\" y=\"204.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"242.05\" y=\"215.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"242.05\" y=\"227.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"255.80\" y=\"149.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"255.80\" y=\"180.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"255.80\" y=\"192.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"255.80\" y=\"204.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"255.80\" y=\"215.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"255.80\" y=\"227.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"269.55\" y=\"152.50\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"269.55\" y=\"184.17\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"269.55\" y=\"195.83\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"269.55\" y=\"207.50\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"269.55\" y=\"219.17\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"269.55\" y=\"230.83\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"283.30\" y=\"156.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"283.30\" y=\"187.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"283.30\" y=\"199.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"283.30\" y=\"211.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"283.30\" y=\"222.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"283.30\" y=\"234.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"297.05\" y=\"159.50\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"297.05\" y=\"191.17\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"297.05\" y=\"202.83\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"297.05\" y=\"214.50\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"297.05\" y=\"226.17\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"297.05\" y=\"237.83\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"310.80\" y=\"163.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"310.80\" y=\"194.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"310.80\" y=\"206.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"310.80\" y=\"218.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"310.80\" y=\"229.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"310.80\" y=\"241.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"324.55\" y=\"163.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"324.55\" y=\"194.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"324.55\" y=\"206.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"324.55\" y=\"218.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"324.55\" y=\"229.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"324.55\" y=\"241.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"338.30\" y=\"163.00\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"338.30\" y=\"194.67\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"338.30\" y=\"206.33\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"338.30\" y=\"218.00\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"338.30\" y=\"229.67\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"338.30\" y=\"241.33\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/><rect x=\"352.05\" y=\"159.50\" width=\"14.15\" height=\"32.07\" fill=\"#FF004D\"/><rect x=\"352.05\" y=\"191.17\" width=\"14.15\" height=\"12.07\" fill=\"#FFA300\"/><rect x=\"352.05\" y=\"202.83\" width=\"14.15\" height=\"12.07\" fill=\"#FFEC27\"/><rect x=\"352.05\" y=\"214.50\" width=\"14.15\" height=\"12.07\" fill=\"#00E436\"/><rect x=\"352.05\" y=\"226.17\" width=\"14.15\" height=\"12.07\" fill=\"#29ADFF\"/><rect x=\"352.05\" y=\"237.83\" width=\"14.15\" height=\"32.07\" fill=\"#8E5CFF\"/></g> <circle cx=\"208\" cy=\"211\" r=\"21\" fill=\"#FFFFFF\"/><circle cx=\"304\" cy=\"211\" r=\"21\" fill=\"#FFFFFF\"/> <circle cx=\"208\" cy=\"211\" r=\"8\" fill=\"#1C1F26\"/><circle cx=\"304\" cy=\"211\" r=\"8\" fill=\"#1C1F26\"/> </g> </svg>";
/* TalonStar 4000 - a 90s cable-weather style local forecast, drawn on a 640 x 480 canvas.
   Original look: TalonStar branding, owl bug, procedural animated icons. */
(function () {
  "use strict";
  const W = 640, H = 480;
  const FONT = '"Bahnschrift SemiBold Condensed", "Bahnschrift Condensed", Bahnschrift, "Arial Narrow", "Roboto Condensed", "Segoe UI", sans-serif';

  const THEMES = {
    classic: { sky: ["#1a1258", "#2b2f9a", "#1b2a7a"], band: ["#b4430c", "#f39a2c", "#ffd36a"], panel: ["#26338f", "#1c2670"], edge: "#7d8cf0", edgeDark: "#0d1240",
               title: "#ffe35a", label: "#dfe4ff", value: "#ffe35a", text: "#ffffff", crawl: ["#2a2f6e", "#141842"], accent: "#7fd2ff", map: ["#173d4a", "#0f2b36"] },
    owl:     { sky: ["#1d0f2e", "#3a1d55", "#24113a"], band: ["#6d2d8c", "#c25fd0", "#f3b6ff"], panel: ["#3a2160", "#28164a"], edge: "#b28cf0", edgeDark: "#12081e",
               title: "#ffd27a", label: "#eadcff", value: "#ffd27a", text: "#ffffff", crawl: ["#2c1846", "#170c26"], accent: "#ff9fd8", map: ["#2a2246", "#1a1530"] },
    gryphon: { sky: ["#0b2a2c", "#12474b", "#0c3033"], band: ["#8a5a0c", "#e2a530", "#ffe08a"], panel: ["#14545a", "#0e3c41"], edge: "#6fd6c8", edgeDark: "#041517",
               title: "#ffe08a", label: "#d8fff8", value: "#ffe08a", text: "#ffffff", crawl: ["#103a3e", "#071d20"], accent: "#ffd166", map: ["#164a3e", "#0d3329"] },
    dusk:    { sky: ["#2c1a3d", "#7a3b5c", "#e0855a"], band: ["#1f2a6e", "#3f57c9", "#9fb4ff"], panel: ["#3b2552", "#2a1a3d"], edge: "#ffb38a", edgeDark: "#140b1d",
               title: "#ffffff", label: "#ffe2d1", value: "#ffd08a", text: "#ffffff", crawl: ["#3a1f45", "#1d1024"], accent: "#ffb38a", map: ["#3d2a4f", "#291c37"] },
  };

  const PAGE_TITLES = {
    current: ["Current", "Conditions"], observations: ["Latest", "Observations"], local: ["Local", "Forecast"],
    extended: ["Extended", "Forecast"], hourly: ["Hourly", "Outlook"], regional: ["Regional", "Observations"],
    almanac: ["Almanac", ""], agenda: ["Aerie", "Agenda"],
  };

  const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
  const back = (x) => { x = Math.min(1, Math.max(0, x)); const c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));

  class TalonStar {
    constructor(canvas) {
      this.c = canvas;
      this.g = canvas.getContext("2d");
      this.w = null; this.extras = {};
      this.s = { pages: Object.keys(PAGE_TITLES), page_seconds: 10, theme: "classic", crt: true, scanlines: 0.35, crawl: true,
                 crawl_text: "", crawl_speed: 90, clock24: false, show_seconds: true, animations: "full" };
      this.queue = []; this.qi = 0; this.pageStart = 0; this.prev = null; this.prevStart = 0;
      this.crawlX = W; this.running = false; this.t0 = performance.now();
      this._frame = this._frame.bind(this);
      this.resize();
    }
    resize() {
      const r = this.c.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const scale = Math.max(1, (r.width || W) / W) * dpr;
      this.c.width = Math.round(W * scale); this.c.height = Math.round(H * scale);
      this.scale = scale;
    }
    setData(w, extras) { const first = !this.w; this.w = w; this.extras = extras || {}; if (first) this.rebuild(true); }
    setSettings(s) {
      const pagesChanged = JSON.stringify(s.pages) !== JSON.stringify(this.s.pages);
      Object.assign(this.s, s);
      if (pagesChanged) this.rebuild(true);
    }
    get th() { return THEMES[this.s.theme] || THEMES.classic; }
    get anim() { return this.s.animations || "full"; }
    now() { return (performance.now() - this.t0) / 1000; }
    start() { if (!this.running) { this.running = true; this.rebuild(false); requestAnimationFrame(this._frame); } }
    stop() { this.running = false; }
    next() { this.advance(); }
    prevPage() { this.qi = (this.qi - 2 + this.queue.length * 2) % Math.max(1, this.queue.length); this.advance(); }

    // the play list: local forecast and observations may need several screens
    rebuild(reset) {
      const q = [];
      const pages = (this.s.pages || []).filter((p) => PAGE_TITLES[p]);
      for (const p of pages) {
        if (p === "local") {
          const screens = this.localScreens();
          screens.forEach((lines, i) => q.push({ page: p, lines, sub: i }));
        } else if (p === "agenda" && !(this.extras.events || []).length && !(this.extras.tasks || []).length) {
          continue;
        } else q.push({ page: p });
      }
      if (!q.length) q.push({ page: "current" });
      this.queue = q;
      if (reset || this.qi >= q.length) { this.qi = 0; this.pageStart = this.now(); this.prev = null; }
    }
    localScreens() {
      const w = this.w; if (!w || !w.narrative) return [[]];
      this.g.font = `24px ${FONT}`;
      const lines = [];
      for (const n of w.narrative) {
        const words = (n.title + "... " + n.text).split(" ");
        let line = "";
        for (const word of words) {
          const tryL = line ? line + " " + word : word;
          if (this.g.measureText(tryL).width > 520 && line) { lines.push(line); line = word; } else line = tryL;
        }
        if (line) lines.push(line);
        lines.push("");
      }
      const screens = []; for (let i = 0; i < lines.length; i += 8) screens.push(lines.slice(i, i + 8));
      return screens.filter((s) => s.some((l) => l)) || [[]];
    }
    advance() {
      this.prev = this.queue[this.qi]; this.prevStart = this.pageStart;
      this.qi = (this.qi + 1) % this.queue.length;
      if (this.qi === 0) this.rebuild(false);
      this.pageStart = this.now();
    }

    _frame() {
      if (!this.running) return;
      const g = this.g;
      g.save();
      try { this.draw(); } catch (e) { if (!this._warned) { console.error(e); this._warned = true; } }
      g.restore();
      if (g.reset && this._warned) { /* a page threw mid-draw: make sure no clip or alpha leaks into the next frame */ g.reset(); this._warned = false; }
      requestAnimationFrame(this._frame);
    }

    // ------------------------------------------------------------ drawing primitives
    txt(str, x, y, size, color, align = "left", opts = {}) {
      const g = this.g;
      g.font = `${opts.weight || ""} ${size}px ${FONT}`;
      g.textAlign = align; g.textBaseline = "alphabetic";
      if (opts.maxW) { while (g.measureText(str).width > opts.maxW && size > 10) { size -= 1; g.font = `${opts.weight || ""} ${size}px ${FONT}`; } }
      g.lineJoin = "round";
      g.fillStyle = "rgba(0,0,0,.85)"; g.fillText(str, x + size * 0.09, y + size * 0.09);          // drop shadow
      g.strokeStyle = "#000"; g.lineWidth = Math.max(2, size * 0.12); g.strokeText(str, x, y);       // outline
      g.fillStyle = color; g.fillText(str, x, y);
      return g.measureText(str).width;
    }
    box(x, y, w, h, colors, edge, edgeDark, r = 6) {
      const g = this.g;
      const grd = g.createLinearGradient(0, y, 0, y + h); grd.addColorStop(0, colors[0]); grd.addColorStop(1, colors[1]);
      g.fillStyle = grd; this.rr(x, y, w, h, r); g.fill();
      g.lineWidth = 2; g.strokeStyle = edgeDark; this.rr(x + 1, y + 1, w, h, r); g.stroke();
      g.strokeStyle = edge; this.rr(x, y, w, h, r); g.stroke();
    }
    rr(x, y, w, h, r) { const g = this.g; g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }

    // ------------------------------------------------------------ frame
    draw() {
      const g = this.g, t = this.now(), th = this.th;
      g.setTransform(this.scale, 0, 0, this.scale, 0, 0);
      // page timing
      const cur = this.queue[this.qi] || { page: "current" };
      let dur = Math.max(4, this.s.page_seconds || 10);
      if (cur.page === "local") dur *= 1.1;
      if (cur.page === "observations" || cur.page === "regional") dur *= 1.2;
      if (t - this.pageStart > dur) this.advance();
      const p = this.queue[this.qi] || cur;
      const age = t - this.pageStart;

      this.background(t);
      this.header(p, age, t);
      // content: slide the old page out and the new one in
      const slide = this.anim === "full" ? 0.55 : 0.0001;
      g.save(); g.beginPath(); g.rect(0, 90, W, 330); g.clip();
      if (this.prev && age < slide) {
        const k = ease(age / slide);
        g.save(); g.translate(-k * W, 0); this.page(this.prev, 99, t); g.restore();
        g.save(); g.translate((1 - k) * W, 0); this.page(p, age, t); g.restore();
      } else this.page(p, age, t);
      g.restore();
      this.crawl(t);
      if (this.s.crt) this.crtFx(t);
    }

    background(t) {
      const g = this.g, th = this.th;
      const grd = g.createLinearGradient(0, 0, W * 0.3, H);
      grd.addColorStop(0, th.sky[0]); grd.addColorStop(0.55, th.sky[1]); grd.addColorStop(1, th.sky[2]);
      g.fillStyle = grd; g.fillRect(0, 0, W, H);
      // slow light sweeps, like a studio backdrop
      if (this.anim !== "off") {
        g.save(); g.globalAlpha = 0.07;
        for (let i = 0; i < 3; i++) {
          const x = ((t * 18 + i * 260) % (W + 400)) - 200;
          const sg = g.createLinearGradient(x - 120, 0, x + 120, 0);
          sg.addColorStop(0, "rgba(255,255,255,0)"); sg.addColorStop(0.5, "#fff"); sg.addColorStop(1, "rgba(255,255,255,0)");
          g.fillStyle = sg; g.beginPath(); g.moveTo(x - 160, H); g.lineTo(x - 40, 0); g.lineTo(x + 80, 0); g.lineTo(x - 40, H); g.fill();
        }
        g.restore();
      }
    }

    header(p, age, t) {
      const g = this.g, th = this.th;
      // the band: a slanted gradient bar behind the title
      const grd = g.createLinearGradient(0, 18, 0, 84);
      grd.addColorStop(0, th.band[2]); grd.addColorStop(0.35, th.band[1]); grd.addColorStop(1, th.band[0]);
      g.fillStyle = grd; g.beginPath(); g.moveTo(0, 18); g.lineTo(W, 18); g.lineTo(W, 74); g.lineTo(0, 84); g.closePath(); g.fill();
      g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(0, 84, W, 3);
      this.bug(14, 22, 58, t);
      const [l1, l2] = PAGE_TITLES[p.page] || ["", ""];
      const k = this.anim === "full" ? ease(age / 0.45) : 1;
      g.save(); g.globalAlpha = k;
      const dx = (1 - k) * -30;
      if (l2) { this.txt(l1, 86 + dx, 46, 26, th.title); this.txt(l2, 86 + dx, 74, 26, th.title); }
      else this.txt(l1, 86 + dx, 62, 32, th.title);
      if (p.page === "local" && this.queue.filter((q) => q.page === "local").length > 1) this.txt(`${p.sub + 1}/${this.queue.filter((q) => q.page === "local").length}`, 300, 74, 16, th.text);
      g.restore();
      // clock
      const d = new Date();
      let h = d.getHours(); const ampm = h >= 12 ? "PM" : "AM";
      if (!this.s.clock24) h = h % 12 || 12;
      const mm = String(d.getMinutes()).padStart(2, "0"), ss = String(d.getSeconds()).padStart(2, "0");
      const time = (this.s.clock24 ? String(h).padStart(2, "0") : String(h)) + ":" + mm + (this.s.show_seconds ? ":" + ss : "") + (this.s.clock24 ? "" : " " + ampm);
      this.txt(time, 624, 46, 24, th.text, "right");
      const date = d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }).toUpperCase().replace(",", "");
      this.txt(date, 624, 72, 20, th.text, "right");
    }

    // the TalonStar bug (1.9.1): the Talon Pilot owl in a storm - rain falling past it and a lightning bolt that flashes
    bug(x, y, s, t) {
      const g = this.g;
      if (!TalonStar.owl) { TalonStar.owl = new Image(); TalonStar.owl.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(OWL_SVG); }
      const owl = TalonStar.owl, anim = this.anim !== "off";
      const ow = s * 0.86, oh = ow * 0.8;                       // the owl art is 640 x 512
      if (owl.complete && owl.naturalWidth) {
        g.save(); g.shadowColor = "rgba(20,10,5,.95)"; g.shadowBlur = 0;
        for (const [dx, dy] of [[1.5, 0], [-1.5, 0], [0, 1.5], [0, -1.5]]) { g.shadowOffsetX = dx; g.shadowOffsetY = dy; g.drawImage(owl, x - s * 0.12, y + s * 0.02, ow * 1.25, oh * 1.25); }
        g.restore();
        g.drawImage(owl, x - s * 0.12, y + s * 0.02, ow * 1.25, oh * 1.25);
      }
      // rain, in front of the owl
      g.save(); g.strokeStyle = "rgba(41,97,242,.85)"; g.lineWidth = 2.6; g.lineCap = "round";
      for (let i = 0; i < 6; i++) {
        const fy = anim ? (t * 1.3 + i * 0.43) % 1 : (i * 0.43) % 1;
        const rx = x + i * s * 0.15 + 8 * ((i * 0.61) % 1), ry = y - 6 + fy * (s + 10);
        g.beginPath(); g.moveTo(rx, ry); g.lineTo(rx - 4, ry + 13); g.stroke();
      }
      g.restore();
      // the bolt
      const ph = t % 4, flash = anim && (ph < 0.15 || Math.abs(ph - 0.3) < 0.06);
      const P = [[0.84, 0.02], [0.60, 0.42], [0.76, 0.39], [0.62, 0.86], [0.90, 0.34], [0.73, 0.37]];
      g.beginPath(); P.forEach(([u, v], i) => (i ? g.lineTo : g.moveTo).call(g, x + u * s, y + v * s)); g.closePath();
      g.lineJoin = "round"; g.lineWidth = 3; g.strokeStyle = "#1f1208"; g.stroke();
      g.fillStyle = flash ? "#fffbe6" : "#ffe14a"; g.fill();
    }

    crawl(t) {
      const g = this.g, th = this.th;
      const grd = g.createLinearGradient(0, 424, 0, 480); grd.addColorStop(0, th.crawl[0]); grd.addColorStop(1, th.crawl[1]);
      g.fillStyle = grd; g.fillRect(0, 424, W, 56);
      g.fillStyle = th.edge; g.fillRect(0, 424, W, 2);
      const w = this.w;
      if (this.s.crawl) {
        const msg = this.crawlMessage();
        g.font = `24px ${FONT}`;
        const width = g.measureText(msg).width;
        const speed = this.anim === "off" ? 0 : (this.s.crawl_speed || 90);
        const dt = t - (this._lastT || t); this._lastT = t;
        this.crawlX -= speed * dt;
        if (this.crawlX < -width) this.crawlX = W;
        g.save(); g.beginPath(); g.rect(0, 426, W, 54); g.clip();
        this.txt(msg, this.crawlX, 461, 24, th.text);
        g.restore();
      } else if (w && w.ok) {
        const items = [`Conditions at ${w.place.name}`, `${w.current.temp}°${w.units.temp}  ${w.current.text}`,
                       `Humidity ${w.current.humidity}%   Wind ${w.current.wind_dir || "Calm"} ${w.current.wind || ""}`];
        const i = Math.floor(t / 4) % items.length;
        this.txt(items[i], W / 2, 461, 24, th.text, "center");
      }
    }
    crawlMessage() {
      const w = this.w, parts = [];
      if (this.s.crawl_text) parts.push(this.s.crawl_text);
      if (w && w.ok) {
        const d = w.daily[1];
        parts.push(`Now in ${w.place.name}: ${w.current.temp}° and ${w.current.text.toLowerCase()}.`);
        if (d) parts.push(`${d.dow}: ${d.text}, high ${d.hi}°.`);
        if (w.stale) parts.push("Weather data is a little old - checking again soon.");
      } else if (w && w.error) parts.push(w.error);
      const ev = (this.extras.events || [])[0];
      if (ev) parts.push(`Next on your calendar: ${ev.title}, ${ev.when}.`);
      if (this.extras.np) parts.push(`Now playing on your PC: ${this.extras.np}.`);
      return parts.join("     ★     ");
    }

    crtFx(t) {
      const g = this.g, k = this.s.scanlines ?? 0.35;
      if (k > 0) {
        if (!this._scan || this._scanK !== k) {
          const c = document.createElement("canvas"); c.width = 4; c.height = 4;
          const x = c.getContext("2d"); x.fillStyle = `rgba(0,0,0,${k})`; x.fillRect(0, 2, 4, 1); x.fillStyle = `rgba(0,0,0,${k * 0.5})`; x.fillRect(0, 3, 4, 1);
          this._scan = g.createPattern(c, "repeat"); this._scanK = k;
        }
        g.fillStyle = this._scan; g.fillRect(0, 0, W, H);
      }
      const v = g.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.85);
      v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,.45)");
      g.fillStyle = v; g.fillRect(0, 0, W, H);
      if (this.anim === "full") {   // a faint rolling bar, like an old set
        const y = (t * 40) % (H + 80) - 40;
        const b = g.createLinearGradient(0, y - 40, 0, y + 40);
        b.addColorStop(0, "rgba(255,255,255,0)"); b.addColorStop(0.5, "rgba(255,255,255,.035)"); b.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = b; g.fillRect(0, y - 40, W, 80);
      }
    }

    // ------------------------------------------------------------ pages
    page(p, age, t) {
      const w = this.w;
      if (!w || !w.ok) return this.noData(age);
      const fn = { current: this.pCurrent, observations: this.pObs, local: this.pLocal, extended: this.pExtended,
                   hourly: this.pHourly, regional: this.pRegional, almanac: this.pAlmanac, agenda: this.pAgenda }[p.page];
      (fn || this.pCurrent).call(this, w, age, t, p);
    }
    panel(x = 24, y = 100, w = 592, h = 312) { const th = this.th; this.box(x, y, w, h, th.panel, th.edge, th.edgeDark, 8); }
    reveal(age, i, step = 0.12, start = 0.35) { return this.anim === "full" ? ease((age - start - i * step) / 0.35) : 1; }

    noData(age) {
      const th = this.th; this.panel();
      this.txt("TalonStar 4000", W / 2, 200, 40, th.title, "center");
      const msg = (this.w && this.w.error) || "Waiting for the weather...";
      this.txt(msg, W / 2, 250, 22, th.text, "center", { maxW: 560 });
      this.txt("Set your city in TalonStar settings.", W / 2, 290, 20, th.label, "center");
    }

    pCurrent(w, age, t) {
      const th = this.th, c = w.current, u = w.units;
      this.panel(24, 100, 270, 312);
      this.panel(306, 100, 310, 312);
      this.txt(w.place.name, 159, 132, 26, th.text, "center", { maxW: 250 });
      const k = this.anim === "full" ? ease(age / 1.0) : 1;
      const temp = c.temp == null ? "--" : Math.round(c.temp * k);
      this.txt(`${temp}°`, 159, 206, 70, th.value, "center");
      this.icon(c.icon, 159, 268, 92, t, c.is_day);
      this.txt(c.text, 159, 352, 26, th.text, "center", { maxW: 250 });
      if (w.sample) this.txt("sample weather", 159, 396, 15, th.label, "center");
      const rows = [
        ["Humidity", c.humidity != null ? `${c.humidity}%` : "--"],
        ["Dewpoint", c.dew != null ? `${c.dew}°` : "--"],
        ["Visibility", c.visibility != null ? `${c.visibility} ${u.vis}` : "--"],
        ["Pressure", c.pressure != null ? `${c.pressure} ${u.pressure}` : "--", c.trend],
        ["Wind", c.wind ? `${c.wind_dir} ${c.wind} ${u.wind}` : "Calm"],
        ["Gusts", c.gust && c.gust > (c.wind || 0) + 4 ? `${c.gust} ${u.wind}` : "None"],
        [c.feels != null && c.temp != null && c.feels < c.temp - 1 ? "Wind Chill" : c.feels > (c.temp || 0) + 1 ? "Heat Index" : "Feels Like", c.feels != null ? `${c.feels}°` : "--"],
      ];
      rows.forEach((r, i) => {
        const a = this.reveal(age, i);
        this.g.save(); this.g.globalAlpha = a;
        const y = 140 + i * 40, dx = (1 - a) * 40;
        this.txt(r[0] + ":", 322 + dx, y, 23, th.label);
        const vw = this.txt(r[1], 600 + dx, y, 23, th.value, "right");
        if (r[2]) this.arrow(600 - vw - 16 + dx, y - 8, r[2], th.value);
        this.g.restore();
      });
    }
    arrow(x, y, trend, color) {
      if (trend === "S") return;
      const g = this.g; g.save(); g.translate(x, y); g.fillStyle = color; g.strokeStyle = "#000"; g.lineWidth = 2;
      g.beginPath();
      if (trend === "R") { g.moveTo(0, -9); g.lineTo(7, 1); g.lineTo(2, 1); g.lineTo(2, 8); g.lineTo(-2, 8); g.lineTo(-2, 1); g.lineTo(-7, 1); }
      else { g.moveTo(0, 9); g.lineTo(7, -1); g.lineTo(2, -1); g.lineTo(2, -8); g.lineTo(-2, -8); g.lineTo(-2, -1); g.lineTo(-7, -1); }
      g.closePath(); g.stroke(); g.fill(); g.restore();
    }

    pObs(w, age, t) {
      const th = this.th, u = w.units;
      this.panel();
      this.txt("Location", 44, 132, 21, th.label); this.txt(`°${u.temp}`, 292, 132, 21, th.label, "center");
      this.txt("Weather", 330, 132, 21, th.label); this.txt("Wind", 600, 132, 21, th.label, "right");
      const rows = [{ name: w.place.name, temp: w.current.temp, short: w.current.short, wind: w.current.wind, wind_dir: w.current.wind_dir, icon: w.current.icon, is_day: w.current.is_day }]
        .concat(w.regional || []).slice(0, 7);
      rows.forEach((r, i) => {
        const a = this.reveal(age, i, 0.1);
        this.g.save(); this.g.globalAlpha = a;
        const y = 170 + i * 34, dx = (1 - a) * 60;
        this.txt(r.name, 44 + dx, y, 23, i === 0 ? th.value : th.text, "left", { maxW: 220 });
        this.txt(r.temp == null ? "--" : String(r.temp), 292 + dx, y, 23, th.value, "center");
        this.icon(r.icon, 340 + dx, y - 8, 24, t, r.is_day);
        this.txt(r.short || "", 360 + dx, y, 23, th.text, "left", { maxW: 140 });
        this.txt(r.wind ? `${r.wind_dir} ${r.wind}` : "Calm", 600 + dx, y, 23, th.text, "right");
        this.g.restore();
      });
    }

    pLocal(w, age, t, p) {
      const th = this.th; this.panel();
      (p.lines || []).forEach((line, i) => {
        const a = this.reveal(age, i, 0.08, 0.25);
        this.g.save(); this.g.globalAlpha = a;
        const head = /\.\.\./.test(line) ? line.split("...")[0] : null;
        if (head && i === (p.lines.indexOf(line))) {
          const wd = this.txt(head + "...", 50, 140 + i * 34, 24, th.value);
          this.txt(line.slice(head.length + 3), 50 + wd + 6, 140 + i * 34, 24, th.text);
        } else this.txt(line, 50, 140 + i * 34, 24, th.text);
        this.g.restore();
      });
    }

    pExtended(w, age, t) {
      const th = this.th, u = w.units;
      const days = (w.daily || []).slice(1, 4);
      days.forEach((d, i) => {
        const x = 24 + i * 200, a = this.anim === "full" ? back((age - 0.2 - i * 0.15) / 0.55) : 1;
        const y = 100 + (1 - a) * -60;
        this.g.save(); this.g.globalAlpha = clamp(a, 0, 1);
        this.box(x, y, 192, 312, th.panel, th.edge, th.edgeDark, 8);
        this.txt(new Date(d.date + "T12:00").toLocaleDateString("en-US", { weekday: "long" }), x + 96, y + 36, 26, th.value, "center");
        this.icon(d.icon, x + 96, y + 108, 84, t, 1);
        this.txt(d.short, x + 96, y + 186, 24, th.text, "center", { maxW: 180 });
        this.txt("Lo", x + 50, y + 232, 20, th.label, "center"); this.txt("Hi", x + 142, y + 232, 20, th.label, "center");
        this.txt(d.lo == null ? "--" : String(d.lo), x + 50, y + 276, 40, th.value, "center");
        this.txt(d.hi == null ? "--" : String(d.hi), x + 142, y + 276, 40, th.value, "center");
        if (d.pop != null && d.pop >= 20) this.txt(`${d.pop}% precip`, x + 96, y + 302, 16, th.accent, "center");
        this.g.restore();
      });
    }

    pHourly(w, age, t) {
      const th = this.th, g = this.g;
      this.panel();
      const hrs = (w.hourly || []).slice(0, 24);
      if (hrs.length < 2) return;
      const temps = hrs.map((h) => h.temp ?? 0);
      let lo = Math.min(...temps), hi = Math.max(...temps); if (hi - lo < 6) { hi += 3; lo -= 3; }
      const X = (i) => 60 + i * (520 / (hrs.length - 1)), Y = (v) => 360 - (v - lo) / (hi - lo) * 150;
      // grid
      g.strokeStyle = "rgba(255,255,255,.12)"; g.lineWidth = 1;
      for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; g.beginPath(); g.moveTo(52, Y(v)); g.lineTo(588, Y(v)); g.stroke(); this.txt(String(Math.round(v)), 46, Y(v) + 6, 16, th.label, "right"); }
      const k = this.anim === "full" ? ease((age - 0.3) / 1.6) : 1;
      const n = Math.max(2, Math.ceil(k * hrs.length));
      // area + line
      const ag = g.createLinearGradient(0, 180, 0, 360); ag.addColorStop(0, th.value + "88"); ag.addColorStop(1, th.value + "00");
      g.beginPath(); g.moveTo(X(0), 360);
      for (let i = 0; i < n; i++) g.lineTo(X(i), Y(temps[i]));
      g.lineTo(X(n - 1), 360); g.closePath(); g.fillStyle = ag; g.fill();
      g.beginPath(); for (let i = 0; i < n; i++) (i ? g.lineTo : g.moveTo).call(g, X(i), Y(temps[i]));
      g.lineWidth = 6; g.strokeStyle = "#000"; g.stroke(); g.lineWidth = 3.5; g.strokeStyle = th.value; g.stroke();
      for (let i = 0; i < n; i += 3) {
        const h = hrs[i], hr = new Date(h.time).getHours();
        this.icon(h.icon, X(i), 140, 30, t, hr >= 7 && hr < 19);
        this.txt(String(h.temp ?? "--"), X(i), Y(temps[i]) - 12, 18, th.text, "center");
        const lbl = this.s.clock24 ? `${String(hr).padStart(2, "0")}` : `${hr % 12 || 12}${hr < 12 ? "a" : "p"}`;
        this.txt(lbl, X(i), 392, 18, th.label, "center");
        if (h.pop >= 30) this.txt(`${h.pop}%`, X(i), 180, 14, th.accent, "center");
      }
    }

    pRegional(w, age, t) {
      const th = this.th, g = this.g;
      // stylized map: soft terrain, lat/lon grid, home in the middle
      this.box(24, 100, 592, 312, th.map, th.edge, th.edgeDark, 8);
      g.save(); this.rr(24, 100, 592, 312, 8); g.clip();
      g.strokeStyle = "rgba(255,255,255,.07)"; g.lineWidth = 1;
      for (let x = 24; x < 616; x += 37) { g.beginPath(); g.moveTo(x, 100); g.lineTo(x, 412); g.stroke(); }
      for (let y = 100; y < 412; y += 37) { g.beginPath(); g.moveTo(24, y); g.lineTo(616, y); g.stroke(); }
      for (let i = 0; i < 9; i++) {           // drifting cloud shadows
        const cx = ((i * 97 + t * 6) % 680) - 20, cy = 130 + (i * 53) % 260;
        g.fillStyle = "rgba(255,255,255,.035)"; g.beginPath(); g.ellipse(cx, cy, 70, 26, 0, 0, Math.PI * 2); g.fill();
      }
      g.restore();
      const home = w.place, pts = (w.regional || []).slice(0, 8);
      let span = 0.5;
      for (const r of pts) span = Math.max(span, Math.abs(r.lat - home.lat), Math.abs((r.lon - home.lon) * Math.cos(home.lat * Math.PI / 180)));
      const P = (lat, lon) => [320 + (lon - home.lon) * Math.cos(home.lat * Math.PI / 180) / span * 250, 256 - (lat - home.lat) / span * 125];
      const all = [{ name: home.name, lat: home.lat, lon: home.lon, temp: w.current.temp, icon: w.current.icon, is_day: w.current.is_day, home: true }].concat(pts);
      // keep labels from piling up: nudge apart
      const placed = all.map((r) => { const [x, y] = P(r.lat, r.lon); return { r, x: clamp(x, 80, 560), y: clamp(y, 140, 380) }; });
      for (let it = 0; it < 40; it++) for (let a = 0; a < placed.length; a++) for (let b = a + 1; b < placed.length; b++) {
        const A = placed[a], B = placed[b], dx = B.x - A.x, dy = B.y - A.y;
        if (Math.abs(dx) < 110 && Math.abs(dy) < 52) { const s = dy >= 0 ? 1 : -1; A.y = clamp(A.y - s * 2, 140, 380); B.y = clamp(B.y + s * 2, 140, 380); A.x = clamp(A.x - Math.sign(dx || 1), 80, 560); B.x = clamp(B.x + Math.sign(dx || 1), 80, 560); }
      }
      placed.forEach((p, i) => {
        const a = this.anim === "full" ? back((age - 0.3 - i * 0.12) / 0.5) : 1;
        if (a <= 0) return;
        g.save(); g.translate(p.x, p.y); g.scale(clamp(a, 0.01, 1.2), clamp(a, 0.01, 1.2));
        this.icon(p.r.icon, -22, -6, 34, t, p.r.is_day);
        this.txt(p.r.temp == null ? "--" : String(p.r.temp), 8, 4, 28, th.value);
        this.txt(p.r.name, 0, 30, 17, p.r.home ? th.value : th.text, "center", { maxW: 120 });
        if (p.r.home) { g.strokeStyle = th.value; g.lineWidth = 2; g.beginPath(); g.arc(-22, -6, 24 + Math.sin(t * 3) * 2, 0, Math.PI * 2); g.stroke(); }
        g.restore();
      });
    }

    pAlmanac(w, age, t) {
      const th = this.th, d0 = w.daily[0], d1 = w.daily[1];
      this.panel(24, 100, 592, 132);
      const tm = (s) => { if (!s) return "--"; const d = new Date(s); return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: !this.s.clock24 }); };
      const name = (d) => d ? new Date(d.date + "T12:00").toLocaleDateString("en-US", { weekday: "long" }) : "";
      this.txt(name(d0), 330, 132, 22, th.value, "center"); this.txt(name(d1), 510, 132, 22, th.value, "center");
      [["Sunrise:", "sunrise"], ["Sunset:", "sunset"]].forEach(([lab, k], i) => {
        const a = this.reveal(age, i, 0.15);
        this.g.save(); this.g.globalAlpha = a;
        this.txt(lab, 50, 172 + i * 40, 24, th.label);
        this.txt(tm(d0 && d0[k]), 330, 172 + i * 40, 24, th.text, "center");
        this.txt(tm(d1 && d1[k]), 510, 172 + i * 40, 24, th.text, "center");
        this.g.restore();
      });
      this.panel(24, 244, 592, 168);
      this.txt("Moon Data:", 44, 274, 22, th.label);
      (w.moon || []).slice(0, 4).forEach((m, i) => {
        const x = 106 + i * 143, a = this.anim === "full" ? back((age - 0.6 - i * 0.15) / 0.5) : 1;
        this.g.save(); this.g.globalAlpha = clamp(a, 0, 1);
        this.txt(m.phase, x, 300, 22, th.value, "center");
        const ph = { New: 0, First: 0.25, Full: 0.5, Last: 0.75 }[m.phase];
        this.moon(x, 340, 26 * clamp(a, 0, 1.15), ph, t);
        this.txt(new Date(m.date + "T12:00").toLocaleDateString("en-US", { month: "short", day: "numeric" }), x, 398, 20, th.text, "center");
        this.g.restore();
      });
    }

    pAgenda(w, age, t) {
      const th = this.th, ex = this.extras;
      this.panel();
      this.txt(ex.owner ? `Hello, ${ex.owner}!` : "Hello!", 44, 136, 26, th.value, "left", { maxW: 400 });
      let y = 176;
      (ex.events || []).slice(0, 4).forEach((e, i) => {
        const a = this.reveal(age, i, 0.12); this.g.save(); this.g.globalAlpha = a;
        this.txt(e.when, 44 + (1 - a) * 40, y, 22, th.label, "left", { maxW: 170 });
        this.txt(e.title, 222 + (1 - a) * 40, y, 22, th.text, "left", { maxW: 380 });
        this.g.restore(); y += 34;
      });
      if (ex.tasks && ex.tasks.length) {
        const a = this.reveal(age, 5); this.g.save(); this.g.globalAlpha = a;
        this.txt(`${ex.tasks.length} task${ex.tasks.length > 1 ? "s" : ""} to do: ${ex.tasks.slice(0, 2).join(", ")}`, 44, Math.max(y + 10, 330), 21, th.accent, "left", { maxW: 550 });
        this.g.restore();
      }
      if (ex.pet && ex.pet.petFood != null) {
        const hungry = ex.pet.petFood < 0.35;
        this.txt(hungry ? "Your Hoot-agotchi is hungry!" : "Your Hoot-agotchi is happy. Hoot!", 44, 392, 20, hungry ? th.value : th.label);
      }
    }

    // ------------------------------------------------------------ moon and icons
    moon(x, y, r, phase, t) {
      const g = this.g;
      r = Math.max(0.5, r);
      g.save(); g.translate(x, y);
      g.fillStyle = "#2a2a35"; g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.fill();
      // lit part: phase 0 new, .25 first quarter (right lit), .5 full, .75 last quarter (left lit)
      const lit = "#f4f0d8";
      g.fillStyle = lit;
      if (phase === 0.5) { g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.fill(); }
      else if (phase === 0.25 || phase === 0.75) {
        g.beginPath(); g.arc(0, 0, r, -Math.PI / 2, Math.PI / 2, phase === 0.75); g.closePath(); g.fill();
      }
      g.lineWidth = 2; g.strokeStyle = "#000"; g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.stroke();
      if (phase === 0) { g.strokeStyle = "rgba(255,255,255,.35)"; g.beginPath(); g.arc(0, 0, r - 3, 0, Math.PI * 2); g.stroke(); }
      g.restore();
    }

    icon(kind, x, y, s, t, isDay = 1) {
      const g = this.g, an = this.anim !== "off";
      const T = an ? t : 0;
      g.save(); g.translate(x, y);
      const sun = (cx, cy, r) => {
        g.save(); g.translate(cx, cy); g.rotate(T * 0.4);
        g.strokeStyle = "#ffb627"; g.lineWidth = r * 0.16; g.lineCap = "round";
        for (let i = 0; i < 10; i++) { const a = i * Math.PI / 5, p = 1 + 0.08 * Math.sin(T * 3 + i); g.beginPath(); g.moveTo(Math.cos(a) * r * 1.25, Math.sin(a) * r * 1.25); g.lineTo(Math.cos(a) * r * 1.65 * p, Math.sin(a) * r * 1.65 * p); g.stroke(); }
        g.restore();
        const sg = g.createRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.1, cx, cy, r);
        sg.addColorStop(0, "#fff7b0"); sg.addColorStop(1, "#ffb000");
        g.fillStyle = sg; g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.fill();
        g.lineWidth = 2; g.strokeStyle = "#7a4a00"; g.stroke();
      };
      const moonI = (cx, cy, r) => {
        g.save(); g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.clip();
        g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.arc(cx + r * 0.5, cy - r * 0.25, r * 0.85, 0, Math.PI * 2);
        g.fillStyle = "#f4efc9"; g.fill("evenodd"); g.restore();
        g.beginPath(); g.arc(cx, cy, r, Math.PI * 0.18, Math.PI * 1.55); g.lineWidth = 2; g.strokeStyle = "#5a5330"; g.stroke();
        for (let i = 0; i < 3; i++) { const tw = 0.5 + 0.5 * Math.sin(T * 2 + i * 2); g.fillStyle = `rgba(255,255,220,${tw})`; g.beginPath(); g.arc(cx + r * (0.9 + i * 0.4), cy - r * (0.9 - i * 0.6), 1.6 + s * 0.012, 0, Math.PI * 2); g.fill(); }
      };
      const cloud = (cx, cy, r, dark = false) => {
        const drift = an ? Math.sin(T * 0.7 + cx) * r * 0.08 : 0;
        cx += drift;
        const cg = g.createLinearGradient(0, cy - r, 0, cy + r * 0.7);
        cg.addColorStop(0, dark ? "#8d93a8" : "#ffffff"); cg.addColorStop(1, dark ? "#4c5165" : "#b9c3d8");
        g.fillStyle = cg; g.strokeStyle = "#1a1d2b"; g.lineWidth = 2;
        g.beginPath();
        g.arc(cx - r * 0.55, cy + r * 0.1, r * 0.45, Math.PI * 0.5, Math.PI * 1.5);
        g.arc(cx - r * 0.15, cy - r * 0.3, r * 0.5, Math.PI, Math.PI * 1.85);
        g.arc(cx + r * 0.4, cy - r * 0.05, r * 0.42, Math.PI * 1.3, Math.PI * 0.5);
        g.closePath(); g.fill(); g.stroke();
      };
      const r = s * 0.42;
      const fall = (n, color, len, flake) => {
        for (let i = 0; i < n; i++) {
          const ph = ((T * (flake ? 0.6 : 1.6) + i / n) % 1);
          const px = -r * 0.7 + (i / (n - 1 || 1)) * r * 1.4 + (flake ? Math.sin(T * 2 + i) * r * 0.1 : -ph * r * 0.25);
          const py = r * 0.35 + ph * r * 1.0;
          g.globalAlpha = 1 - ph * 0.7;
          if (flake) { g.fillStyle = color; g.font = `${s * 0.22}px sans-serif`; g.textAlign = "center"; g.fillText("✳", px, py + s * 0.08); }
          else { g.strokeStyle = color; g.lineWidth = Math.max(1.5, s * 0.04); g.lineCap = "round"; g.beginPath(); g.moveTo(px, py); g.lineTo(px - len * 0.3, py + len); g.stroke(); }
        }
        g.globalAlpha = 1;
      };
      switch (kind) {
        case "sun": isDay ? sun(0, 0, r * 0.75) : moonI(0, 0, r * 0.75); break;
        case "partly": isDay ? sun(r * 0.35, -r * 0.35, r * 0.5) : moonI(r * 0.35, -r * 0.4, r * 0.45); cloud(-r * 0.1, r * 0.15, r * 0.8); break;
        case "cloud": cloud(r * 0.3, -r * 0.3, r * 0.6, true); cloud(-r * 0.05, r * 0.1, r * 0.85); break;
        case "fog": {
          g.strokeStyle = "#d8dde8"; g.lineWidth = s * 0.07; g.lineCap = "round";
          for (let i = 0; i < 4; i++) { const o = an ? Math.sin(T * 0.8 + i) * r * 0.25 : 0; g.beginPath(); g.moveTo(-r + o, -r * 0.5 + i * r * 0.38); g.lineTo(r * 0.8 + o, -r * 0.5 + i * r * 0.38); g.stroke(); }
          break;
        }
        case "drizzle": cloud(0, -r * 0.3, r * 0.85); fall(4, "#7fc8ff", r * 0.25, false); break;
        case "rain": case "showers":
          if (kind === "showers" && isDay) sun(r * 0.45, -r * 0.55, r * 0.38);
          cloud(0, -r * 0.3, r * 0.85, kind === "rain"); fall(6, "#5ab4ff", r * 0.45, false); break;
        case "snow": cloud(0, -r * 0.3, r * 0.85); fall(5, "#ffffff", 0, true); break;
        case "sleet": cloud(0, -r * 0.3, r * 0.85); fall(3, "#5ab4ff", r * 0.4, false); fall(3, "#ffffff", 0, true); break;
        case "storm": {
          cloud(0, -r * 0.35, r * 0.9, true); fall(5, "#5ab4ff", r * 0.4, false);
          const flash = an ? ((T % 2.6) < 0.18 || ((T % 2.6) > 0.3 && (T % 2.6) < 0.38)) : true;
          if (flash) {
            g.fillStyle = "#ffe14d"; g.strokeStyle = "#000"; g.lineWidth = 2; g.beginPath();
            g.moveTo(r * 0.05, r * 0.05); g.lineTo(-r * 0.3, r * 0.6); g.lineTo(-r * 0.02, r * 0.55); g.lineTo(-r * 0.2, r * 1.05); g.lineTo(r * 0.35, r * 0.38); g.lineTo(r * 0.06, r * 0.42); g.lineTo(r * 0.3, r * 0.05); g.closePath(); g.fill(); g.stroke();
          }
          break;
        }
        default: cloud(0, 0, r * 0.85);
      }
      g.restore();
    }
  }

  window.TalonStar = TalonStar;
  window.TalonStarPages = PAGE_TITLES;
  window.TalonStarThemes = Object.keys(THEMES);

  // ---------------------------------------------------------------- the jazz loop (sample-accurate WebAudio loop)
  class Jazz {
    constructor(url) { this.url = url; this.ctx = null; this.buf = null; this.src = null; this.gain = null; this.vol = 0.55; this.want = false; this.loading = null; }
    async load() {
      if (this.buf) return;
      if (!this.loading) this.loading = (async () => {
        this.ctx = this.ctx || new (window.AudioContext || window.webkitAudioContext)();
        const r = await fetch(this.url); const data = await r.arrayBuffer();
        this.buf = await this.ctx.decodeAudioData(data);
      })();
      await this.loading;
    }
    async play() {
      this.want = true;
      try { await this.load(); } catch (e) { console.warn("jazz", e); return; }
      if (!this.want || this.src) return;
      if (this.ctx.state === "suspended") await this.ctx.resume();
      this.gain = this.ctx.createGain(); this.gain.gain.value = 0; this.gain.connect(this.ctx.destination);
      this.src = this.ctx.createBufferSource(); this.src.buffer = this.buf; this.src.loop = true; this.src.connect(this.gain);
      this.src.start();
      this.gain.gain.linearRampToValueAtTime(this.vol, this.ctx.currentTime + 1.5);
    }
    stop() {
      this.want = false;
      if (!this.src) return;
      const src = this.src, gain = this.gain; this.src = null;
      gain.gain.cancelScheduledValues(this.ctx.currentTime);
      gain.gain.setValueAtTime(gain.gain.value, this.ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0, this.ctx.currentTime + 0.8);
      setTimeout(() => { try { src.stop(); } catch (e) {} }, 900);
    }
    setVolume(v) { this.vol = v; if (this.gain && this.src) this.gain.gain.setTargetAtTime(v, this.ctx.currentTime, 0.1); }
    get playing() { return !!this.src; }
    get blocked() { return this.ctx && this.ctx.state === "suspended"; }
  }
  window.TalonJazz = Jazz;
})();
