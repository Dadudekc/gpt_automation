import os
import time
import json
import pickle
import logging
import shutil
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from setup_logging import setup_logging

logger = setup_logging("openai_login", log_dir=os.path.join(os.getcwd(), "logs", "social"))

class OpenAIClient:
    def __init__(self, profile_dir, headless=False, driver_path=None):
        """
        Initialize the OpenAIClient.

        Args:
            profile_dir (str): Path to the Chrome user data directory.
            headless (bool): Whether to run Chrome in headless mode.
            driver_path (str): Optional custom path to a ChromeDriver binary.
        """
        self.profile_dir = profile_dir
        self.headless = headless
        self.driver_path = driver_path

        # Configuration
        self.CHATGPT_URL = "https://chat.openai.com/"
        self.COOKIE_DIR = os.path.join(os.getcwd(), "cookies")
        self.COOKIE_FILE = os.path.join(self.COOKIE_DIR, "openai.pkl")
        self.CACHED_DRIVER_PATH = os.path.join(os.getcwd(), "drivers", "chromedriver.exe")

        # Initialize driver
        self.driver = self.get_openai_driver()

    def get_openai_driver(self):
        """
        Returns a stealth Chrome driver using undetected_chromedriver.
        """
        try:
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError:
            logger.error("❌ webdriver_manager is not installed. Run 'pip install webdriver_manager'")
            raise

        final_driver_path = None

        if self.driver_path and os.path.exists(self.driver_path):
            final_driver_path = self.driver_path
            logger.info(f"🔎 Using custom ChromeDriver: {final_driver_path}")
        elif os.path.exists(self.CACHED_DRIVER_PATH):
            final_driver_path = self.CACHED_DRIVER_PATH
            logger.info(f"🔎 Using cached ChromeDriver: {final_driver_path}")
        else:
            logger.warning("❌ No valid ChromeDriver found locally. Downloading with webdriver_manager...")
            try:
                downloaded_driver_path = ChromeDriverManager().install()
                logger.info(f"✅ ChromeDriver downloaded to {downloaded_driver_path}")

                # Look for the actual executable in the directory
                driver_dir = os.path.dirname(downloaded_driver_path)
                if os.path.isdir(driver_dir):
                    for filename in os.listdir(driver_dir):
                        if filename.endswith(".exe"):
                            downloaded_driver_path = os.path.join(driver_dir, filename)
                            logger.info(f"✅ ChromeDriver executable found at {downloaded_driver_path}")
                            break

                os.makedirs(os.path.dirname(self.CACHED_DRIVER_PATH), exist_ok=True)
                shutil.copyfile(downloaded_driver_path, self.CACHED_DRIVER_PATH)
                final_driver_path = self.CACHED_DRIVER_PATH
                logger.info(f"✅ ChromeDriver cached at {final_driver_path}")
            except Exception as e:
                logger.error(f"❌ Failed to download ChromeDriver: {e}")
                raise FileNotFoundError("ChromeDriver not found. Provide a valid driver_path or place a driver in /drivers/.")

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        if self.profile_dir:
            options.add_argument(f"--user-data-dir={self.profile_dir}")
        if self.headless:
            options.add_argument("--headless=new")

        # uc.Chrome internally references `options.headless`, which was removed
        # from Selenium 4.20. Dynamically add the attribute to prevent
        # `AttributeError: 'ChromeOptions' object has no attribute 'headless'`.
        # This preserves backward-compatibility and respects the `self.headless`
        # flag.
        options.headless = self.headless

        driver = uc.Chrome(
            options=options,
            driver_executable_path=final_driver_path
        )

        logger.info("✅ Undetected Chrome driver initialized for OpenAI.")
        return driver

    def save_openai_cookies(self):
        """
        Save OpenAI cookies to a pickle file.
        """
        os.makedirs(self.COOKIE_DIR, exist_ok=True)
        try:
            cookies = self.driver.get_cookies()
            with open(self.COOKIE_FILE, "wb") as f:
                pickle.dump(cookies, f)
            logger.info(f"✅ Saved OpenAI cookies to {self.COOKIE_FILE}")
        except Exception as e:
            logger.error(f"❌ Failed to save cookies: {e}")

    def load_openai_cookies(self):
        """
        Load OpenAI cookies from file and refresh session.
        """
        if not os.path.exists(self.COOKIE_FILE):
            logger.warning("⚠️ No OpenAI cookie file found. Manual login may be required.")
            return False

        self.driver.get(self.CHATGPT_URL)
        time.sleep(2)

        try:
            with open(self.COOKIE_FILE, "rb") as f:
                cookies = pickle.load(f)
            for cookie in cookies:
                cookie.pop("sameSite", None)
                self.driver.add_cookie(cookie)
            self.driver.refresh()
            time.sleep(5)
            logger.info("✅ OpenAI cookies loaded and session refreshed.")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load cookies: {e}")
            return False

    def is_logged_in(self):
        """
        Checks if the user is logged in to ChatGPT by navigating to a tactic generator URL.
        """
        TARGET_URL = "https://chatgpt.com/g/g-67a4c53f01648191bdf31ab8591e84e7-tbow-tactic-generator"
        self.driver.get(TARGET_URL)
        time.sleep(3)
        current_url = self.driver.current_url

        if current_url.startswith("https://chatgpt.com/g/"):
            logger.info("✅ Tactic generator page reached; user is logged in.")
            self.driver.get(self.CHATGPT_URL)
            time.sleep(3)
            return True
        else:
            logger.warning("⚠️ Unable to reach tactic generator page; login may be required.")
            return False

    def login_openai(self):
        """
        Login handler for OpenAI/ChatGPT.
        Checks if session is active; if not, tries to load cookies or falls back to manual login.
        """
        logger.info("🔐 Starting OpenAI login process...")

        if self.is_logged_in():
            logger.info("✅ Already logged in; starting work immediately.")
            return True

        if self.load_openai_cookies() and self.is_logged_in():
            logger.info("✅ OpenAI auto-login successful with cookies.")
            return True

        logger.warning("⚠️ Manual login required. Navigating to login page...")
        self.driver.get("https://chat.openai.com/auth/login")
        time.sleep(5)

        input("👉 Please manually complete the login + verification and press ENTER here...")

        if self.is_logged_in():
            self.save_openai_cookies()
            logger.info("✅ Manual OpenAI login successful. Cookies saved.")
            return True
        else:
            logger.error("❌ Manual OpenAI login failed. Try again.")
            return False

    def send_prompt_smoothly(self, element, prompt, delay=0.05):
        """
        Sends the prompt text one character at a time for a more human-like interaction.
        """
        for char in prompt:
            element.send_keys(char)
            time.sleep(delay)

    def get_chatgpt_response(self, prompt, timeout=120, model_url=None):
        """
        Sends a prompt to ChatGPT and retrieves the full response by interacting with the ProseMirror element.
        """
        logger.info("✉️ Sending prompt to ChatGPT...")

        try:
            target_url = model_url if model_url else self.CHATGPT_URL
            self.driver.get(target_url)

            wait = WebDriverWait(self.driver, 15)

            # Wait for the ProseMirror contenteditable div to be present and clickable.
            input_div = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "div.ProseMirror[contenteditable='true']")
            ))
            logger.info("✅ Found ProseMirror input.")

            input_div.click()

            # Type the prompt slowly for human-like behavior.
            self.send_prompt_smoothly(input_div, prompt, delay=0.03)

            # Submit the prompt
            input_div.send_keys(Keys.RETURN)
            logger.info("✅ Prompt submitted, waiting for response...")

            return self.get_full_response(timeout=timeout)

        except Exception as e:
            logger.error(f"❌ Error in get_chatgpt_response: {e}")
            return ""

    def get_full_response(self, timeout=120):
        """
        Waits for the full response from ChatGPT, clicking "Continue generating" if necessary.
        """
        logger.info("🔄 Waiting for full response...")
        start_time = time.time()
        full_response = ""

        while True:
            if time.time() - start_time > timeout:
                logger.warning("⚠️ Timeout reached while waiting for ChatGPT response.")
                break

            time.sleep(3)
            try:
                messages = self.driver.find_elements(By.CSS_SELECTOR, ".markdown.prose.w-full.break-words")
                if messages:
                    latest_message = messages[-1].text
                    if latest_message != full_response:
                        full_response = latest_message
                    else:
                        logger.info("✅ Response appears complete.")
                        break

                continue_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue generating')]")
                if continue_buttons:
                    logger.info("🔘 Clicking 'Continue generating'...")
                    continue_buttons[0].click()
            except Exception as e:
                logger.error(f"❌ Error during response fetch: {e}")
                continue

        return full_response

    def process_prompt(self, prompt, timeout=120, model_url=None):
        """
        A convenience method for asynchronous workers.
        Ensures the session is valid and returns the ChatGPT response for a given prompt.
        """
        if not self.is_logged_in():
            logger.info("Session expired. Attempting to log in again...")
            if not self.login_openai():
                logger.error("❌ Unable to re-login; cannot process prompt.")
                return ""
        response = self.get_chatgpt_response(prompt, timeout=timeout, model_url=model_url)
        return response

    def iterate_conversations(self, question, delay_between=3, max_threads=None, save_dir="conversation_queries"):
        """
        Iterate over each ChatGPT conversation visible in the sidebar, ask a uniform
        question, capture the response, and save the result to disk.

        Args:
            question (str): The prompt/question you want to ask in every thread.
            delay_between (int): Seconds to wait after switching threads before sending the question.
            max_threads (int|None): Process only the first *n* threads; None means no limit.
            save_dir (str): Directory used to persist each answer as a text file.

        Returns:
            dict[str, str]: Mapping of conversation identifier (slug or title) to the response text.
        """
        logger.info("🔄 Starting bulk-question run across conversation history…")

        if not self.is_logged_in():
            logger.error("❌ Cannot iterate conversations: not logged in.")
            return {}

        # Make sure we are on the main chat page so the sidebar is present.
        self.driver.get(self.CHATGPT_URL)
        time.sleep(3)

        os.makedirs(save_dir, exist_ok=True)
        results = {}

        # Collect sidebar links to conversation threads.
        conv_links = self.driver.find_elements(By.CSS_SELECTOR, "nav a[href^='/c/']")
        logger.info(f"📋 Found {len(conv_links)} conversation links in sidebar.")

        for idx, link in enumerate(conv_links):
            if max_threads is not None and idx >= max_threads:
                break
            try:
                # Extract identifier for logging and filenames.
                conv_href = link.get_attribute("href")
                conv_id = conv_href.split("/c/")[-1].strip("/") or f"thread_{idx}"

                logger.info(f"➡️ Opening conversation {idx + 1}: {conv_id}")
                self.driver.execute_script("arguments[0].click();", link)
                time.sleep(delay_between)

                # Ask the question inside this thread.
                response_text = self.get_chatgpt_response(question)
                results[conv_id] = response_text

                # Persist to individual file for offline review.
                out_path = os.path.join(save_dir, f"{conv_id}.txt")
                with open(out_path, "w", encoding="utf-8") as fh:
                    fh.write(response_text)
                logger.info(f"✅ Saved answer for {conv_id} → {out_path}")
            except Exception as e:
                logger.error(f"❌ Failed while processing conversation {idx + 1}: {e}")

        logger.info("🏁 Completed bulk-question run across history.")
        return results

    def get_full_response_for_debug(self, timeout=120):
        """
        For debugging purposes: returns the full response without sending a prompt.
        """
        return self.get_full_response(timeout=timeout)

    def shutdown(self):
        """
        Shut down the driver gracefully.
        """
        logger.info("🛑 Shutting down OpenAIClient driver...")
        try:
            if self.driver:
                self.driver.quit()
                logger.info("✅ Driver shut down successfully.")
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")


# --------------------
# Test Run (Optional)
# --------------------
if __name__ == "__main__":
    PROFILE_DIR = os.path.join(os.getcwd(), "chrome_profile", "openai")
    client = OpenAIClient(profile_dir=PROFILE_DIR, headless=False, driver_path=None)

    if client.login_openai():
        logger.info("🎉 OpenAI Login Complete!")
    else:
        logger.error("❌ OpenAI Login Failed.")

    prompt = "Tell me a joke about AI."
    response = client.process_prompt(prompt)
    logger.info(f"Received response: {response}")

    time.sleep(10)
    client.shutdown()
