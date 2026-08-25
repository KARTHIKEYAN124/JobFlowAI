(() => {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const targetValue = params.get("target");
  if (!targetValue) return;
  let target;
  try { target = new URL(targetValue); }
  catch { return; }
  const token = new URLSearchParams(target.hash.slice(1)).get("jobflow");
  if (!token || target.protocol !== "https:") return;
  target.hash = "";
  chrome.runtime.sendMessage({ type: "STORE_LAUNCH", token }, response => {
    if (response?.ok) window.location.replace(target.toString());
  });
})();
