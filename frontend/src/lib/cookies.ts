export const setAuthCookie = (token: string) => {
  const payload = token;

  let cookieString = `session_token=${token}; path=/; samesite=strict`;

  if (window.location.protocol === "https:") {
    cookieString += "; secure";
  }

  document.cookie = cookieString;
};

export const getAuthCookie = (): string => {
  const cookies = document.cookie.split(";");

  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "session_token") {
      return value || "";
    }
  }

  return "";
};

export const removeAuthCookie = (): void => {
  let cookieString =
    "session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; samesite=strict";

  if (window.location.protocol === "https:") {
    cookieString += "; secure";
  }

  document.cookie = cookieString;
};

export const isAuthenticated = (): boolean => {
  const token = getAuthCookie();

  if (!token) return false;

  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const currentTime = Math.floor(Date.now() / 1000);

    return payload.exp > currentTime;
  } catch (error) {
    console.error("Error validating authentication token:", error);
    return false;
  }
};
