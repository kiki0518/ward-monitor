import { BrowserRouter, Routes, Route } from "react-router-dom";
import Overview from "./pages/Overview";
import RoomDetail from "./pages/RoomDetail";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/room/:bedId" element={<RoomDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
