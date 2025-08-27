// create api that mirrors normal python turtle in javascript

// screen where visuals are displayed
class Screen {
    constructor(opts = {}) {
       const {
          canvas = null,
          width = 640,
          height = 480,
          bgcolor = "white",
          pixelRatio = window.devicePixelRatio || 1,
       } = opts;
 
       this.canvas = canvas || this._createCanvas(width, height);
       this.ctx = this.canvas.getContext("2d", { alpha: false });
       this.width = width;
       this.height = height;
       this.pixelRatio = pixelRatio;
       this.bgcolor = bgcolor;
 
       this._configureCanvas();
       this.clearscreen();
    }
    // turtle needs its own canvas to draw
    _createCanvas(w, h) {
       const c = document.createElement("canvas");
       c.width = w;
       c.height = h;
       c.style.width = w + "px";
       c.style.height = h + "px";
       // putting the turtle canvas inside the graphics container
       (document.getElementById("graphics-container") || document.body).appendChild(c);
       return c;
    }
 
    // setting up the canvas
    _configureCanvas() {
       const pr = this.pixelRatio;
       const cssW = this.width, cssH = this.height;
       this.canvas.style.width = cssW + "px";
       this.canvas.style.height = cssH + "px";
       this.canvas.width = Math.floor(cssW * pr);
       this.canvas.height = Math.floor(cssH * pr);
 
       const ctx = this.ctx;
       ctx.setTransform(1, 0, 0, 1, 0, 0);
       ctx.scale(pr, pr);
       // origin is the center
       ctx.translate(cssW / 2, cssH / 2);
       ctx.scale(1, -1);
    }
 
    bgcolor_(color) {
       this.bgcolor = color;
       this.clearscreen();
    }
 
    clearscreen() {
       const ctx = this.ctx;
       ctx.save();
       ctx.setTransform(1, 0, 0, 1, 0, 0);
       ctx.fillStyle = this.bgcolor;
       ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
       ctx.restore();
    }
 
