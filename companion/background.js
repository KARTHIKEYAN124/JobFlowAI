const API_ORIGIN = "https://jobflow-ai-delta.vercel.app";
const API_BASE = `${API_ORIGIN}/backend/api/v1`;

const fetchWithTimeout = async (url, options = {}, timeoutMs = 25000) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("JobFlow took too long to respond. Please try again.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "STORE_LAUNCH") {
    const tabId = _sender.tab?.id;
    if (tabId === undefined || !message.token) {
      sendResponse({ ok: false });
      return false;
    }
    chrome.storage.session.set({ [`launch_${tabId}`]: { token: message.token, expiresAt: Date.now() + 20 * 60 * 1000 } })
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "CLAIM_LAUNCH") {
    const tabId = _sender.tab?.id;
    if (tabId === undefined) {
      sendResponse({ ok: false });
      return false;
    }
    const key = `launch_${tabId}`;
    chrome.storage.session.get(key).then(result => {
      const launch = result[key];
      return chrome.storage.session.remove(key).then(() => sendResponse({ ok: Boolean(launch?.token && launch.expiresAt > Date.now()), token: launch?.expiresAt > Date.now() ? launch.token : null }));
    }).catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "FETCH_PACKAGE") {
    fetchWithTimeout(`${API_BASE}/portal-sessions/${encodeURIComponent(message.token)}`)
      .then(async response => {
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Could not load the JobFlow application package");
        const applicationPackage = await response.json();
        sendResponse({ ok: true, applicationPackage });
      })
      .catch(error => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "FETCH_RESUME") {
    fetchWithTimeout(`${API_BASE}/portal-sessions/${encodeURIComponent(message.token)}/resume`, {}, 35000)
      .then(async response => {
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Could not prepare the tailored resume");
        sendResponse({ ok: true, resumeBytes: Array.from(new Uint8Array(await response.arrayBuffer())) });
      })
      .catch(error => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "RECORD_SUBMITTED") {
    fetch(`${API_BASE}/portal-sessions/${encodeURIComponent(message.token)}/submitted`, { method: "POST" })
      .then(response => sendResponse({ ok: response.ok }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  return false;
});
