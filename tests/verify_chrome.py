import logging
import sys
import os

# Add project root to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from actions.executor import execute_system_command_detailed

# Setup basic logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TEST_RUNNER")

def test_open_chrome():
    print("\n" + "="*50)
    print("TESTING AGENTIC CORE: 'open chrome'")
    print("="*50)

    try:
        # We call the detailed executor which is the main entry point for the app
        result = execute_system_command_detailed("open chrome")

        print("\n--- Result ---")
        print(f"Success: {result.get('success')}")
        print(f"Method:  {result.get('method')}")
        print(f"Message:  {result.get('message')}")
        print(f"Output:   {result.get('output')}")
        print("="*50)

        if result.get('success'):
            print("\nSUCCESS: The AgentBrain generated and executed the code.")
        else:
            print("\nFAILED: The AgentBrain could not execute the command.")
            print(f"Error: {result.get('message')}")

    except Exception as e:
        print(f"\nCRITICAL ERROR during test: {e}")

if __name__ == "__main__":
    test_open_chrome()
