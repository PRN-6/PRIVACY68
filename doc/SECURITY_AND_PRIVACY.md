# Security and privacy reference

See [the security policy](../SECURITY.md) for current data handling and reporting instructions.

The assistant accepts text input. Cloud inference, Telegram, browser navigation, and requested screenshots can involve external services. Do not describe all processing as local or all stored credentials as encrypted.

The security guard checks generated code and supports user confirmation for sensitive actions. Execution retains the current user's permissions; neither a subprocess nor static code checks provide a full sandbox.

Telegram authorization is scoped to the configured chat. Unauthenticated responses do not include the pairing PIN. Audio attachments are rejected and edited messages do not trigger commands.
