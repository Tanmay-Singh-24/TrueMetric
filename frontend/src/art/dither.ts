// Helpers for the pixel art: ordered (Bayer) dithering, smooth noise and colour parsing.

// A 4×4 Bayer matrix. Comparing a shade against it turns smooth gradients into the
// regular pixel texture of old printers and screens.
const BAYER_4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];

/** The dither threshold, between 0 and 1, for one art pixel. */
export function bayer(x: number, y: number): number {
  return (BAYER_4[(y & 3) * 4 + (x & 3)] + 0.5) / 16;
}

/** A palette colour for a shade from 0 to 1, dithered between the two nearest colours. */
export function ditherPick(palette: number[], shade: number, x: number, y: number): number {
  const last = palette.length - 1;
  const scaled = clamp(shade, 0, 1) * last;
  const low = Math.floor(scaled);
  return palette[scaled - low > bayer(x, y) ? Math.min(low + 1, last) : low];
}

export function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function hash(x: number, y: number): number {
  let h = Math.imul(x, 374761393) + Math.imul(y, 668265263);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

/** Smooth random noise between 0 and 1. */
export function valueNoise(x: number, y: number): number {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const u = (x - xi) * (x - xi) * (3 - 2 * (x - xi));
  const v = (y - yi) * (y - yi) * (3 - 2 * (y - yi));
  const top = hash(xi, yi) + (hash(xi + 1, yi) - hash(xi, yi)) * u;
  const bottom = hash(xi, yi + 1) + (hash(xi + 1, yi + 1) - hash(xi, yi + 1)) * u;
  return top + (bottom - top) * v;
}

/** Noise at several scales added together: soft shapes with ragged edges, like clouds. */
export function fractalNoise(x: number, y: number, octaves: number): number {
  let total = 0;
  let amplitude = 0.5;
  let frequency = 1;
  let weight = 0;
  for (let octave = 0; octave < octaves; octave += 1) {
    total += valueNoise(x * frequency, y * frequency) * amplitude;
    weight += amplitude;
    amplitude *= 0.5;
    frequency *= 2;
  }
  return total / weight;
}

/** A "#rrggbb" colour as one ImageData pixel (bytes are red, green, blue, alpha in memory). */
export function toPixel(hex: string): number {
  const value = parseInt(hex.replace("#", ""), 16);
  const red = (value >> 16) & 255;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  // Uint32Array reads memory little-endian, so the first byte (red) is the lowest.
  return ((255 << 24) | (blue << 16) | (green << 8) | red) >>> 0;
}

/** Colours from CSS custom properties, so the art follows light and dark mode. */
export function readPalette(element: Element, names: string[]): number[] {
  const style = getComputedStyle(element);
  return names.map((name) => toPixel(style.getPropertyValue(name).trim()));
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
