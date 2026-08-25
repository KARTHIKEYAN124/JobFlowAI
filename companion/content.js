(() => {
  const launch = new URLSearchParams(window.location.hash.slice(1));
  const token = launch.get("jobflow");
  if (!token) return;
  history.replaceState(null, "", `${location.pathname}${location.search}`);

  const panel = document.createElement("aside");
  panel.setAttribute("aria-live", "polite");
  Object.assign(panel.style, {
    position: "fixed", right: "20px", bottom: "20px", zIndex: "2147483647", width: "360px",
    maxHeight: "min(720px, calc(100vh - 40px))", overflowY: "auto", padding: "18px",
    borderRadius: "12px", background: "#111827", color: "#f9fafb",
    font: "14px/1.45 system-ui, sans-serif", boxShadow: "0 18px 50px rgba(0,0,0,.28)"
  });
  document.body.appendChild(panel);

  const addText = (parent, tag, value, style = {}) => {
    const element = document.createElement(tag);
    element.textContent = value;
    Object.assign(element.style, style);
    parent.appendChild(element);
    return element;
  };
  const showMessage = (title, message) => {
    panel.replaceChildren();
    addText(panel, "strong", title, { fontSize: "16px" });
    addText(panel, "p", message);
  };
  showMessage("JobFlow AI Companion", "Loading your reviewed application…");

  const emitChange = control => {
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const normalized = value => String(value ?? "").trim().toLowerCase();
  const labelText = control => {
    const labels = control.labels ? Array.from(control.labels).map(label => label.textContent) : [];
    return [...labels, control.getAttribute("aria-label"), control.name, control.id, control.placeholder]
      .filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
  };
  const description = control => labelText(control).toLowerCase();
  const isVisible = control => !control.disabled && !control.readOnly && control.getClientRects().length > 0;
  const applicationRoot = () => document.querySelector("input[type=file]")?.closest("form")
    || Array.from(document.forms).sort((left, right) => right.querySelectorAll("input, textarea, select").length - left.querySelectorAll("input, textarea, select").length)[0]
    || document;
  const supportedControls = () => Array.from(applicationRoot().querySelectorAll("input, textarea, select")).filter(control => {
    const ignoredTypes = new Set(["hidden", "file", "submit", "button", "reset", "image"]);
    return isVisible(control) && !ignoredTypes.has(normalized(control.type));
  });

  const setControlValue = (control, value) => {
    if (!control || value === undefined || value === null || normalized(value) === "") return false;
    if (control instanceof HTMLSelectElement) {
      const wanted = normalized(value);
      const option = Array.from(control.options).find(item => normalized(item.value) === wanted || normalized(item.textContent) === wanted)
        || Array.from(control.options).find(item => normalized(item.textContent).includes(wanted));
      if (!option) return false;
      control.value = option.value;
      emitChange(control);
      return true;
    }
    if (control instanceof HTMLInputElement && control.type === "checkbox") {
      control.checked = ["yes", "true", "on", "1", "check"].includes(normalized(value));
      emitChange(control);
      return true;
    }
    if (control instanceof HTMLInputElement && control.type === "radio") {
      const group = control.name ? Array.from(applicationRoot().querySelectorAll(`input[type="radio"][name="${CSS.escape(control.name)}"]`)) : [control];
      const wanted = normalized(value);
      const choice = group.find(item => normalized(item.value) === wanted || normalized(labelText(item)).includes(wanted));
      if (!choice) return false;
      choice.checked = true;
      emitChange(choice);
      return true;
    }
    const prototype = control instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (setter) setter.call(control, String(value)); else control.value = String(value);
    emitChange(control);
    return true;
  };
  const fill = (keywords, value) => {
    const control = supportedControls().find(item => keywords.some(keyword => description(item).includes(keyword)));
    return setControlValue(control, value);
  };
  const hasAnswer = control => {
    if (control instanceof HTMLInputElement && control.type === "radio") {
      return Boolean(control.name && applicationRoot().querySelector(`input[type="radio"][name="${CSS.escape(control.name)}"]:checked`));
    }
    if (control instanceof HTMLInputElement && control.type === "checkbox") return control.checked;
    if (control instanceof HTMLSelectElement) {
      const choice = control.options[control.selectedIndex];
      if (!choice || normalized(choice.value) === "") return false;
      if (control.selectedIndex === 0 && /select|choose|please/i.test(choice.textContent || "")) return false;
    }
    return normalized(control.value) !== "";
  };
  const questionControls = () => {
    const seenRadioGroups = new Set();
    return supportedControls().filter(control => {
      if (control instanceof HTMLInputElement && control.type === "radio") {
        const key = control.name || control.id || control;
        if (seenRadioGroups.has(key)) return false;
        seenRadioGroups.add(key);
      }
      return !hasAnswer(control);
    });
  };
  const requiredUnanswered = () => Array.from(applicationRoot().querySelectorAll("input[required], textarea[required], select[required]"))
    .filter(isVisible)
    .filter(control => control instanceof HTMLInputElement && control.type === "file" ? !control.files?.length : !hasAnswer(control));
  const highlight = controls => controls.forEach(control => {
    control.style.outline = "2px solid #f59e0b";
    control.style.outlineOffset = "2px";
  });

  const questionOptions = control => {
    if (control instanceof HTMLSelectElement) return Array.from(control.options).filter(option => normalized(option.value) !== "").map(option => ({ value: option.value, label: option.textContent?.trim() || option.value }));
    if (control instanceof HTMLInputElement && control.type === "radio") {
      const group = control.name ? Array.from(applicationRoot().querySelectorAll(`input[type="radio"][name="${CSS.escape(control.name)}"]`)) : [control];
      return group.map(item => ({ value: item.value, label: labelText(item) || item.value }));
    }
    if (control instanceof HTMLInputElement && control.type === "checkbox") return [{ value: "check", label: "Yes" }, { value: "leave", label: "No" }];
    return [];
  };
  const createEditor = control => {
    const options = questionOptions(control);
    if (options.length) {
      const select = document.createElement("select");
      Object.assign(select.style, { width: "100%", marginTop: "6px", padding: "9px", borderRadius: "7px", border: "1px solid #4b5563", background: "#fff", color: "#111827" });
      const prompt = document.createElement("option");
      prompt.value = ""; prompt.textContent = "Select an answer";
      select.appendChild(prompt);
      options.forEach(option => {
        const item = document.createElement("option");
        item.value = option.value; item.textContent = option.label;
        select.appendChild(item);
      });
      return select;
    }
    const editor = control instanceof HTMLTextAreaElement ? document.createElement("textarea") : document.createElement("input");
    if (editor instanceof HTMLInputElement) editor.type = ["date", "number", "email", "tel", "url"].includes(control.type) ? control.type : "text";
    if (editor instanceof HTMLTextAreaElement) editor.rows = 3;
    Object.assign(editor.style, { width: "100%", boxSizing: "border-box", marginTop: "6px", padding: "9px", borderRadius: "7px", border: "1px solid #4b5563", background: "#fff", color: "#111827" });
    return editor;
  };
  const primaryButton = label => {
    const button = document.createElement("button");
    button.type = "button"; button.textContent = label;
    Object.assign(button.style, { width: "100%", border: "0", borderRadius: "8px", marginTop: "12px", padding: "11px", background: "#22c55e", color: "#052e16", fontWeight: "700", cursor: "pointer" });
    return button;
  };

  const renderSubmitReview = (filled, resumeAttached) => {
    panel.replaceChildren();
    addText(panel, "strong", "Application ready for your review", { fontSize: "16px" });
    addText(panel, "p", `${filled} fields filled${resumeAttached ? " · tailored resume attached" : ""}. Review every answer on the employer page.`);
    const missing = requiredUnanswered();
    highlight(missing);
    if (missing.length) addText(panel, "p", `${missing.length} required fields still need an answer and are highlighted.`, { color: "#fbbf24" });
    const button = primaryButton("Review complete — submit application");
    button.onclick = () => {
      const unanswered = requiredUnanswered();
      if (unanswered.length) {
        highlight(unanswered);
        unanswered[0].scrollIntoView({ behavior: "smooth", block: "center" });
        unanswered[0].focus();
        return;
      }
      if (!window.confirm("Submit this application to the employer now? JobFlow will record it as applied.")) return;
      const submit = Array.from(applicationRoot().querySelectorAll("button[type=submit], input[type=submit]")).find(control => isVisible(control));
      if (!submit) {
        addText(panel, "p", "No enabled submit button was found. Use the employer's submit control manually after review.", { color: "#fbbf24" });
        return;
      }
      chrome.runtime.sendMessage({ type: "RECORD_SUBMITTED", token });
      submit.click();
    };
    panel.appendChild(button);
  };
  const renderQuestions = (questions, filled, resumeAttached) => {
    panel.replaceChildren();
    addText(panel, "strong", `${questions.length} portal questions need your input`, { fontSize: "16px" });
    addText(panel, "p", "JobFlow will not guess employer-specific answers. Required questions are marked with *.");
    const entries = questions.map((control, index) => {
      const row = document.createElement("label");
      Object.assign(row.style, { display: "block", marginTop: "14px", fontSize: "12px", fontWeight: "600" });
      const fallback = `Application question ${index + 1}`;
      addText(row, "span", `${labelText(control) || fallback}${control.required ? " *" : ""}`);
      const editor = createEditor(control);
      row.appendChild(editor);
      panel.appendChild(row);
      return { control, editor };
    });
    const apply = primaryButton("Apply answers to portal");
    apply.onclick = () => {
      let newlyFilled = 0;
      entries.forEach(({ control, editor }) => {
        if (normalized(editor.value) && setControlValue(control, editor.value)) newlyFilled += 1;
      });
      const missing = requiredUnanswered();
      if (missing.length) {
        highlight(missing);
        addText(panel, "p", `${missing.length} required questions still need an answer.`, { color: "#fbbf24" });
        return;
      }
      renderSubmitReview(filled + newlyFilled, resumeAttached);
    };
    panel.appendChild(apply);
  };

  chrome.runtime.sendMessage({ type: "FETCH_PACKAGE", token }, response => {
    if (!response?.ok) {
      showMessage("JobFlow could not start", response?.error || "Unknown error");
      return;
    }
    window.setTimeout(() => {
      const data = response.applicationPackage;
      const candidate = data.candidate || {};
      const answers = data.answers || {};
      const names = String(candidate.full_name || "").trim().split(/\s+/);
      const firstName = names.shift() || "";
      const lastName = names.join(" ");
      let filled = 0;
      if (location.hostname === "jobs.lever.co" && setControlValue(document.querySelector('input[name="name"]'), candidate.full_name)) filled += 1;
      [
        [["first name", "first_name", "firstname"], firstName], [["last name", "last_name", "lastname", "surname"], lastName],
        [["full name", "candidate name"], candidate.full_name], [["email"], candidate.email], [["phone", "mobile"], candidate.phone],
        [["address", "city", "location"], candidate.address], [["linkedin"], candidate.linkedin], [["portfolio", "website", "github"], candidate.portfolio],
        [["salary", "compensation", "pay expectation"], answers.expected_salary], [["notice period"], answers.notice_period],
        [["start date", "available from"], answers.available_from], [["sponsorship", "visa"], answers.sponsorship],
        [["work authorization", "authorised to work", "authorized to work"], answers.work_authorization],
        [["motivation", "why do you", "why are you interested"], answers.motivation],
        [["relevant experience", "additional information", "cover letter"], answers.relevant_experience || data.documents?.cover_letter]
      ].forEach(([keywords, value]) => { if (fill(keywords, value)) filled += 1; });

      let resumeAttached = false;
      const fileInput = applicationRoot().querySelector("input[type=file]");
      if (fileInput && response.resumeBytes?.length) {
        try {
          const transfer = new DataTransfer();
          transfer.items.add(new File([new Uint8Array(response.resumeBytes)], "jobflow-tailored-resume.pdf", { type: "application/pdf" }));
          fileInput.files = transfer.files;
          fileInput.dispatchEvent(new Event("change", { bubbles: true }));
          resumeAttached = true;
        } catch { resumeAttached = false; }
      }
      const questions = questionControls();
      highlight(questions.filter(control => control.required));
      if (questions.length) renderQuestions(questions, filled, resumeAttached);
      else renderSubmitReview(filled, resumeAttached);
    }, 500);
  });
})();
