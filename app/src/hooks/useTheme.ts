import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark";
const KEY = "echlon-theme";

/** Dark mode is native to the design system, so the app defaults to dark and
 *  persists the user's choice. Applies the `.dark` class on <html>. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(KEY);
    return stored === "light" || stored === "dark" ? stored : "dark";
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }, []);

  return { theme, toggle };
}
