// Light and dark mode. The theme lives on <html data-theme="...">: the CSS colours and the
// canvas drawings both follow that one attribute. A script in index.html sets it before
// the page first paints, so there is no flash of the wrong theme.

import { prefersReducedMotion } from "./art/dither";

export type Theme = "light" | "dark";

const STORAGE_KEY = "truemetric-theme";

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** The theme the visitor chose with the switch, if any. */
export function savedTheme(): Theme | null {
  // Storage can be blocked (private windows, strict settings); then nothing is saved.
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Not saved: the switch still works for this visit.
  }
}

type DocumentWithTransitions = Document & {
  startViewTransition?: (update: () => void) => unknown;
};

/**
 * Apply a theme. Where the browser supports view transitions, the new theme is revealed
 * in a circle growing from (x, y), the switch's position on screen.
 */
export function applyTheme(theme: Theme, x: number, y: number): void {
  const root = document.documentElement;
  const update = () => {
    root.dataset.theme = theme;
  };
  const transitionDocument = document as DocumentWithTransitions;
  if (!transitionDocument.startViewTransition || prefersReducedMotion()) {
    update();
    return;
  }
  root.style.setProperty("--reveal-x", `${x}px`);
  root.style.setProperty("--reveal-y", `${y}px`);
  transitionDocument.startViewTransition(update);
}

/** Switch between light and dark, remember the choice, reveal it from (x, y). */
export function toggleTheme(x: number, y: number): void {
  const next: Theme = currentTheme() === "dark" ? "light" : "dark";
  saveTheme(next);
  applyTheme(next, x, y);
}
