# Security and privacy

PRIVACY68 is a Windows text-command automation assistant. It can execute programs with the current user's permissions.

## Data handling

- Typed instructions may be sent to the configured AI provider. Cloud providers process requests outside this computer; a local model endpoint must be configured separately for local inference.
- Telegram is an external service. Commands, replies, and requested screenshots pass through its Bot API.
- The application does not capture or transcribe audio. Telegram audio attachments are rejected without downloading them.
- AI and Telegram settings can be stored in local `.env` and profile files. These files are not all encrypted. The GitHub credential helper uses Windows Credential Manager when available, with local fallback behavior.
- Logs and learned skills may contain command details. Review them before sharing diagnostics.

## Execution boundaries

Generated Python is checked by the security guard and run in a subprocess with a timeout. Static checks and confirmation prompts are defense in depth, not an operating-system sandbox. Scripts and built-in actions retain the user's filesystem and desktop privileges.

Telegram requires a pairing PIN before a chat can execute commands. The PIN is displayed locally and is not included in unauthenticated welcome messages. Commands are accepted only from the configured chat; edited messages are ignored. Use a private chat and keep the bot token and desktop PIN confidential. `/unpair` clears authorization and rotates the PIN in the running process.

## Reporting vulnerabilities

Do not post undisclosed vulnerabilities or credentials in public issues. Use the repository's GitHub **Security → Report a vulnerability** workflow. Include reproduction steps, the affected version, operating system, and expected versus actual behavior.
