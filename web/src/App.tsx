import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import ChatWidget from "./components/ChatWidget";
import { TourProvider } from "./features/tour/TourProvider";
import { TourOverlay } from "./features/tour/TourOverlay";

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
