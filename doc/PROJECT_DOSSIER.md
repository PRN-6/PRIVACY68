# Project overview

PRIVACY68 is a Windows desktop assistant for typed natural-language commands. Its UI consists of a system tray, a compact command bar, and a WebView Control Center. An optional Telegram bot provides remote text input and desktop screenshots.

The executor handles common operations directly and sends complex tasks to the configured AI model. Markdown skills supply task context, while native Python services implement Windows and Gmail integrations. Generated code passes through security checks before subprocess execution.

The current cleanup removes speech recognition, audio decoding, recording controls, voice enrollment stubs, and their packaging dependencies. It also preserves typed payloads, makes UI worker communication use queues, and reports browser-launch failures accurately.

For implementation details, use [architecture](ARCHITECTURE.md), [channels](CHANNELS.md), [setup](SETUP_AND_CONFIGURATION.md), and [verification](VERIFICATION_AND_TESTS.md). Performance depends on the machine, configured model, and network; the repository does not establish universal latency or memory guarantees.
