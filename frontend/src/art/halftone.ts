// The "How it works" art: a field of halftone dots that changes shape as the page scrolls,
// from a fork (routing) to a database (verified code) to a magnifying glass (the audit).
// Each shape is a signed distance function: negative inside, positive outside. A dot's
// size comes from how far inside the shape its centre is.

import { clamp, onThemeChange, prefersReducedMotion, smoothstep } from "./dither";

type Shape = (x: number, y: number) => number;

const SPACING = 11; // CSS pixels between dot centres
const FRAME_MS = 1000 / 30;

function circle(x: number, y: number, cx: number, cy: number, r: number): number {
  return Math.hypot(x - cx, y - cy) - r;
}

function segment(x: number, y: number, a: [number, number], b: [number, number], r: number): number {
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  const t = clamp(((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy), 0, 1);
  return Math.hypot(x - a[0] - dx * t, y - a[1] - dy * t) - r;
}

function box(x: number, y: number, cx: number, cy: number, hx: number, hy: number): number {
  const dx = Math.abs(x - cx) - hx;
  const dy = Math.abs(y - cy) - hy;
  return Math.hypot(Math.max(dx, 0), Math.max(dy, 0)) + Math.min(Math.max(dx, dy), 0);
}

function ellipse(x: number, y: number, cy: number, rx: number, ry: number): number {
  return (Math.hypot(x / rx, (y - cy) / ry) - 1) * Math.min(rx, ry);
}

// Coordinates run from -1 to 1 across the canvas, with y pointing down.
const route: Shape = (x, y) =>
  Math.min(
    segment(x, y, [0, 0.75], [0, 0.05], 0.09),
    segment(x, y, [0, 0.05], [-0.55, -0.55], 0.09),
    segment(x, y, [0, 0.05], [0.55, -0.55], 0.09),
    circle(x, y, -0.55, -0.6, 0.17),
    circle(x, y, 0.55, -0.6, 0.17),
    circle(x, y, 0, 0.78, 0.13),
  );

function rim(x: number, y: number, cy: number): number {
  // The lower half of an ellipse outline: the edge of one disk in a stack.
  return y > cy ? Math.abs(ellipse(x, y, cy, 0.55, 0.2)) - 0.035 : 1;
}

const database: Shape = (x, y) => {
  const body = Math.min(
    box(x, y, 0, 0.05, 0.55, 0.6),
    ellipse(x, y, -0.55, 0.55, 0.2),
    ellipse(x, y, 0.65, 0.55, 0.2),
  );
  return Math.max(body, -Math.min(rim(x, y, -0.55), rim(x, y, -0.12), rim(x, y, 0.3)));
};

const magnifier: Shape = (x, y) =>
  Math.min(
    Math.abs(circle(x, y, -0.12, -0.12, 0.45)) - 0.09,
    segment(x, y, [0.22, 0.22], [0.68, 0.68], 0.11),
    segment(x, y, [-0.32, -0.24], [0.08, -0.24], 0.045),
    segment(x, y, [-0.32, -0.06], [0.0, -0.06], 0.045),
    segment(x, y, [-0.32, 0.12], [-0.06, 0.12], 0.045),
  );

const SHAPES = [route, database, magnifier];

interface Position {
  step: number; // the active step, 0 to 2
  from: number;
  to: number;
  t: number; // how far the morph from `from` to `to` has gone
}

/** Where the section is in its scroll, and which shapes to show. */
function scrollPosition(section: HTMLElement): Position {
  const rect = section.getBoundingClientRect();
  const progress = clamp((window.innerHeight * 0.5 - rect.top) / Math.max(1, rect.height), 0, 0.999);
  const step = Math.floor(progress * 3);
  // Each morph is centred on a step boundary: the shape is half-way through changing at
  // the moment the heading and the highlighted step switch.
  const shape = clamp(progress * 3 - 0.5, 0, 2);
  const from = Math.floor(shape);
  const t = from < 2 ? smoothstep(0.3, 0.7, shape - from) : 0;
  return { step, from, to: Math.min(from + 1, 2), t };
}

interface Halftone {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
  ink: string;
  paper: string;
  reduced: boolean;
}

function coverage(shape: Shape, x: number, y: number): number {
  return smoothstep(0.05, -0.12, shape(x, y));
}

function draw(halftone: Halftone, position: Position, now: number): void {
  const { canvas, context } = halftone;
  const spacing = SPACING * (canvas.width / Math.max(1, canvas.clientWidth));
  const columns = Math.floor(canvas.width / spacing);
  const rows = Math.floor(canvas.height / spacing);
  const scale = Math.min(columns, rows) * spacing * 0.46;
  context.clearRect(0, 0, canvas.width, canvas.height);
  const paper = new Path2D();
  const ink = new Path2D();
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const cx = (column + 0.5) * spacing + (canvas.width - columns * spacing) / 2;
      const cy = (row + 0.5) * spacing + (canvas.height - rows * spacing) / 2;
      const x = (cx - canvas.width / 2) / scale;
      const y = (cy - canvas.height / 2) / scale;
      const from = coverage(SHAPES[position.from], x, y);
      const amount = position.t > 0 ? from + (coverage(SHAPES[position.to], x, y) - from) * position.t : from;
      // A slow ripple keeps the dots breathing, like ink on paper.
      const breath = halftone.reduced ? 1 : 0.86 + 0.14 * Math.sin(now * 0.0025 + row * 0.6 + column * 0.9);
      const radius = amount * spacing * 0.52 * breath;
      paper.moveTo(cx + spacing * 0.09, cy);
      paper.arc(cx, cy, spacing * 0.09, 0, Math.PI * 2);
      if (radius > spacing * 0.06) {
        ink.moveTo(cx + radius, cy);
        ink.arc(cx, cy, radius, 0, Math.PI * 2);
      }
    }
  }
  context.fillStyle = halftone.paper;
  context.fill(paper);
  context.fillStyle = halftone.ink;
  context.fill(ink);
}

