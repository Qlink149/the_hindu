import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "darkMode";

const ThemeContext = createContext({
  darkMode: false,
  toggleDarkMode: () => {},
  setDarkMode: () => {},
});

export function readStoredDarkMode() {
  return false;
}

export function applyThemeClass(darkMode) {
  const root = document.documentElement;
  root.classList.toggle("dark-mode", Boolean(darkMode));
  root.classList.toggle("light-mode", !darkMode);
  root.classList.add("executive-shell");
  const body = document.body;
  if (body) {
    body.classList.toggle("dark-mode", Boolean(darkMode));
    body.classList.toggle("light-mode", !darkMode);
    body.classList.add("executive-shell");
  }
}

export function ThemeProvider({ children }) {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(false));
    } catch {
      /* ignore quota / private mode */
    }
    applyThemeClass(false);
  }, [darkMode]);

  const toggleDarkMode = useCallback(() => {
    setDarkMode(false);
  }, []);

  const value = useMemo(
    () => ({ darkMode: false, setDarkMode: () => {}, toggleDarkMode }),
    [toggleDarkMode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}

export default ThemeContext;
