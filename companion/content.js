(() => {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  const token = hash.get("jobflow");
  if (!token) return;
  history.replaceState(null, "", `${location.pathname}${location.search}`);

  const panel = document.createElement("aside");
  panel.setAttribute("aria-live", "polite");
  Object.assign(panel.style, {
    position: "fixed", right: "20px", bottom: "20px", zIndex: "2147483647", width: "320px",
    padding: "18px", borderRadius: "12px", background: "#111827", color: "#f9fafb",
    font: "14px/1.45 system-ui, sans-serif", boxShadow: "0 18px 50px rgba(0,0,0,.28)"
  });
  panel.innerHTML = "<strong style='font-size:16px'>JobFlow AI Companion</strong><p>Loading your reviewed application…</p>";
  document.body.appendChild(panel);

  const setValue = (control, value) => {
    if (!control || value === undefined || value === null || String(value).trim() === "") return false;
    const prototype = control instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : control instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (setter) setter.call(control, String(value)); else control.value = String(value);
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };

  const controls = () => Array.from(document.querySelectorAll("input:not([type=hidden]):not([type=file]), textarea, select"));
  const description = control => {
    const explicit = control.labels ? Array.from(control.labels).map(label => label.textContent).join(" ") : "";
    return [explicit, control.getAttribute("aria-label"), control.name, control.id, control.placeholder].filter(Boolean).join(" ").toLowerCase();
  };
  const fill = (keywords, value) => {
    const control = controls().find(item => keywords.some(keyword => description(item).includes(keyword)));
    return setValue(control, value);
  };

  chrome.runtime.sendMessage({ type: "FETCH_PACKAGE", token }, response => {
    if (!response?.ok) {
      panel.innerHTML = `<strong>JobFlow could not start</strong><p>${response?.error || "Unknown error"}</p>`;
      return;
    }
    const data = response.applicationPackage;
    const candidate = data.candidate || {};
    const answers = data.answers || {};
    const names = String(candidate.full_name || "").trim().split(/\s+/);
    const firstName = names.shift() || "";
    const lastName = names.join(" ");
    let filled = 0;
    if (location.hostname === "jobs.lever.co" && setValue(document.querySelector('input[name="name"]'), candidate.full_name)) filled += 1;
    [
      [["first name", "first_name", "firstname"], firstName],
      [["last name", "last_name", "lastname", "surname"], lastName],
      [["full name", "candidate name"], candidate.full_name],
      [["email"], candidate.email], [["phone", "mobile"], candidate.phone],
      [["address", "city", "location"], candidate.address],
      [["linkedin"], candidate.linkedin], [["portfolio", "website", "github"], candidate.portfolio],
      [["salary", "compensation", "pay expectation"], answers.expected_salary],
      [["notice period"], answers.notice_period], [["start date", "available from"], answers.available_from],
      [["sponsorship", "visa"], answers.sponsorship], [["work authorization", "authorised to work", "authorized to work"], answers.work_authorization],
      [["motivation", "why do you", "why are you interested"], answers.motivation],
      [["relevant experience", "additional information", "cover letter"], answers.relevant_experience || data.documents?.cover_letter]
    ].forEach(([keywords, value]) => { if (fill(keywords, value)) filled += 1; });

    let resumeAttached = false;
    const fileInput = document.querySelector("input[type=file]");
    if (fileInput && response.resumeBytes?.length) {
      try {
        const transfer = new DataTransfer();
        transfer.items.add(new File([new Uint8Array(response.resumeBytes)], "jobflow-tailored-resume.pdf", { type: "application/pdf" }));
        fileInput.files = transfer.files;
        fileInput.dispatchEvent(new Event("change", { bubbles: true }));
        resumeAttached = true;
      } catch { resumeAttached = false; }
    }

    const missing = Array.from(document.querySelectorAll("input[required], textarea[required], select[required]")).filter(control => !control.value && control.type !== "hidden");
    missing.forEach(control => { control.style.outline = "2px solid #f59e0b"; control.style.outlineOffset = "2px"; });
    panel.innerHTML = `<strong style="font-size:16px">Application filled for review</strong><p>${filled} fields filled${resumeAttached ? " · tailored resume attached" : ""}.</p><p>${missing.length ? `${missing.length} required fields still need your answer and are highlighted.` : "Review every answer before continuing."}</p>`;
    const button = document.createElement("button");
    button.textContent = "Review complete — submit application";
    Object.assign(button.style, { width: "100%", border: "0", borderRadius: "8px", padding: "11px", background: "#22c55e", color: "#052e16", fontWeight: "700", cursor: "pointer" });
    button.onclick = () => {
      const unanswered = Array.from(document.querySelectorAll("input[required], textarea[required], select[required]")).filter(control => !control.value && control.type !== "hidden");
      if (unanswered.length) { unanswered[0].scrollIntoView({ behavior: "smooth", block: "center" }); unanswered[0].focus(); return; }
      if (!window.confirm("Submit this application to the employer now? JobFlow will record it as applied.")) return;
      const submit = Array.from(document.querySelectorAll("button[type=submit], input[type=submit]")).find(control => !control.disabled);
      if (!submit) { panel.insertAdjacentHTML("beforeend", "<p>No enabled submit button was found. Submit manually after review.</p>"); return; }
      chrome.runtime.sendMessage({ type: "RECORD_SUBMITTED", token });
      submit.click();
    };
    panel.appendChild(button);
  });
})();