function readColors(halftone: Halftone): void {
  const style = getComputedStyle(halftone.canvas);
  halftone.ink = style.getPropertyValue("--art-halftone").trim();
  halftone.paper = style.getPropertyValue("--art-halftone-faint").trim();
}

function fitToScreen(canvas: HTMLCanvasElement): void {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(canvas.clientWidth * ratio);
  canvas.height = Math.round(canvas.clientHeight * ratio);
}

/** Start drawing; calls onStep when the active step changes; returns a stop function. */
export function startHalftone(
  canvas: HTMLCanvasElement,
  section: HTMLElement,
  onStep: (step: number) => void,
): () => void {
  const context = canvas.getContext("2d");
  if (!context) {
    return () => undefined;
  }
  const halftone: Halftone = { canvas, context, ink: "", paper: "", reduced: prefersReducedMotion() };
  readColors(halftone);
  fitToScreen(canvas);
  let visible = false;
  let lastKey = "";
  let lastStep = -1;
  let lastPaint = 0;
  const resizeObserver = new ResizeObserver(() => {
    fitToScreen(canvas);
    lastKey = "";
  });
  const visibility = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
  });
  const recolor = () => {
    readColors(halftone);
    lastKey = "";
  };
  resizeObserver.observe(canvas);
  visibility.observe(section);
  const stopWatchingTheme = onThemeChange(recolor);
  let frame = requestAnimationFrame(function loop(now) {
    frame = requestAnimationFrame(loop);
    if (!visible || now - lastPaint < FRAME_MS) {
      return;
    }
    const position = scrollPosition(section);
    if (position.step !== lastStep) {
      lastStep = position.step;
      onStep(position.step);
    }
    // With reduced motion, redraw only when the scroll position changes the picture.
    const key = `${position.from}-${position.to}-${position.t.toFixed(3)}`;
    if (!halftone.reduced || key !== lastKey) {
      lastKey = key;
      lastPaint = now;
      draw(halftone, position, now);
    }
  });
  return () => {
    cancelAnimationFrame(frame);
    resizeObserver.disconnect();
    visibility.disconnect();
    stopWatchingTheme();
  };
}
