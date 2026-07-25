import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

// Self-hosted fonts (no CDN): Bricolage Grotesque (display, characterful),
// Hanken Grotesk (UI/body, clean + warm), JetBrains Mono (data).
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/hanken-grotesk";
import "@fontsource-variable/jetbrains-mono";

import "./index.css";
import App from "./App";

// NOTE: intentionally not wrapped in React.StrictMode — its dev-only double
// mount makes React Flow measure a 0-size container and render blank until a
// resize/refresh. StrictMode has no effect on production builds anyway.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
);
