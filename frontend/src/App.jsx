import { BrowserRouter, Routes, Route } from "react-router-dom";
import Overview from "./pages/Overview";
import RoomDetail from "./pages/RoomDetail";
import { DismissedEventsProvider } from "./context/DismissedEventsContext";

function App() {
  return (
    <DismissedEventsProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/room/:bedId" element={<RoomDetail />} />
        </Routes>
      </BrowserRouter>
    </DismissedEventsProvider>
  );
}

export default App;
