import { type MouseEvent, useEffect, useState } from "react";

import { onThemeChange } from "../art/dither";
import { applyTheme, currentTheme, savedTheme, systemTheme, toggleTheme } from "../theme";
import { MOON, PixelIcon, SUN } from "./PixelIcon";

export function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme);

  useEffect(() => {
    // The sun in the sky can switch the theme too, so follow the page, not just clicks here.
    const stopWatching = onThemeChange(() => setTheme(currentTheme()));
    // Until the visitor chooses, follow the system setting if it changes.
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const followSystem = () => {
      if (!savedTheme()) {
        applyTheme(systemTheme(), 0, 0);
      }
    };
    media.addEventListener("change", followSystem);
    return () => {
      stopWatching();
      media.removeEventListener("change", followSystem);
    };
  }, []);

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    // The new theme is revealed in a circle growing from the middle of the switch.
    const box = event.currentTarget.getBoundingClientRect();
    toggleTheme(box.left + box.width / 2, box.top + box.height / 2);
  }

  const dark = theme === "dark";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label="Dark mode"
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      className={dark ? "theme-toggle is-dark" : "theme-toggle"}
      onClick={handleClick}
    >
      <span className="theme-knob">
        <PixelIcon rows={dark ? MOON : SUN} size={14} />
      </span>
    </button>
  );
}
