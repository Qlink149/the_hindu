import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "darkMode";

const ThemeContext = createContext({
  darkMode: true,
  toggleDarkMode: () => {},
  setDarkMode: () => {},
});

export function readStoredDarkMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved !== null ? JSON.parse(saved) : true;
  } catch {
    return true;
  }
}

export function applyThemeClass(darkMode) {
  const root = document.documentElement;
  root.classList.toggle("dark-mode", darkMode);
  root.classList.toggle("light-mode", !darkMode);
}

export function ThemeProvider({ children }) {
  const [darkMode, setDarkMode] = useState(readStoredDarkMode);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(darkMode));
    } catch {
      /* ignore quota / private mode */
    }
    applyThemeClass(darkMode);
  }, [darkMode]);

  const toggleDarkMode = useCallback(() => {
    setDarkMode((prev) => !prev);
  }, []);

  const value = useMemo(
    () => ({ darkMode, setDarkMode, toggleDarkMode }),
    [darkMode, toggleDarkMode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}

export default ThemeContext;
