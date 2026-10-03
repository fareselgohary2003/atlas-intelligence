// The session JWT is httpOnly (invisible to JS). Only the CSRF token cookie is readable and must be echoed on unsafe requests.
export const SAFE = new Set(["GET", "HEAD", "OPTIONS"]);
export const readCookie = (name, cookieString = "") => {
  for (const part of cookieString.split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return decodeURIComponent(part.slice(i + 1).trim());
  }
  return null;
};
export const csrfHeaders = (method, cookieString = "", cookieName = "atlas_csrf") => {
  if (SAFE.has(String(method).toUpperCase())) return {};
  const t = readCookie(cookieName, cookieString);
  return t ? { "X-CSRF-Token": t } : {};
};
