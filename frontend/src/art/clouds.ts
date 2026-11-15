// The hero sky: dithered clouds that gather around the search bar, a sun by day or a
// crescent moon and twinkling stars by night, and a wind that follows the pointer and
// clears a gap in the clouds. Sky pixels are transparent, so the page colour shows through.

import {
  ditherPick,
  fractalNoise,
  hash,
  isDarkTheme,
  onThemeChange,
  prefersReducedMotion,
  readPalette,
  smoothstep,
} from "./dither";

const FRAME_MS = 1000 / 30;
const DRIFT_SPEED = 0.00006; // noise units per millisecond
const TRANSPARENT = 0;

interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

interface Sky {
  canvas: HTMLCanvasElement;
  area: HTMLElement; // the element whose pointer moves make wind
  context: CanvasRenderingContext2D;
  image: ImageData;
  width: number;
  height: number;
  cell: number; // screen pixels per art pixel
  night: boolean;
  clouds: number[];
  body: number[]; // sun or moon colours
  star: number;
  bar: Box; // the search bar, in art pixels
  sun: { x: number; y: number; r: number };
  wind: { x: number; y: number; targetX: number; targetY: number; strength: number; target: number };
  reduced: boolean;
  visible: boolean;
  startedAt: number;
}

function recolor(sky: Sky): void {
  sky.night = isDarkTheme();
  sky.clouds = [TRANSPARENT, ...readPalette(sky.canvas, ["--art-cloud-1", "--art-cloud-2", "--art-cloud-3"])];
  const body = sky.night ? ["--art-moon-1", "--art-moon-2", "--art-moon-3"] : ["--art-sun-1", "--art-sun-2", "--art-sun-3"];
  sky.body = [TRANSPARENT, ...readPalette(sky.canvas, body)];
  [sky.star] = readPalette(sky.canvas, ["--art-star"]);
}

function resize(sky: Sky): void {
  const cssWidth = sky.canvas.clientWidth;
  sky.cell = cssWidth < 600 ? 3 : 4;
  sky.width = Math.max(1, Math.ceil(cssWidth / sky.cell));
  sky.height = Math.max(1, Math.ceil(sky.canvas.clientHeight / sky.cell));
  sky.canvas.width = sky.width;
  sky.canvas.height = sky.height;
  sky.image = sky.context.createImageData(sky.width, sky.height);
  const narrow = cssWidth < 600;
  // Up and to the right, clear of the centred headline.
  sky.sun = {
    x: Math.round(sky.width * (narrow ? 0.88 : 0.91)),
    y: Math.round(sky.height * (narrow ? 0.06 : 0.14)),
    r: Math.max(5, Math.min(14, Math.round(sky.height * 0.07))),
  };
}

/** Where the search bar is, in art pixels, measured from the page each frame. */
function measureBar(sky: Sky): void {
  const box = sky.area.querySelector(".ask-box")?.getBoundingClientRect();
  const canvasBox = sky.canvas.getBoundingClientRect();
  if (!box || canvasBox.width === 0) {
    return;
  }
  const scale = sky.width / canvasBox.width;
  sky.bar = {
    left: (box.left - canvasBox.left) * scale,
    top: (box.top - canvasBox.top) * scale,
    right: (box.right - canvasBox.left) * scale,
    bottom: (box.bottom - canvasBox.top) * scale,
  };
}

function windAt(sky: Sky, x: number, y: number): number {
  const { wind } = sky;
  if (wind.strength < 0.01) {
    return 0;
  }
  const dx = x - wind.x;
  const dy = (y - wind.y) * 1.6; // the gap is wider than it is tall
  return wind.strength * 1.3 * Math.exp(-(dx * dx + dy * dy) / 300);
}

function cloudShade(sky: Sky, x: number, y: number, drift: number): number {
  const { bar, height } = sky;
  // Clouds gather in a bank around the search bar, a band across its height, and a few
  // wisps near the top of the sky.
  const dx = Math.max(bar.left - x, 0, x - bar.right);
  const dy = Math.max(bar.top - y, 0, y - bar.bottom);
  const nearBar = Math.exp(-(dx * dx + dy * dy * 2) / 900);
  const centre = (bar.top + bar.bottom) / 2;
  const band = Math.exp(-(((y - centre) / (height * 0.2)) ** 2)) * 0.7;
  const wisps = Math.exp(-(((y - height * 0.12) / (height * 0.1)) ** 2)) * 0.4;
  const weight = Math.max(nearBar, band, wisps);
  if (weight < 0.03) {
    return 0;
  }
  const density = fractalNoise(x * 0.028 - drift, y * 0.075 + drift * 0.2, 3);
  return smoothstep(0.38, 0.74, density) * weight * 1.4 - windAt(sky, x, y);
}

function bodyShade(sky: Sky, x: number, y: number): number {
  const dx = x - sky.sun.x;
  const dy = y - sky.sun.y;
  const distance = Math.hypot(dx, dy) / sky.sun.r;
  if (sky.night) {
    // A crescent: the moon's disc minus a second disc shifted up and to the right.
    const bite = Math.hypot(dx - sky.sun.r * 0.42, dy + sky.sun.r * 0.15) / sky.sun.r;
    return distance <= 0.8 && bite > 0.62 ? 0.95 - distance * 0.4 : 0;
  }
  // A bright disc with a dithered glow around it.
  return distance <= 0.7 ? 1 - distance * 0.3 : Math.max(0, (1.9 - distance) * 0.38);
}

