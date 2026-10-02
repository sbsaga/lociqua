# Lociqua Evidence Capture extension

This Chrome/Edge Manifest V3 extension is a user-assisted evidence form. It
does not crawl websites, automate browsing, solve CAPTCHAs, collect credentials,
or extract search results.

## Install for development

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this `extension` directory.
4. Sign in to Lociqua, select **Extension token**, and copy the displayed
   10-minute token. Do not use a password or a long-lived owner token.
5. Open a normal website that has an approved `browser_capture` source policy.
6. Click the extension, enter the Lociqua URL and token, review the fields, and
   explicitly confirm the capture.

The extension stores its configuration in browser session storage. Closing the
browser clears the token. An owner must approve a source policy before capture
is enabled for its domain.
