import logging
import time
import threading
import pyttsx3
from faster_whisper import WhisperModel
from actions.agent_brain import agent_brain

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PRIVACY68.Core")

class Privacy68Assistant:
    def __init__(self):
        logger.info("Initializing PRIVACY68 Assistant...")

        # 1. Initialize Voice Output (TTS)
        self.engine = pyttsx3.init()
        self.set_voice_properties()

        # 2. Initialize Voice Input (STT) - Using tiny model for speed
        # You can change "tiny" to "base" or "small" for better accuracy
        logger.info("Loading Whisper STT Model...")
        self.stt_model = WhisperModel("tiny", device="cpu", compute_type="int8")

        self.is_running = True
        self.is_listening = False

    def set_voice_properties(self):
        voices = self.engine.getProperty('voices')
        # Try to find a clear English voice
        for voice in voices:
            if "English" in voice.name:
                self.engine.setProperty('voice', voice.id)
                break
        self.engine.setProperty('rate', 175)  # Speaking speed

    def speak(self, text):
        """Makes the assistant talk."""
        logger.info(f"[VOICE]: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        """
        Listens to the microphone and converts speech to text.
        In a full production version, this would include a Wake-Word (e.g., 'Hey Privacy').
        """
        # Note: This is a simplified implementation.
        # For a real production app, we would use a streaming audio buffer.
        import sounddevice as sd
        import numpy as np
        import scipy.io.wavfile as wav

        duration = 5  # seconds to record per command
        fs = 16000

        try:
            logger.info("Listening...")
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
            sd.wait()

            # Save temporary file for Whisper to process
            wav.write("temp_cmd.wav", fs, recording)

            segments, _ = self.stt_model.transcribe("temp_cmd.wav", beam_size=5)
            text = " ".join([segment.text for segment in segments]).strip()
            return text
        except Exception as e:
            logger.error(f"Error during listening: {e}")
            return ""

    def run(self):
        """Main Application Loop"""
        self.speak("PRIVACY 68 system online. I am listening.")

        try:
            while self.is_running:
                # 1. Listen for a command
                command = self.listen()

                if not command:
                    continue

                logger.info(f"[USER]: {command}")

                # Optional: Check for exit command
                if "shutdown" in command.lower() or "stop" in command.lower():
                    self.speak("Shutting down system. Goodbye.")
                    self.is_running = False
                    break

                # 2. Process with the Brain
                self.speak("Processing your request...")
                result = agent_brain.generate_and_execute(command)

                # 3. Respond based on result
                if result["success"]:
                    self.speak("Task completed successfully.")
                    logger.info(f"Result: {result.get('output', '')}")
                else:
                    error_msg = result.get("message", "I encountered an error.")
                    self.speak(f"I'm sorry, {error_msg}")
                    logger.error(f"Brain Error: {error_msg}")

        except KeyboardInterrupt:
            self.is_running = False
            logger.info("Stopped by user.")

if __name__ == "__main__":
    assistant = Privacy68Assistant()
    assistant.run()
