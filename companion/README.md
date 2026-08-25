# JobFlow AI Companion

The companion runs in the candidate's own Chrome/Edge browser. It supports public Greenhouse and Lever application pages, fills reviewed JobFlow details, attaches the verified tailored PDF when the portal permits it, highlights unanswered required fields, and waits for an explicit confirmation before clicking the portal's submit button.

## Install locally

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `companion` directory.
4. In JobFlow, prepare and review an application, then select **Fill on job portal**.

The launch token expires after 20 minutes. The extension never receives JobFlow passwords or employer-portal credentials, does not bypass CAPTCHA/MFA, and supports only the domains declared in `manifest.json`.
