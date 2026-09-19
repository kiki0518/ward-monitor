// 「誤觸」清單：純前端、不寫回後端（見 API_CONTRACT.md「誤觸」一節）
// 放在 Context 而不是單一頁面的 state，這樣 RoomDetail 標記的誤觸，
// 離開頁面回到 Overview 後，異常警示/床位卡顏色也能跟著濾掉

import { createContext, useCallback, useContext, useState } from "react";

const DismissedEventsContext = createContext(null);

export function DismissedEventsProvider({ children }) {
  const [dismissedIds, setDismissedIds] = useState(() => new Set());

  const dismissEvent = useCallback((eventId) => {
    setDismissedIds((prev) => new Set(prev).add(eventId));
  }, []);

  return (
    <DismissedEventsContext.Provider value={{ dismissedIds, dismissEvent }}>
      {children}
    </DismissedEventsContext.Provider>
  );
}

export function useDismissedEvents() {
  const ctx = useContext(DismissedEventsContext);
  if (!ctx) throw new Error("useDismissedEvents must be used within DismissedEventsProvider");
  return ctx;
}
