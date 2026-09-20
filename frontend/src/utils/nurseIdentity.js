// 護理師身分：不做帳號密碼，單純讓護理師在自己的裝置上選一次姓名，
// 存在該裝置的 localStorage 記住，之後開網頁就直接是「我的病人」畫面。
// 換人用同一台裝置時按「切換護理師」清掉即可，不需要登出流程。

const STORAGE_KEY = "wardMonitor.nurseName";

export function getStoredNurse() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredNurse(name) {
  try {
    localStorage.setItem(STORAGE_KEY, name);
  } catch {
    // localStorage 被封鎖（例如私密瀏覽）時就當作沒存成功，每次重整都要重選
  }
}

export function clearStoredNurse() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 同上，沒有 localStorage 可清也無妨
  }
}
