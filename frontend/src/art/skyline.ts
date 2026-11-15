// The hero art: a dithered pixel landscape whose skyline is the real monthly revenue.
// It is drawn at low resolution into an ImageData buffer and scaled up with
// `image-rendering: pixelated`, so every art pixel is a crisp square on screen.

import { MONTHLY_REVENUE } from "../data";
import { clamp, ditherPick, fractalNoise, prefersReducedMotion, readPalette, smoothstep } from "./dither";

const FRAME_MS = 1000 / 30;
const RISE_MS = 1200;
const STAGGER_MS = 55;
const CLOUD_SPEED = 0.00008; // noise units per millisecond

interface Bar {
  left: number;
  right: number;
  top: number;
}

interface Scene {
  width: number;
  height: number;
  cell: number; // screen pixels per art pixel
  groundTop: number;
  bars: Bar[];
  barAt: Int16Array; // which bar covers each column, or -1
}

interface Palettes {
  sky: number[];
  bar: number[];
  hover: number[];
  ground: number[];
}

/** Where a hovered bar's tooltip goes, in CSS pixels inside the canvas. */
export interface SkylineHover {
  index: number;
  x: number;
  y: number;
}

interface Skyline {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
  scene: Scene;
  palettes: Palettes;
  image: ImageData;
  hovered: number;
  visible: boolean;
  reduced: boolean;
  startedAt: number;
  onHover: (hover: SkylineHover | null) => void;
}

function buildScene(cssWidth: number, cssHeight: number): Scene {
  const cell = cssWidth < 600 ? 3 : 4;
  const width = Math.max(1, Math.ceil(cssWidth / cell));
  const height = Math.max(1, Math.ceil(cssHeight / cell));
  const groundTop = Math.round(height * 0.8);
  const span = width * (cssWidth < 600 ? 0.92 : 0.72);
  const slot = span / MONTHLY_REVENUE.length;
  const gap = Math.max(1, Math.round(slot * 0.25));
  const highest = Math.max(...MONTHLY_REVENUE.map((month) => month.revenue));
  const start = (width - span) / 2;
  const bars = MONTHLY_REVENUE.map((month, index) => ({
    left: Math.round(start + index * slot),
    right: Math.round(start + (index + 1) * slot) - gap,
    top: Math.round(groundTop - (month.revenue / highest) * groundTop * 0.72),
  }));
  const barAt = new Int16Array(width).fill(-1);
  bars.forEach((bar, index) => barAt.fill(index, bar.left, bar.right));
  return { width, height, cell, groundTop, bars, barAt };
}

function readPalettes(canvas: HTMLCanvasElement): Palettes {
  return {
    sky: readPalette(canvas, ["--art-sky", "--art-cloud-1", "--art-cloud-2", "--art-cloud-3"]),
    bar: readPalette(canvas, ["--art-bar-1", "--art-bar-2", "--art-bar-3", "--art-bar-4"]),
    hover: readPalette(canvas, ["--art-hover-1", "--art-hover-2", "--art-hover-3", "--art-hover-4"]),
    ground: readPalette(canvas, ["--art-ground-1", "--art-ground-2", "--art-ground-3", "--art-ground-4"]),
  };
}

/** How far a bar has risen in the intro, from 0 to 1, easing out at the end. */
function riseAmount(index: number, elapsed: number): number {
  const t = clamp((elapsed - index * STAGGER_MS) / RISE_MS, 0, 1);
  return 1 - (1 - t) ** 3;
}

function skyColor(scene: Scene, sky: number[], x: number, y: number, drift: number): number {
  // Clouds float in a band across the middle of the sky and drift to the right.
  const density = fractalNoise(x * 0.03 - drift, y * 0.08, 3);
  const band = clamp(1 - Math.abs(y / scene.groundTop - 0.5) * 2.2, 0, 1);
  return ditherPick(sky, smoothstep(0.45, 0.75, density) * band * 1.15, x, y);
}

function groundColor(ground: number[], x: number, y: number, groundTop: number): number {
  if (y === groundTop) {
    return ground[0];
  }
  return ditherPick(ground, fractalNoise(x * 0.2, y * 0.5, 2) * 1.25 - 0.08, x, y);
}

function barColor(palette: number[], bar: Bar, top: number, x: number, y: number): number {
  // Lit from the left: light along the top edge and the left side, darker to the right.
  const across = (x - bar.left) / Math.max(1, bar.right - bar.left - 1);
  const shade = y === top ? 0.95 : 0.8 - across * 0.6;
  return ditherPick(palette, shade, x, y);
}

