const API_ORIGIN = "https://jobflow-ai-delta.vercel.app";
const API_BASE = `${API_ORIGIN}/backend/api/v1`;

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
    fetch(`${API_BASE}/portal-sessions/${encodeURIComponent(message.token)}`)
      .then(async response => {
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Could not load the JobFlow application package");
        const applicationPackage = await response.json();
        let resumeBytes = null;
        if (applicationPackage.resume_url) {
          const resume = await fetch(`${API_ORIGIN}/backend${applicationPackage.resume_url}`);
          if (resume.ok) resumeBytes = Array.from(new Uint8Array(await resume.arrayBuffer()));
        }
        sendResponse({ ok: true, applicationPackage, resumeBytes });
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
