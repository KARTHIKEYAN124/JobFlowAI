void (async () => {
  const launch = new URLSearchParams(window.location.hash.slice(1));
  let token = launch.get("jobflow");
  if (!token) {
    const claimed = await new Promise(resolve => chrome.runtime.sendMessage({ type: "CLAIM_LAUNCH" }, resolve));
    token = claimed?.ok ? claimed.token : null;
  }
  if (!token) return;
  history.replaceState(null, "", `${location.pathname}${location.search}`);

  const panel = document.createElement("aside");
  panel.setAttribute("aria-live", "polite");
  Object.assign(panel.style, {
    position: "fixed", right: "20px", bottom: "20px", zIndex: "2147483647", width: "360px",
    maxWidth: "calc(100vw - 24px)", maxHeight: "min(720px, calc(100vh - 24px))", overflow: "hidden",
    borderRadius: "12px", background: "#111827", color: "#f9fafb",
    font: "14px/1.45 system-ui, sans-serif", boxShadow: "0 18px 50px rgba(0,0,0,.28)"
  });
  const panelHeader = document.createElement("div");
  Object.assign(panelHeader.style, {
    display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px",
    padding: "10px 12px 10px 16px", background: "#1f2937", fontWeight: "700", cursor: "grab",
    userSelect: "none", touchAction: "none", borderBottom: "1px solid #374151"
  });
  const panelTitle = document.createElement("span");
  panelTitle.textContent = "JobFlow 1.3.1 · Drag here";
  const panelControls = document.createElement("div");
  Object.assign(panelControls.style, { display: "flex", gap: "6px", flexShrink: "0" });
  const headerButton = (label, title) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.title = title;
    button.setAttribute("aria-label", title);
    Object.assign(button.style, {
      width: "30px", height: "30px", padding: "0", border: "1px solid #6b7280", borderRadius: "6px",
      background: "#374151", color: "#f9fafb", font: "700 16px/1 system-ui, sans-serif", cursor: "pointer"
    });
    panelControls.appendChild(button);
    return button;
  };
  const dockLeftButton = headerButton("←", "Move JobFlow panel to the left");
  const dockRightButton = headerButton("→", "Move JobFlow panel to the right");
  const minimizeButton = headerButton("−", "Minimize JobFlow panel");
  panelHeader.append(panelTitle, panelControls);
  const panelContent = document.createElement("div");
  Object.assign(panelContent.style, { padding: "18px", overflowY: "auto", maxHeight: "calc(min(720px, 100vh - 24px) - 48px)" });
  panel.append(panelHeader, panelContent);
  document.body.appendChild(panel);

  const clampPanelToViewport = () => {
    const rect = panel.getBoundingClientRect();
    const left = Math.min(Math.max(0, rect.left), Math.max(0, window.innerWidth - rect.width));
    const top = Math.min(Math.max(0, rect.top), Math.max(0, window.innerHeight - rect.height));
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
  };
  dockLeftButton.addEventListener("click", () => {
    panel.style.left = "12px";
    panel.style.right = "auto";
    clampPanelToViewport();
  });
  dockRightButton.addEventListener("click", () => {
    panel.style.left = "auto";
    panel.style.right = "12px";
  });
  minimizeButton.addEventListener("click", () => {
    const minimized = panelContent.style.display !== "none";
    panelContent.style.display = minimized ? "none" : "block";
    minimizeButton.textContent = minimized ? "+" : "−";
    minimizeButton.title = minimized ? "Restore JobFlow panel" : "Minimize JobFlow panel";
    minimizeButton.setAttribute("aria-label", minimizeButton.title);
    panelTitle.textContent = minimized ? "JobFlow 1.3.1" : "JobFlow 1.3.1 · Drag here";
    window.requestAnimationFrame(clampPanelToViewport);
  });
  panelHeader.addEventListener("pointerdown", event => {
    if (event.button !== 0 || event.target.closest("button")) return;
    const rect = panel.getBoundingClientRect();
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    panel.style.left = `${rect.left}px`;
    panel.style.top = `${rect.top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    panelHeader.style.cursor = "grabbing";
    panelHeader.setPointerCapture(event.pointerId);
    const move = moveEvent => {
      const maxLeft = Math.max(0, window.innerWidth - panel.offsetWidth);
      const maxTop = Math.max(0, window.innerHeight - panel.offsetHeight);
      panel.style.left = `${Math.min(Math.max(0, moveEvent.clientX - offsetX), maxLeft)}px`;
      panel.style.top = `${Math.min(Math.max(0, moveEvent.clientY - offsetY), maxTop)}px`;
    };
    const stop = () => {
      panelHeader.style.cursor = "grab";
      panelHeader.removeEventListener("pointermove", move);
      panelHeader.removeEventListener("pointerup", stop);
      panelHeader.removeEventListener("pointercancel", stop);
    };
    panelHeader.addEventListener("pointermove", move);
    panelHeader.addEventListener("pointerup", stop);
    panelHeader.addEventListener("pointercancel", stop);
  });
  window.addEventListener("resize", clampPanelToViewport);

  const addText = (parent, tag, value, style = {}) => {
    const element = document.createElement(tag);
    element.textContent = value;
    Object.assign(element.style, style);
    parent.appendChild(element);
    return element;
  };
  const showMessage = (title, message) => {
    panelContent.replaceChildren();
    addText(panelContent, "strong", title, { fontSize: "16px" });
    addText(panelContent, "p", message);
  };
  showMessage("JobFlow AI Companion", "Loading your reviewed application…");

  const sendMessage = (message, timeoutMs) => new Promise(resolve => {
    let settled = false;
    const timeout = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      resolve({ ok: false, error: "JobFlow took too long to respond. Check the API, then try Fill on job portal again." });
    }, timeoutMs);
    chrome.runtime.sendMessage(message, response => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      const runtimeError = chrome.runtime.lastError;
      resolve(runtimeError ? { ok: false, error: runtimeError.message } : response);
    });
  });

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
  const uploadFieldText = control => {
    const nearby = control.closest("label, [role=group], .field, .form-field")?.textContent || "";
    return `${labelText(control)} ${nearby.slice(0, 240)}`.replace(/\s+/g, " ").trim();
  };
  const resumeUploadInputs = () => Array.from(applicationRoot().querySelectorAll('input[type="file"]')).filter(control => {
    if (control.disabled) return false;
    const text = normalized(uploadFieldText(control));
    const isResume = /(^|\W)(resume|résumé|cv|curriculum vitae)(\W|$)/i.test(text);
    const isOtherDocument = /cover letter|transcript|portfolio|photo|headshot|certificate|supporting document/i.test(text);
    return isResume && !isOtherDocument;
  });
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

  const appendResumeImport = (parent, resumeState, onAttached) => {
    if (!resumeState.available) return;
    const section = document.createElement("section");
    Object.assign(section.style, { margin: "14px 0", padding: "12px", border: "1px solid #4b5563", borderRadius: "8px", background: "#182234" });
    addText(section, "strong", "Resume import", { display: "block" });
    const fields = resumeUploadInputs();
    if (!fields.length) {
      addText(section, "p", "No resume/CV upload field is visible on this portal page yet. Open the application form or its resume step, then scan again.", { color: "#d1d5db" });
      const scan = primaryButton("Scan portal again");
      scan.onclick = () => {
        if (!resumeUploadInputs().length) {
          scan.textContent = "No resume field found — scan again";
          return;
        }
        section.remove();
        appendResumeImport(parent, resumeState, onAttached);
      };
      section.appendChild(scan);
      parent.appendChild(section);
      return;
    }
    if (resumeState.attached) {
      addText(section, "p", `Tailored resume imported into ${resumeState.fieldLabel || "the portal resume field"}.`, { marginBottom: "0", color: "#86efac" });
      parent.appendChild(section);
      return;
    }
    addText(section, "p", "Choose the portal field, then import the tailored PDF stored by JobFlow.", { margin: "6px 0" });
    let selector = null;
    if (fields.length > 1) {
      selector = document.createElement("select");
      Object.assign(selector.style, { width: "100%", padding: "8px", borderRadius: "7px", background: "#fff", color: "#111827" });
      fields.forEach((field, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = uploadFieldText(field) || `Resume upload ${index + 1}`;
        selector.appendChild(option);
      });
      section.appendChild(selector);
    }
    const status = addText(section, "p", "", { marginBottom: "0", color: "#fbbf24" });
    const button = primaryButton("Import tailored resume");
    button.onclick = async () => {
      button.disabled = true;
      button.textContent = "Importing resume…";
      status.textContent = "Downloading your reviewed tailored PDF…";
      const resumeResponse = await resumeState.responsePromise;
      const field = fields[Number(selector?.value || 0)];
      if (!resumeResponse?.resumeBytes?.length || !field?.isConnected) {
        status.textContent = resumeResponse?.error || "The resume field changed or the tailored PDF could not be loaded. Reopen this application step and try again.";
        button.disabled = false;
        button.textContent = "Try resume import again";
        return;
      }
      try {
        const transfer = new DataTransfer();
        transfer.items.add(new File([new Uint8Array(resumeResponse.resumeBytes)], "jobflow-tailored-resume.pdf", { type: "application/pdf" }));
        field.files = transfer.files;
        emitChange(field);
        resumeState.attached = true;
        resumeState.fieldLabel = uploadFieldText(field) || "the portal resume field";
        status.style.color = "#86efac";
        status.textContent = `Imported into ${resumeState.fieldLabel}. Confirm the filename on the employer page.`;
        button.remove();
        selector?.setAttribute("disabled", "disabled");
        onAttached?.();
      } catch (error) {
        status.textContent = `This portal blocked automatic attachment: ${error?.message || "use its upload control to select the PDF manually"}.`;
        button.disabled = false;
        button.textContent = "Try resume import again";
      }
    };
    section.appendChild(button);
    parent.appendChild(section);
  };

  const renderSubmitReview = (filled, resumeState) => {
    panelContent.replaceChildren();
    addText(panelContent, "strong", "Application ready for your review", { fontSize: "16px" });
    const summary = addText(panelContent, "p", `${filled} fields filled${resumeState.attached ? " · tailored resume attached" : ""}. Review every answer on the employer page.`);
    appendResumeImport(panelContent, resumeState, () => {
      summary.textContent = `${filled} fields filled · tailored resume attached. Review every answer on the employer page.`;
    });
    const missing = requiredUnanswered();
    highlight(missing);
    if (missing.length) addText(panelContent, "p", `${missing.length} required fields still need an answer and are highlighted.`, { color: "#fbbf24" });
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
        addText(panelContent, "p", "No enabled submit button was found. Use the employer's submit control manually after review.", { color: "#fbbf24" });
        return;
      }
      chrome.runtime.sendMessage({ type: "RECORD_SUBMITTED", token });
      submit.click();
    };
    panelContent.appendChild(button);
  };
  const renderQuestions = (questions, filled, resumeState) => {
    panelContent.replaceChildren();
    addText(panelContent, "strong", `${questions.length} portal questions need your input`, { fontSize: "16px" });
    addText(panelContent, "p", "JobFlow will not guess employer-specific answers. Required questions are marked with *.");
    appendResumeImport(panelContent, resumeState);
    const entries = questions.map((control, index) => {
      const row = document.createElement("label");
      Object.assign(row.style, { display: "block", marginTop: "14px", fontSize: "12px", fontWeight: "600" });
      const fallback = `Application question ${index + 1}`;
      addText(row, "span", `${labelText(control) || fallback}${control.required ? " *" : ""}`);
      const editor = createEditor(control);
      row.appendChild(editor);
      panelContent.appendChild(row);
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
        addText(panelContent, "p", `${missing.length} required questions still need an answer.`, { color: "#fbbf24" });
        return;
      }
      renderSubmitReview(filled + newlyFilled, resumeState);
    };
    panelContent.appendChild(apply);
  };

  const slowNotice = window.setTimeout(() => {
    showMessage("JobFlow AI Companion", "The secure application package is still loading. A cold server start can take a few seconds…");
  }, 6000);
  const response = await sendMessage({ type: "FETCH_PACKAGE", token }, 30000);
  window.clearTimeout(slowNotice);
    if (!response?.ok) {
      showMessage("JobFlow could not start", response?.error || "Unknown error");
      return;
    }
    const resumePromise = response.applicationPackage.resume_available
      ? sendMessage({ type: "FETCH_RESUME", token }, 40000)
      : Promise.resolve({ ok: false, resumeBytes: null });
    const resumeState = {
      available: Boolean(response.applicationPackage.resume_available),
      responsePromise: resumePromise,
      attached: false,
      fieldLabel: ""
    };
    let attempts = 0;
    const fillWhenReady = async () => {
      if (supportedControls().length < 2 && attempts < 30) {
        attempts += 1;
        window.setTimeout(fillWhenReady, 300);
        return;
      }
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

      const questions = questionControls();
      highlight(questions.filter(control => control.required));
      if (questions.length) renderQuestions(questions, filled, resumeState);
      else renderSubmitReview(filled, resumeState);
    };
    window.setTimeout(fillWhenReady, 300);
})();
