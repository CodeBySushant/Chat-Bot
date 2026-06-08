// Token + active-tenant persistence. Tokens live in localStorage (Bearer auth);
// a lightweight cookie flag lets middleware do a first-paint redirect.
const ACCESS = "cb_access";
const REFRESH = "cb_refresh";
const COMPANY = "cb_company";
const CHATBOT = "cb_chatbot";

const isBrowser = () => typeof window !== "undefined";

export const tokenStore = {
  get access() { return isBrowser() ? localStorage.getItem(ACCESS) : null; },
  get refresh() { return isBrowser() ? localStorage.getItem(REFRESH) : null; },
  set(access: string, refresh: string) {
    if (!isBrowser()) return;
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
    document.cookie = `cb_authed=1; path=/; max-age=2592000; samesite=lax`;
  },
  clear() {
    if (!isBrowser()) return;
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    document.cookie = "cb_authed=; path=/; max-age=0";
  },
};

export const activeStore = {
  get company() { return isBrowser() ? localStorage.getItem(COMPANY) : null; },
  get chatbot() { return isBrowser() ? localStorage.getItem(CHATBOT) : null; },
  setCompany(id: string | null) {
    if (!isBrowser()) return;
    id ? localStorage.setItem(COMPANY, id) : localStorage.removeItem(COMPANY);
  },
  setChatbot(id: string | null) {
    if (!isBrowser()) return;
    id ? localStorage.setItem(CHATBOT, id) : localStorage.removeItem(CHATBOT);
  },
};