function paint(skyline: Skyline, elapsed: number, drift: number): void {
  const { scene, palettes, hovered } = skyline;
  const pixels = new Uint32Array(skyline.image.data.buffer);
  const tops = scene.bars.map((bar, index) =>
    Math.round(scene.groundTop - (scene.groundTop - bar.top) * riseAmount(index, elapsed)),
  );
  for (let y = 0; y < scene.height; y += 1) {
    for (let x = 0; x < scene.width; x += 1) {
      const index = scene.barAt[x];
      let color: number;
      if (y >= scene.groundTop) {
        color = groundColor(palettes.ground, x, y, scene.groundTop);
      } else if (index >= 0 && y >= tops[index]) {
        const palette = index === hovered ? palettes.hover : palettes.bar;
        color = barColor(palette, scene.bars[index], tops[index], x, y);
      } else {
        color = skyColor(scene, palettes.sky, x, y, drift);
      }
      pixels[y * scene.width + x] = color;
    }
  }
  skyline.context.putImageData(skyline.image, 0, 0);
}

function render(skyline: Skyline, now: number): void {
  const elapsed = skyline.reduced ? Number.POSITIVE_INFINITY : now - skyline.startedAt;
  const drift = skyline.reduced ? 0 : (now - skyline.startedAt) * CLOUD_SPEED;
  paint(skyline, elapsed, drift);
}

function resize(skyline: Skyline): void {
  skyline.scene = buildScene(skyline.canvas.clientWidth, skyline.canvas.clientHeight);
  skyline.canvas.width = skyline.scene.width;
  skyline.canvas.height = skyline.scene.height;
  skyline.image = skyline.context.createImageData(skyline.scene.width, skyline.scene.height);
  render(skyline, performance.now());
}

function pointAt(skyline: Skyline, clientX: number | null): void {
  // Work from the canvas's on-screen box, so zoom or CSS scaling cannot shift the bars.
  const rect = skyline.canvas.getBoundingClientRect();
  const column = clientX === null ? -1 : Math.floor(((clientX - rect.left) / rect.width) * skyline.scene.width);
  const index = skyline.scene.barAt[column] ?? -1;
  if (index === skyline.hovered) {
    return;
  }
  skyline.hovered = index;
  const bar = skyline.scene.bars[index];
  const cssPerPixel = skyline.canvas.clientWidth / skyline.scene.width;
  skyline.onHover(
    bar ? { index, x: ((bar.left + bar.right) / 2) * cssPerPixel, y: bar.top * cssPerPixel } : null,
  );
  if (skyline.reduced) {
    render(skyline, performance.now());
  }
}

/** Start drawing on the canvas; returns a function that stops everything. */
export function startSkyline(
  canvas: HTMLCanvasElement,
  onHover: (hover: SkylineHover | null) => void,
): () => void {
  const context = canvas.getContext("2d");
  if (!context) {
    return () => undefined;
  }
  const scene = buildScene(canvas.clientWidth, canvas.clientHeight);
  const skyline: Skyline = {
    canvas,
    context,
    scene,
    palettes: readPalettes(canvas),
    image: context.createImageData(scene.width, scene.height),
    hovered: -1,
    visible: true,
    reduced: prefersReducedMotion(),
    startedAt: performance.now(),
    onHover,
  };
  return listen(skyline);
}

function listen(skyline: Skyline): () => void {
  const { canvas } = skyline;
  const resizeObserver = new ResizeObserver(() => resize(skyline));
  const visibility = new IntersectionObserver(([entry]) => {
    skyline.visible = entry.isIntersecting;
  });
  const darkMode = window.matchMedia("(prefers-color-scheme: dark)");
  const recolor = () => {
    skyline.palettes = readPalettes(canvas);
    render(skyline, performance.now());
  };
  const move = (event: PointerEvent) => pointAt(skyline, event.clientX);
  const leave = () => pointAt(skyline, null);
  resizeObserver.observe(canvas);
  visibility.observe(canvas);
  darkMode.addEventListener("change", recolor);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerdown", move);
  canvas.addEventListener("pointerleave", leave);
  let lastPaint = 0;
  let frame = requestAnimationFrame(function loop(now) {
    frame = requestAnimationFrame(loop);
    if (!skyline.reduced && skyline.visible && now - lastPaint >= FRAME_MS) {
      lastPaint = now;
      render(skyline, now);
    }
  });
  return () => {
    cancelAnimationFrame(frame);
    resizeObserver.disconnect();
    visibility.disconnect();
    darkMode.removeEventListener("change", recolor);
    canvas.removeEventListener("pointermove", move);
    canvas.removeEventListener("pointerdown", move);
    canvas.removeEventListener("pointerleave", leave);
  };
}