function starAt(sky: Sky, x: number, y: number, time: number): boolean {
  if (!sky.night || y > sky.height * 0.75 || hash(x, y) < 0.993) {
    return false;
  }
  return Math.sin(time * 0.004 + hash(y, x) * 40) > 0.2;
}

function paint(sky: Sky, now: number): void {
  const time = sky.reduced ? 0 : now - sky.startedAt;
  const drift = time * DRIFT_SPEED;
  const pixels = new Uint32Array(sky.image.data.buffer);
  measureBar(sky);
  for (let y = 0; y < sky.height; y += 1) {
    for (let x = 0; x < sky.width; x += 1) {
      let color = starAt(sky, x, y, time) ? sky.star : TRANSPARENT;
      const body = bodyShade(sky, x, y);
      if (body > 0) {
        color = ditherPick(sky.body, body, x, y) || color;
      }
      const cloud = cloudShade(sky, x, y, drift);
      if (cloud > 0) {
        color = ditherPick(sky.clouds, cloud, x, y) || color;
      }
      pixels[y * sky.width + x] = color;
    }
  }
  sky.context.putImageData(sky.image, 0, 0);
}

/** Ease the wind towards the pointer, so the gap trails behind it like real air. */
function stepWind(sky: Sky): void {
  const { wind } = sky;
  wind.x += (wind.targetX - wind.x) * 0.18;
  wind.y += (wind.targetY - wind.y) * 0.18;
  wind.strength += (wind.target - wind.strength) * 0.08;
}

function artPoint(sky: Sky, event: MouseEvent): { x: number; y: number } {
  const box = sky.canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - box.left) / box.width) * sky.width,
    y: ((event.clientY - box.top) / box.height) * sky.height,
  };
}

function overSun(sky: Sky, point: { x: number; y: number }): boolean {
  return Math.hypot(point.x - sky.sun.x, point.y - sky.sun.y) < sky.sun.r * 1.3;
}

/** Start the sky; onSunClick gets the click position when the sun or moon is clicked. */
export function startClouds(
  canvas: HTMLCanvasElement,
  area: HTMLElement,
  onSunClick: (x: number, y: number) => void,
): () => void {
  const context = canvas.getContext("2d");
  if (!context) {
    return () => undefined;
  }
  const sky: Sky = {
    canvas,
    area,
    context,
    image: context.createImageData(1, 1),
    width: 1,
    height: 1,
    cell: 4,
    night: false,
    clouds: [],
    body: [],
    star: TRANSPARENT,
    bar: { left: 0, top: 0, right: 0, bottom: 0 },
    sun: { x: 0, y: 0, r: 8 },
    wind: { x: 0, y: 0, targetX: 0, targetY: 0, strength: 0, target: 0 },
    reduced: prefersReducedMotion(),
    visible: true,
    startedAt: performance.now(),
  };
  recolor(sky);
  resize(sky);
  return listen(sky, onSunClick);
}

function listen(sky: Sky, onSunClick: (x: number, y: number) => void): () => void {
  const { area, canvas } = sky;
  const move = (event: PointerEvent) => {
    const point = artPoint(sky, event);
    sky.wind.targetX = point.x;
    sky.wind.targetY = point.y;
    sky.wind.target = sky.reduced ? 0 : 1;
    area.classList.toggle("is-over-sun", overSun(sky, point));
  };
  const leave = () => {
    sky.wind.target = 0;
    area.classList.remove("is-over-sun");
  };
  const click = (event: MouseEvent) => {
    if (overSun(sky, artPoint(sky, event))) {
      onSunClick(event.clientX, event.clientY);
    }
  };
  const resizeObserver = new ResizeObserver(() => {
    resize(sky);
    paint(sky, performance.now());
  });
  const visibility = new IntersectionObserver(([entry]) => {
    sky.visible = entry.isIntersecting;
  });
  const stopWatchingTheme = onThemeChange(() => {
    recolor(sky);
    paint(sky, performance.now());
  });
  area.addEventListener("pointermove", move);
  area.addEventListener("pointerleave", leave);
  area.addEventListener("click", click);
  resizeObserver.observe(canvas);
  visibility.observe(canvas);
  let lastPaint = 0;
  let frame = requestAnimationFrame(function loop(now) {
    frame = requestAnimationFrame(loop);
    if (!sky.visible || (sky.reduced && lastPaint > 0) || now - lastPaint < FRAME_MS) {
      return;
    }
    lastPaint = now;
    stepWind(sky);
    paint(sky, now);
  });
  return () => {
    cancelAnimationFrame(frame);
    resizeObserver.disconnect();
    visibility.disconnect();
    stopWatchingTheme();
    area.removeEventListener("pointermove", move);
    area.removeEventListener("pointerleave", leave);
    area.removeEventListener("click", click);
  };
}
