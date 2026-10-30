// Crayon pictures in SVG: wobbly doubled lines, scribbled colouring-in, and a waxy filter.
// scripts/build.py inlines this file into each page. The scene calls crayon.draw({ name(P) { ... } }),
// and every <svg data-draw="name"> is drawn with a pen P. SKILL.md documents the pen.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const COLORS = {
    INK: "#3a352e", RED: "#e0393e", ORANGE: "#f08a24", YELLOW: "#f6c22e", GREEN: "#3b9a4f", BLUE: "#2f6bd0",
    SKY: "#86b9ec", PURPLE: "#8a48b8", PINK: "#e86aa6", BROWN: "#8b5a33", GRAY: "#9c9488", PAPER: "#fffefa",
    TERM: "#9fe0a0",
  };
  const { INK, RED, ORANGE, YELLOW, GREEN, BLUE, SKY, BROWN, GRAY, PAPER } = COLORS;
  const f = (n) => n.toFixed(1);

  function arc(cx, cy, rx, ry, a0, a1, n = 20) {
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const a = a0 + ((a1 - a0) * i) / n;
      pts.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]);
    }
    return pts;
  }

  // A rounded pill, such as an on/off switch.
  function pill(cx, cy, w, h) {
    const r = h / 2;
    return [...arc(cx - w / 2 + r, cy, r, r, Math.PI / 2, Math.PI * 1.5, 8), ...arc(cx + w / 2 - r, cy, r, r, -Math.PI / 2, Math.PI / 2, 8)];
  }

  function smooth(pts) {
    let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += ` C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
    }
    return d;
  }

  // Seeded from the picture's name, so each picture wobbles the same way on every load and after edits elsewhere.
  function random(seed) {
    let s = seed % 2147483646 + 1;
    return () => (s = (s * 16807) % 2147483647) / 2147483647;
  }
  const hash = (s) => [...s].reduce((h, ch) => (h * 31 + ch.codePointAt(0)) % 2147483647, 7);

  function pen(svg, seed) {
    const rnd = random(seed);
    const jit = (a) => (rnd() * 2 - 1) * a;
    const add = (parent, tag, attrs) => {
      const e = document.createElementNS(NS, tag);
      for (const k in attrs) e.setAttribute(k, attrs[k]);
      parent.appendChild(e);
      return e;
    };
    // Everything drawn goes through the crayon filter; plain text sits on top so small labels stay legible.
    let under = add(svg, "g", {}), wax = add(svg, "g", { filter: "url(#crayon)" }), over = add(svg, "g", {});

    const P = {
      dash: null,
      arc,
      pill,
      jit,
      stroke(d, c = INK, w = 2.4, o = 1) {
        const a = { d, stroke: c, "stroke-width": w, fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round", opacity: o };
        if (P.dash) a["stroke-dasharray"] = P.dash;
        add(wax, "path", a);
      },
      // Gone over twice, like a kid tracing their own line.
      line(x1, y1, x2, y2, c = INK, w = 2.4) {
        for (let i = 0; i < 2; i++) {
          P.stroke(`M${f(x1 + jit(1.1))} ${f(y1 + jit(1.1))} Q${f((x1 + x2) / 2 + jit(1.8))} ${f((y1 + y2) / 2 + jit(1.8))} ${f(x2 + jit(1.1))} ${f(y2 + jit(1.1))}`, c, i ? w * 0.65 : w, i ? 0.6 : 1);
        }
      },
      poly(pts, c, w, closed) {
        const n = closed ? pts.length : pts.length - 1;
        for (let i = 0; i < n; i++) {
          const a = pts[i], b = pts[(i + 1) % pts.length];
          P.line(a[0], a[1], b[0], b[1], c, w);
        }
      },
      rect(x, y, w, h, c, sw) { P.poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], c, sw, true); },
      curve(pts, c = INK, w = 2.4) { P.stroke(smooth(pts.map(([x, y]) => [x + jit(0.8), y + jit(0.8)])), c, w); },
      ring(cx, cy, rx, ry, c = INK, w = 2.4) {
        const a0 = rnd() * 6.28;
        P.stroke(smooth(arc(cx, cy, rx, ry, a0, a0 + 6.28 * 1.08, 26).map(([x, y]) => [x + jit(rx * 0.04), y + jit(ry * 0.04)])), c, w);
      },
      arrow(x1, y1, x2, y2, c = INK, w = 2.4, bend = 0) {
        let from = [x1, y1];
        if (bend) {
          const len = Math.hypot(x2 - x1, y2 - y1) || 1;
          from = [(x1 + x2) / 2 - ((y2 - y1) / len) * bend, (y1 + y2) / 2 + ((x2 - x1) / len) * bend];
          P.curve([[x1, y1], from, [x2, y2]], c, w);
        } else P.line(x1, y1, x2, y2, c, w);
        const a = Math.atan2(y2 - from[1], x2 - from[0]);
        [-0.5, 0.5].forEach((da) => P.line(x2, y2, x2 - 9 * Math.cos(a + da), y2 - 9 * Math.sin(a + da), c, w));
      },
      // Colouring in: one back-and-forth scribble across a convex shape.
      fillPoly(pts, c, o = 0.45, gap = 4.5) {
        const ys = pts.map((p) => p[1]), y0 = Math.min(...ys), y1 = Math.max(...ys);
        let d = "", left = true;
        for (let y = y0 + gap * 0.6; y < y1 - gap * 0.3; y += gap) {
          const xs = [];
          pts.forEach((a, i) => {
            const b = pts[(i + 1) % pts.length];
            if (a[1] !== b[1] && (a[1] - y) * (b[1] - y) <= 0) xs.push(a[0] + ((y - a[1]) / (b[1] - a[1])) * (b[0] - a[0]));
          });
          if (xs.length < 2) continue;
          const x = left ? Math.min(...xs) + 1.5 : Math.max(...xs) - 1.5;
          d += `${d ? " L" : "M"}${f(x + jit(1.4))} ${f(y + jit(0.9))}`;
          left = !left;
        }
        if (d) P.stroke(d, c, gap * 1.35, o);
      },
      fill(x, y, w, h, c, o, gap) { P.fillPoly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], c, o, gap); },
      blob(cx, cy, rx, ry, c, o, gap) { P.fillPoly(arc(cx, cy, rx, ry, 0, 6.283, 24), c, o, gap); },
      dot(cx, cy, r, c = INK) { add(wax, "circle", { cx, cy, r, fill: c }); },
      // Solid, under the crayon: the paper behind a list, or a screen whose text must stay readable.
      paper(x, y, w, h, c = PAPER) { add(under, "rect", { x, y, width: w, height: h, rx: 3, fill: c }); },
      text(x, y, s, size = 12, c = INK, o = {}) {
        const t = add(o.wax ? wax : over, "text", { x, y, "font-size": size, fill: c, "text-anchor": o.anchor || "start", "font-weight": o.bold ? 700 : 400, style: "white-space:pre" });
        const lines = String(s).split("\n");
        if (lines.length === 1) t.textContent = s;
        else lines.forEach((line, i) => { add(t, "tspan", { x, dy: i ? f(size * 1.15) : 0 }).textContent = line; });
        return t;
      },
      tick(x, y, s = 1, c = GREEN) { P.line(x, y, x + 4 * s, y + 5 * s, c, 3); P.line(x + 4 * s, y + 5 * s, x + 12 * s, y - 7 * s, c, 3); },
      cross(x, y, s = 1, c = RED) { P.line(x, y - 5 * s, x + 10 * s, y + 5 * s, c, 3); P.line(x + 10 * s, y - 5 * s, x, y + 5 * s, c, 3); },
      // Draws whatever `draw` adds inside an SVG transform, e.g. "translate(40 10) scale(0.6)" or "rotate(-8 160 90)".
      at(transform, draw) {
        const saved = [under, wax, over];
        under = add(under, "g", { transform });
        wax = add(wax, "g", { transform });
        over = add(over, "g", { transform });
        try { draw(); } finally { [under, wax, over] = saved; }
      },

      // Stamps: ready-made things to put in a picture.
      person(x, feet, o = {}) {
        const hy = feet - 70;
        if (o.hat) {
          P.fillPoly(arc(x, hy - 2, 12, 11, Math.PI, 2 * Math.PI, 12), o.hat, 0.9, 3.5);
          P.line(x - 15, hy - 2, x + 15, hy - 2, ORANGE, 3);
        }
        P.ring(x, hy, 9.5, 10.5);
        if (o.sleep) { P.line(x - 6, hy + 1, x - 2, hy + 1, INK, 1.6); P.line(x + 2, hy + 1, x + 6, hy + 1, INK, 1.6); }
        else { P.dot(x - 3.5, hy, 1.5); P.dot(x + 3.5, hy, 1.5); }
        P.stroke(`M${x - 4} ${hy + 4.5} Q${x} ${hy + 8} ${x + 4} ${hy + 4.5}`, INK, 1.6);
        P.line(x, hy + 10.5, x, feet - 30);
        P.line(x, feet - 30, x - 10, feet);
        P.line(x, feet - 30, x + 10, feet);
        (o.arms || [[x - 14, hy + 40], [x + 14, hy + 40]]).forEach(([ax, ay]) => P.line(x, hy + 20, ax, ay));
      },
      robot(x, feet, o = {}) {
        const top = feet - 125;
        P.line(x, top, x, top - 12, INK, 2.2);
        P.dot(x, top - 15, 4.5, RED);
        P.fill(x - 24, top, 48, 38, GRAY, 0.4);
        P.rect(x - 24, top, 48, 38);
        if (o.sleep) { P.line(x - 14, top + 15, x - 6, top + 15, INK, 2); P.line(x + 6, top + 15, x + 14, top + 15, INK, 2); }
        else { P.dot(x - 10, top + 15, 4.2, BLUE); P.dot(x + 10, top + 15, 4.2, BLUE); }
        P.stroke(`M${x - 9} ${top + 27} Q${x} ${top + 33} ${x + 9} ${top + 27}`, INK, 2);
        P.line(x, top + 38, x, top + 46);
        P.fill(x - 30, top + 46, 60, 54, o.color || SKY, 0.45);
        P.rect(x - 30, top + 46, 60, 54);
        (o.arms || [[x - 42, top + 80], [x + 42, top + 80]]).forEach(([hx, hy], i) => P.line(i ? x + 30 : x - 30, top + 60, hx, hy));
        if (o.switch) {
          const on = o.switch === "on", sw = pill(x, top + 66, 40, 18), knob = on ? x + 11 : x - 11;
          P.fillPoly(sw, on ? GREEN : GRAY, 0.55, 3);
          P.curve([...sw, sw[0]], INK, 2);
          P.blob(knob, top + 66, 6.5, 6.5, PAPER, 0.95, 2.5);
          P.ring(knob, top + 66, 7, 7, INK, 1.8);
          P.text(x, top + 91, on ? "ON" : "OFF", 13, on ? GREEN : INK, { anchor: "middle", bold: true });
        }
        P.line(x - 14, top + 100, x - 14, top + 124);
        P.line(x + 14, top + 100, x + 14, top + 124);
        P.line(x - 22, top + 125, x - 12, top + 125, INK, 3);
        P.line(x + 12, top + 125, x + 22, top + 125, INK, 3);
      },
      house(x, ground, o = {}) {
        const top = ground - 72, roof = o.roof || RED;
        P.fill(x - 49, top, 98, 72, o.wall || YELLOW, 0.35);
        P.rect(x - 49, top, 98, 72);
        P.fillPoly([[x - 53, top + 1], [x, top - 44], [x + 53, top + 1]], roof, 0.55);
        P.poly([[x - 57, top + 2], [x, top - 46], [x + 57, top + 2]], roof, 2.8, true);
        P.fill(x - 9, ground - 36, 20, 36, BROWN, 0.6, 4);
        P.rect(x - 9, ground - 36, 20, 36, BROWN, 2.2);
        for (const wx of [x - 38, x + 19]) {
          P.fill(wx, top + 12, 22, 20, SKY, 0.6, 4);
          P.rect(wx, top + 12, 22, 20, BLUE, 2);
          P.line(wx + 11, top + 12, wx + 11, top + 32, BLUE, 1.5);
          P.line(wx, top + 22, wx + 22, top + 22, BLUE, 1.5);
        }
      },
      sun(cx, cy, r = 13) {
        P.blob(cx, cy, r, r, YELLOW, 0.75, 4);
        P.ring(cx, cy, r, r, ORANGE, 2.2);
        for (let i = 0; i < 8; i++) {
          const a = (i * Math.PI) / 4;
          P.line(cx + Math.cos(a) * (r + 5), cy + Math.sin(a) * (r + 5), cx + Math.cos(a) * (r + 12), cy + Math.sin(a) * (r + 12), ORANGE, 2.2);
        }
      },
      cloud(cx, cy, w = 80, h = 40, c = SKY) {
        const pts = [];
        for (let i = 0; i < 48; i++) {
          const a = (i / 48) * Math.PI * 2, bump = 1 + 0.16 * Math.abs(Math.sin(a * 3));
          pts.push([cx + (Math.cos(a) * w * bump) / 2.3, cy + (Math.sin(a) * h * bump) / 2.3]);
        }
        P.fillPoly(pts, c, 0.35, 5);
        P.curve([...pts, pts[0]], c === SKY ? BLUE : INK, 2.2);
      },
      clock(cx, cy, r = 26, o = {}) {
        P.ring(cx, cy, r, r, INK, 2.4);
        for (let i = 0; i < 12; i++) {
          const a = (i * Math.PI) / 6;
          P.line(cx + Math.cos(a) * r * 0.73, cy + Math.sin(a) * r * 0.73, cx + Math.cos(a) * r * 0.85, cy + Math.sin(a) * r * 0.85, GRAY, 1.4);
        }
        const hand = (turns, len) => P.line(cx, cy, cx + Math.sin(turns * 2 * Math.PI) * len, cy - Math.cos(turns * 2 * Math.PI) * len, INK, 2.4);
        const minute = o.minute ?? 0;
        hand(minute / 60, r * 0.69);
        hand(((o.hour ?? 3) % 12) / 12 + minute / 720, r * 0.5);
        P.dot(cx, cy, 2.6, RED);
      },
      // The screen is (x, y, w, h); write on it in a light colour such as TERM or PAPER.
      laptop(x, y, w, h, o = {}) {
        P.paper(x, y, w, h, o.screen || "#2f2b26");
        P.rect(x, y, w, h, INK, 2.6);
        const base = [[x - 8, y + h + 1], [x + w + 8, y + h + 1], [x + w, y + h + 14], [x, y + h + 14]];
        P.fillPoly(base, GRAY, 0.35);
        P.poly(base, INK, 2.2, true);
      },
      // The screen is (x + 4, y + 10, w - 8, h - 22).
      phone(x, y, w = 44, h = 76, o = {}) {
        P.paper(x + 4, y + 10, w - 8, h - 22, o.screen || PAPER);
        P.rect(x, y, w, h, INK, 2.4);
        P.line(x + w / 2 - 6, y + 5, x + w / 2 + 6, y + 5, INK, 1.6);
        P.ring(x + w / 2, y + h - 6, 3, 3, INK, 1.4);
      },
      doc(x, y, w = 46, h = 58, o = {}) {
        const fold = Math.min(12, w / 4);
        P.paper(x, y, w, h);
        P.poly([[x, y], [x + w - fold, y], [x + w, y + fold], [x + w, y + h], [x, y + h]], INK, 2, true);
        P.poly([[x + w - fold, y], [x + w - fold, y + fold], [x + w, y + fold]], INK, 1.6, false);
        const lines = o.lines ?? Math.floor((h - 14) / 9);
        for (let i = 0; i < lines; i++) {
          const ly = y + 11 + i * 9;
          P.line(x + 7, ly, x + w - (ly < y + fold + 3 ? fold + 5 : 7), ly, GRAY, 1.5);
        }
      },
      // A database: a ring on top, two sides, and the front of the bottom rim.
      drum(cx, top, bottom, rx, ry, fill = SKY) {
        P.fillPoly([[cx - rx, top], [cx + rx, top], ...arc(cx, bottom, rx, ry, 0, Math.PI, 10)], fill, 0.4, 5);
        P.ring(cx, top, rx, ry, INK, 2.4);
        P.line(cx - rx, top, cx - rx, bottom);
        P.line(cx + rx, top, cx + rx, bottom);
        P.curve(arc(cx, bottom, rx, ry, 0, Math.PI, 12));
      },
      // A speech bubble sized to its words; `to: [x, y]` points its tail at the speaker. Returns { rx, ry }.
      bubble(cx, cy, s, o = {}) {
        const size = o.size || 11, lines = String(s).split("\n"), lineH = size * 1.15;
        const t = P.text(cx, f(cy + size * 0.35 - ((lines.length - 1) * lineH) / 2), s, size, o.color || INK, { anchor: "middle" });
        const parts = lines.length > 1 ? [...t.children] : [t];
        const w = Math.max(...parts.map((e) => e.getComputedTextLength()));
        const half = (lines.length * lineH) / 2;
        const ry = Math.max(16, half + 9), rx = (w / 2 + 7) / Math.sqrt(1 - (half / ry) ** 2);
        add(under, "ellipse", { cx, cy, rx: f(rx), ry: f(ry), fill: PAPER });
        P.ring(cx, cy, rx, ry, INK, 2);
        if (o.to) {
          const [tx, ty] = o.to, a = Math.atan2((ty - cy) / ry, (tx - cx) / rx);
          P.line(cx + Math.cos(a) * rx, cy + Math.sin(a) * ry, tx, ty, INK, 1.8);
        }
        return { rx, ry };
      },
    };
    return P;
  }

  const builtins = {
    new(P) {
      P.blob(32, 15, 29, 12, YELLOW, 0.8, 4);
      P.text(32, 21, "NEW!", 16, RED, { anchor: "middle", bold: true, wax: true });
    },
  };

  const FILTER = `<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <filter id="crayon" x="-4%" y="-4%" width="108%" height="108%">
    <feTurbulence type="fractalNoise" baseFrequency=".04" numOctaves="2" seed="4" result="warp"/>
    <feDisplacementMap in="SourceGraphic" in2="warp" scale="3" xChannelSelector="R" yChannelSelector="G" result="wobble"/>
    <feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="1" seed="9" result="grain"/>
    <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3.6 0 0 0 -.95" result="wax"/>
    <feComposite in="wobble" in2="wax" operator="in"/>
  </filter>
</svg>`;

  // Text is measured (speech bubbles), so draw once the handwriting fonts are in, or after 2.5 s without them.
  function fontsLoaded() {
    if (!document.fonts) return Promise.resolve();
    const loads = ['16px "Patrick Hand"', '700 16px "Gaegu"'].map((font) => document.fonts.load(font).catch(() => []));
    return Promise.race([Promise.all(loads), new Promise((done) => setTimeout(done, 2500))]);
  }

  const errors = [];
  let finished;
  // Resolves with { errors } once every picture is drawn; scripts/check.py waits on it.
  window.crayonReady = new Promise((done) => { finished = done; });

  function draw(pictures = {}) {
    const all = { ...builtins, ...pictures };
    if (!document.getElementById("crayon")) document.body.insertAdjacentHTML("afterbegin", FILTER);
    return fontsLoaded().then(() => {
      const seen = {};
      document.querySelectorAll("svg[data-draw]").forEach((svg) => {
        const name = svg.dataset.draw;
        seen[name] = (seen[name] || 0) + 1;
        svg.replaceChildren();
        try {
          if (!all[name]) throw new Error(`no drawing named "${name}" was passed to crayon.draw`);
          all[name](pen(svg, hash(name) + seen[name] * 7919));
        } catch (e) {
          errors.push(`${name}: ${e.message}`);
          console.error(e);
          const t = document.createElementNS(NS, "text");
          t.setAttribute("x", 8);
          t.setAttribute("y", 20);
          t.setAttribute("fill", RED);
          t.dataset.crayonError = "";
          t.textContent = `Drawing "${name}" failed`;
          svg.appendChild(t);
        }
      });
      finished({ errors });
    });
  }

  Object.assign(window, COLORS);
  window.crayon = { draw, colors: COLORS };
})();
