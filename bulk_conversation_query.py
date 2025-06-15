import argparse
import os
import sys
import time
from pathlib import Path

# Re-use existing helper modules
from config import PROFILE_DIR, CHROMEDRIVER_PATH, CHATGPT_HEADLESS
from OpenAIClient import OpenAIClient


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send a uniform question to every ChatGPT conversation in the account sidebar and save the answers.")

    parser.add_argument("question", type=str, help="The question/prompt to send to each conversation thread.")
    parser.add_argument("--max-threads", type=int, default=None, dest="max_threads",
                        help="Maximum number of conversation threads to process (default: all).")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds to wait after opening a conversation before sending the prompt (default: 3).")
    parser.add_argument("--headless", action="store_true",
                        help="Launch Chrome in headless mode (overrides CHATGPT_HEADLESS config).")
    parser.add_argument("--driver-path", type=str, default=CHROMEDRIVER_PATH,
                        help="Path to chromedriver executable (default: value in config.py).")
    parser.add_argument("--profile-dir", type=str, default=PROFILE_DIR,
                        help="Chrome user-data directory to reuse login session (default: chrome_profile/openai).")

    return parser.parse_args()


def main():
    args = parse_args()

    # Ensure profile directory exists
    os.makedirs(args.profile_dir, exist_ok=True)

    # Instantiate OpenAIClient directly to avoid full AutomationEngine startup overhead.
    client = OpenAIClient(
        profile_dir=args.profile_dir,
        headless=args.headless or CHATGPT_HEADLESS,
        driver_path=args.driver_path,
    )

    if not client.login_openai():
        print("[ERROR] Failed to log in to ChatGPT. Aborting.")
        client.shutdown()
        sys.exit(1)

    results = client.iterate_conversations(
        question=args.question,
        delay_between=args.delay,
        max_threads=args.max_threads,
    )

    # Simple summary output
    output_dir = Path("conversation_queries").resolve()
    print("\n=== SUMMARY ===")
    print(f"Saved {len(results)} responses to {output_dir}")
    for conv_id, answer in results.items():
        snippet = (answer[:75] + "…") if answer and len(answer) > 75 else answer
        print(f"- {conv_id}: {snippet}")

    client.shutdown()


if __name__ == "__main__":
    main() 