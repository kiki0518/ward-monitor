import { BrowserRouter, Routes, Route } from "react-router-dom";
import Overview from "./pages/Overview";
import RoomDetail from "./pages/RoomDetail";
import NurseView from "./pages/NurseView";
import { DismissedEventsProvider } from "./context/DismissedEventsContext";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/room/:bedId" element={<RoomDetail />} />
        <Route path="/nurse" element={<NurseView />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
