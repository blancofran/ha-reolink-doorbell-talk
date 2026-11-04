# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's private reporting instead: go to the **Security** tab of this repository and choose **Report a vulnerability**. You will get an answer as soon as possible.

Please include the integration version, what you found and, if you can, how to reproduce it. Do not include real passwords or public addresses.

## Good to know

- The doorbell password is stored by Home Assistant in its configuration (`/config/.storage/core.config_entries`, in plain text, like any integration's credentials) and is never sent to the browser. Encrypt your Home Assistant backups.
- Diagnostics downloaded from the integration hide the password, the username, the address and the serial number.
- By default any Home Assistant user can use the talk button; the integration option *Only administrators can talk* restricts it.
