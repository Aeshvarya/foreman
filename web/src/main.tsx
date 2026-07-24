import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

// Self-hosted fonts (no CDN): Geist (UI), Geist Mono (data), Space Grotesk (display).
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/space-grotesk/700.css";

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
