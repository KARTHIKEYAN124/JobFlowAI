# JobFlow AI Companion

The companion runs in the candidate's own Chrome/Edge browser. It supports public Greenhouse, Lever, Ashby, and SmartRecruiters application pages, fills reviewed JobFlow details, and builds a review panel from every visible unanswered employer field. Drag the panel by its header, use **←/→** to dock it, or use **−/+** to minimize and restore it. When the real portal form exposes a field labelled resume, résumé, CV, or curriculum vitae, the panel shows **Import tailored resume** and lets you choose the correct field before attaching the verified PDF. It uses the portal's real dropdown/radio choices, refuses to guess unknown answers, highlights missing required fields, and waits for an explicit confirmation before clicking the portal's submit button.

## Install locally

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `companion` directory.
4. If it was already installed, click **Reload** and confirm version **1.3.2**.
5. In JobFlow, prepare and review an application, then select **Fill on job portal**.

JobFlow first opens a bridge page so the extension can preserve the 20-minute launch token across employer redirects. If the extension is missing or stale, that page shows reload instructions instead of failing silently. Answers entered in the companion remain on the employer page and are not added to the resume or stored as qualifications. The extension never receives JobFlow passwords or employer-portal credentials, does not bypass CAPTCHA/MFA, and supports only the domains declared in `manifest.json`.