    // Compatibility
    mainloop() { return null; }
    done() { return this.mainloop(); }
    exitonclick() {
       const handler = () => this.canvas.removeEventListener("click", handler);
       this.canvas.addEventListener("click", handler, { once: true });
       return null;
    }
    bye() { this.clearscreen(); return null; }
 }
 
 class Turtle {
    constructor(screen) {
       this.screen = screen;
       this.ctx = screen.ctx;
       this.x = 0;
       this.y = 0;
       this.heading = 0;          // direction turtle is facing, 0 = east
       this.isDown = true;
       this.pencolor = "black";
       this.fillcolor = null;
       this.linewidth = 1;
       this._queue = [];
       this._animating = false; // animating not really working yet, but possible
       this._pathForFill = null;
       this._font = { family: "Arial, sans-serif", size: 16, align: "center" };
    }
 
    // queue so everything runs in order (and animates)
    _enqueue(fn) { this._queue.push(fn); if (!this._animating) this._drain(); }
    _drain() {
       this._animating = true;
       const step = () => {
          let n = 0;
          while (this._queue.length && n < 4) { this._queue.shift()(); n++; }
          if (this._queue.length) requestAnimationFrame(step);
          else this._animating = false;
       };
       requestAnimationFrame(step);
    }
 
    // converts degree to radian
    _degToRad(d) { return d * Math.PI / 180; }
 
    // actually draws
    _lineTo(nx, ny) {
       const ctx = this.ctx;
       ctx.save();
       ctx.lineWidth = this.linewidth;
       ctx.strokeStyle = this.pencolor;
       ctx.beginPath();
       ctx.moveTo(this.x, this.y);
       ctx.lineTo(nx, ny);
       ctx.stroke();
       ctx.restore();
       if (this._pathForFill) this._pathForFill.lineTo(nx, ny);
       this.x = nx; this.y = ny;
    }
    _moveTo(nx, ny) { if (this._pathForFill) this._pathForFill.moveTo(nx, ny); this.x = nx; this.y = ny; }
 
    /* ---- public API ---- */
    forward(d) { this.fd(d); }
 
    fd(dist) {
       this._enqueue(() => {
          // uses heading direction in queue, not at first run
          const rad = this._degToRad(this.heading);
          const nx = this.x + Math.cos(rad) * dist;
          const ny = this.y + Math.sin(rad) * dist;
 
          if (this.isDown) this._lineTo(nx, ny);
          else this._moveTo(nx, ny);
 
          this._drawCursor?.();
       });
    }
 
    backward(dist) { this.bk(dist); }
    bk(dist) { this.fd(-dist); }
 
 
    right(a) { return this.rt(a); }
 
    rt(a) {
       const da = Number(a) || 0;
       this._enqueue(() => {
          this.heading = (this.heading - da) % 360;
          if (this.heading < 0) this.heading += 360;
          console.log('heading after rt:', this.heading);
          this._drawCursor?.();
       });
    }
 
    left(a) { return this.lt(a); }
 
    lt(a) {
       const da = Number(a) || 0;
       this._enqueue(() => {
          this.heading = (this.heading + da) % 360;
          this._drawCursor?.();
       });
    }
 
 
    penup() { this.up(); }
    up() { this._enqueue(() => { this.isDown = false; }); }
    pendown() { this.down(); }
    down() { this._enqueue(() => { this.isDown = true; }); }
 
    goto(x, y) {
       const nx = +x, ny = +y;
       this._enqueue(() => this.isDown ? this._lineTo(nx, ny) : this._moveTo(nx, ny));
    }
 
    setheading(a) { this._enqueue(() => { this.heading = +a; }); }
    seth(a) { this.setheading(a); }
    home() { this._enqueue(() => { this.x = 0; this.y = 0; this.heading = 0; }); }
 
    color(pen, fill) { this._enqueue(() => { if (pen != null) this.pencolor = pen; if (fill != null) this.fillcolor = fill; }); }
    width(w) { this.pensize(w); }
    pensize(w) { this._enqueue(() => { this.linewidth = +w; }); }
    speed(_) { /* nothing here yet */ }
 
    clear() { this.screen.clearscreen(); }
    reset() {
       this._enqueue(() => {
          this.screen.clearscreen();
          this.x = 0; this.y = 0; this.heading = 0;
          this.isDown = true; this.pencolor = "black"; this.fillcolor = null; this.linewidth = 1; this._pathForFill = null;
       });
    }
 
    begin_fill() { this._enqueue(() => { this._pathForFill = new Path2D(); this._pathForFill.moveTo(this.x, this.y); }); }
    end_fill() {
       this._enqueue(() => {
          if (!this._pathForFill) return;
          const ctx = this.ctx; ctx.save(); ctx.fillStyle = this.fillcolor || this.pencolor; ctx.fill(this._pathForFill); ctx.restore();
          this._pathForFill = null;
       });
    }
 
    circle(radius, extent = 360) {
       const start = this._degToRad(this.heading);
       const sweep = this._degToRad(extent);
       const cx = this.x + Math.cos(start + Math.PI / 2) * radius;
       const cy = this.y + Math.sin(start + Math.PI / 2) * radius;
       this._enqueue(() => {
          const ctx = this.ctx; ctx.save();
          ctx.lineWidth = this.linewidth; ctx.strokeStyle = this.pencolor; ctx.beginPath();
          const anticw = sweep < 0;
          ctx.arc(cx, cy, Math.abs(radius), start, start + sweep, anticw);
          if (this.isDown) ctx.stroke();
          ctx.restore();
          const end = start + sweep;
          const nx = cx - Math.cos(end + Math.PI / 2) * radius;
          const ny = cy - Math.sin(end + Math.PI / 2) * radius;
          if (this._pathForFill) this._pathForFill.arc(cx, cy, Math.abs(radius), start, start + sweep, anticw);
          this.x = nx; this.y = ny; this.heading += extent;
       });
    }
 
    write(text, align = "center", fontTuple = null) {
       this._enqueue(() => {
          const ctx = this.ctx;
          const f = { ...this._font };
          if (Array.isArray(fontTuple)) {
             const [family, size] = fontTuple;
             if (family) f.family = family;
             if (size) f.size = +size;
          }
          ctx.save();
          ctx.scale(1, -1); // flip text upright
          ctx.font = `${f.size}px ${f.family}`;
          ctx.textAlign = ({ left: "left", right: "right", center: "center" }[align] || "center");
          ctx.textBaseline = "middle";
          ctx.fillStyle = this.pencolor;
          ctx.fillText(String(text), this.x, -this.y);
          ctx.restore();
       });
    }
 }
 
 /* -------- module singletons and API -------- */
 const _state = { screen: null, defaultTurtle: null };
 
 // makes sure there is a screen to draw on
 function _ensureScreen(opts) {
    if (!_state.screen) _state.screen = new Screen(opts || {});
    if (!_state.defaultTurtle) _state.defaultTurtle = new Turtle(_state.screen);
    return _state.screen;
 }
 function ScreenFactory(opts) { return new Screen(opts); }
 function TurtleFactory() { _ensureScreen(); return new Turtle(_state.screen); }
 
 const moduleAPI = {
    // called by main.js
    setup({ canvas, width, height, bgcolor, pixelRatio } = {}) {
       _state.screen = new Screen({ canvas, width, height, bgcolor, pixelRatio });
       _state.defaultTurtle = new Turtle(_state.screen);
       return null;
    },
 
    // factories / accessors
    Screen: ScreenFactory,
    Turtle: TurtleFactory,
    getscreen() { _ensureScreen(); return _state.screen; },
 
    // module-level ops on default turtle
    forward: (d) => { _ensureScreen(); _state.defaultTurtle.forward(d); },
    fd: (d) => moduleAPI.forward(d),
    back: (d) => { _ensureScreen(); _state.defaultTurtle.backward(d); },
    backward: (d) => moduleAPI.back(d),
    bk: (d) => moduleAPI.back(d),
    right: (a) => { _ensureScreen(); _state.defaultTurtle.right(a); },
    rt: (a) => moduleAPI.right(a),
    left: (a) => { _ensureScreen(); _state.defaultTurtle.left(a); },
    lt: (a) => moduleAPI.left(a),
    penup: () => { _ensureScreen(); _state.defaultTurtle.penup(); },
    up: () => moduleAPI.penup(),
    pendown: () => { _ensureScreen(); _state.defaultTurtle.pendown(); },
    down: () => moduleAPI.pendown(),
    goto: (x, y) => { _ensureScreen(); _state.defaultTurtle.goto(x, y); },
    setheading: (a) => { _ensureScreen(); _state.defaultTurtle.setheading(a); },
    seth: (a) => moduleAPI.setheading(a),
    color: (p, f) => { _ensureScreen(); _state.defaultTurtle.color(p, f); },
    width: (w) => { _ensureScreen(); _state.defaultTurtle.width(w); },
    pensize: (w) => moduleAPI.width(w),
    speed: (s) => { _ensureScreen(); _state.defaultTurtle.speed(s); },
    clear: () => { _ensureScreen(); _state.defaultTurtle.clear(); },
    reset: () => { _ensureScreen(); _state.defaultTurtle.reset(); },
    home: () => { _ensureScreen(); _state.defaultTurtle.home(); },
    begin_fill: () => { _ensureScreen(); _state.defaultTurtle.begin_fill(); },
    end_fill: () => { _ensureScreen(); _state.defaultTurtle.end_fill(); },
    circle: (r, e = 360) => { _ensureScreen(); _state.defaultTurtle.circle(r, e); },
    write: (t, align, font) => { _ensureScreen(); _state.defaultTurtle.write(t, align, font); },
 
    // CPython-style module-level shims
    mainloop: () => { _ensureScreen(); return _state.screen.mainloop(); },
    done: () => { _ensureScreen(); return _state.screen.done(); },
    exitonclick: () => { _ensureScreen(); return _state.screen.exitonclick(); },
    bye: () => { _ensureScreen(); return _state.screen.bye(); },
 };
 
 export { Screen, Turtle };
 export default moduleAPI;
 