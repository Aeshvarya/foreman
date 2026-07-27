import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import ChatWidget from "./components/ChatWidget";
import { TourProvider } from "./features/tour/TourProvider";
import { TourOverlay } from "./features/tour/TourOverlay";
import { clearStaleScene } from "./lib/scene";

// A reload/hard-nav skips Cascade's unmount cleanup but keeps sessionStorage,
// so a stale scene could make Ask Foreman answer in "explain the screen" mode
// forever instead of querying the graph. Clear it before anything mounts.
clearStaleScene();

export default function App() {
  return (
    <TourProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/dashboard/:tool" element={<Dashboard />} />
      </Routes>
      <ChatWidget />
      <TourOverlay />
    </TourProvider>
  );
}
