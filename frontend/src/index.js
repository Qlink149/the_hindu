import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { applyThemeClass, readStoredDarkMode } from "@/context/ThemeContext";

applyThemeClass(readStoredDarkMode());

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
