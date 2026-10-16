// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import React from "react";
import ReactDOM from "react-dom/client";
import { getCurrentWindow } from "@tauri-apps/api/window";
import App from "./App";
import { HudOverlay } from "./hud";
import "./styles.css";

// One bundle serves both windows; the overlay window renders only alert cards.
const isHud = getCurrentWindow().label === "hud";
document.documentElement.dataset.window = isHud ? "hud" : "main";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isHud ? <HudOverlay /> : <App />}
  </React.StrictMode>,
);
