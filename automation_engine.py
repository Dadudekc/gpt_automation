import os
import shutil
import logging
import json
from pathlib import Path
from webdriver_manager.chrome import ChromeDriverManager

# External imports from your project
from config import PROFILE_DIR, CHATGPT_HEADLESS, CHROMEDRIVER_PATH
from ModelRegistry import ModelRegistry  # Class-based registry
from ProjectScanner import ProjectScanner
from OpenAIClient import OpenAIClient   # New ChatGPT driver class
from local_llm_engine import LocalLLMEngine

# ------------------------------
# Logger Setup (with UTF-8 encoding)
# ------------------------------
log_file = "automation_engine.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ------------------------------
# Constants: Directory Paths
# ------------------------------
DEPLOY_FOLDER = Path("deployed")
BACKUP_FOLDER = Path("backups")

DEPLOY_FOLDER.mkdir(exist_ok=True)
BACKUP_FOLDER.mkdir(exist_ok=True)

# ------------------------------
# Automation Engine Class
# ------------------------------
class AutomationEngine:
    def __init__(self, use_local_llm=True, model_name='mistral'):
        logger.info("🚀 Initializing Automation Engine...")
        self.use_local_llm = use_local_llm
        self.model_name = model_name

        # Ensure ChromeDriver is available
        global CHROMEDRIVER_PATH
        if not os.path.exists(CHROMEDRIVER_PATH):
            logger.warning(f"❌ ChromeDriver not found at {CHROMEDRIVER_PATH}")
            logger.info("⬇️ Downloading ChromeDriver via webdriver_manager...")
            try:
                # Get the downloaded driver path and ensure correct file is referenced
                chrome_manager_path = ChromeDriverManager().install()
                # Fix path to ensure we're using the actual executable
                driver_dir = os.path.dirname(chrome_manager_path)
                if os.path.isdir(driver_dir):
                    for filename in os.listdir(driver_dir):
                        if filename.endswith(".exe"):
                            CHROMEDRIVER_PATH = os.path.join(driver_dir, filename)
                            logger.info(f"✅ ChromeDriver executable found at {CHROMEDRIVER_PATH}")
                            break
                    if not os.path.exists(CHROMEDRIVER_PATH):
                        CHROMEDRIVER_PATH = chrome_manager_path
                else:
                    CHROMEDRIVER_PATH = chrome_manager_path
                logger.info(f"✅ ChromeDriver downloaded to {CHROMEDRIVER_PATH}")
            except Exception as e:
                logger.error(f"❌ Failed to download ChromeDriver: {e}")
                raise FileNotFoundError(f"ChromeDriver not found and download failed: {e}")

        # Instantiate ModelRegistry and retrieve the registry
        try:
            model_reg_instance = ModelRegistry()
            self.model_registry = model_reg_instance.get_registry()
            if not self.model_registry:
                raise Exception("❌ No model plugins loaded. Aborting startup.")
            logger.info(f"✅ Model registry loaded with {len(self.model_registry)} models.")
        except Exception as e:
            logger.error(f"❌ Model registry initialization error: {e}")
            raise

        # Instantiate LLM Driver: Either Local or OpenAI
        if self.use_local_llm:
            try:
                self.driver = LocalLLMEngine(model=self.model_name)
                logger.info(f"✅ Local LLM engine initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"❌ Local LLM engine initialization error: {e}")
                raise
        else:
            try:
                self.openai_client = OpenAIClient(
                    profile_dir=PROFILE_DIR,
                    headless=CHATGPT_HEADLESS,
                    driver_path=CHROMEDRIVER_PATH
                )
                if not self.openai_client.login_openai():
                    logger.error("❌ OpenAI Login Failed.")
                    raise Exception("OpenAI Login Failed.")
                self.driver = self.openai_client.driver
                logger.info("✅ OpenAI session established via OpenAIClient.")
            except Exception as e:
                logger.error(f"❌ OpenAIClient initialization error: {e}")
                raise

        # Run ProjectScanner to load project analysis
        try:
            scanner = ProjectScanner(project_root=".")
            scanner.scan_project()
            analysis_path = Path("project_analysis.json")
            if analysis_path.exists():
                with open(analysis_path, "r", encoding="utf-8") as f:
                    self.project_analysis = json.load(f)
                logger.info("✅ Project analysis loaded successfully.")
            else:
                logger.warning("⚠️ No project analysis report found.")
                self.project_analysis = {}
        except Exception as e:
            logger.error(f"❌ Error running ProjectScanner: {e}")
            self.project_analysis = {}

    def get_chatgpt_response(self, prompt):
        """Unified call to LLM"""
        return self.driver.get_response(prompt)

    def switch_model(self, model_name):
        """Switch active LLM (local only for now)."""
        if not self.use_local_llm:
            logger.warning("⚠️ Model switching only works with local LLMs right now.")
            return
        self.driver.set_model(model_name)
        logger.info(f"✅ Switched to local model: {model_name}")

    def shutdown(self):
        """Gracefully shut down the ChatGPT or OpenAI driver."""
        logger.info("🛑 Shutting down Automation Engine...")
        try:
            if not self.use_local_llm and hasattr(self, "openai_client"):
                self.openai_client.shutdown()
                logger.info("✅ OpenAIClient driver shut down successfully.")
            else:
                logger.info("✅ Local LLM engine does not require shutdown.")
        except Exception as e:
            logger.error(f"❌ Error shutting down driver: {e}")

    def process_file(self, file_path, manual_model=None):
        """Process a single file from start to deployment."""
        logger.info(f"📂 Processing file: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"❌ File not found: {file_path}")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            logger.error(f"❌ Failed to read file {file_path}: {e}")
            return None

        # --- Model Selection ---
        model_choice = manual_model or self.select_model(file_content)
        model_meta = self.model_registry.get(model_choice)
        if not model_meta:
            logger.error(f"❌ Model '{model_choice}' not found in registry.")
            return None

        endpoint = model_meta.get('endpoint')
        handler = model_meta.get('handler')
        logger.info(f"🧠 Selected model: {model_choice} | Endpoint: {endpoint}")

        # Invoke the model handler.
        # Each handler now accepts (driver, file_content, endpoint)
        try:
            response = handler(self.driver, file_content, endpoint)
        except Exception as e:
            logger.error(f"❌ Error from model handler '{model_choice}': {e}")
            return None

        if not response:
            logger.warning(f"⚠️ No response received for {file_path}")
            return None

        # --- Save Refactored Code ---
        output_file = file_path.replace(".py", "_refactored.py")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(response)
            logger.info(f"✅ Refactored file saved: {output_file}")
        except Exception as e:
            logger.error(f"❌ Failed to write refactored file {output_file}: {e}")
            return None

        # --- Test and Deploy ---
        if self.run_tests(output_file):
            self.deploy_file(output_file)
        else:
            logger.warning(f"⚠️ Tests failed for {output_file}. Skipping deployment.")
        return output_file

    def self_heal_file(self, file_path):
        """Perform self-healing on the file at file_path."""
        logger.info(f"🩺 Starting self-heal process for: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"❌ File not found: {file_path}")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            logger.error(f"❌ Failed to read file {file_path}: {e}")
            return None

        # --- Self-Heal Prompt ---
        prompt_text = (
            "You are a code repair bot. Analyze the following file and fix any issues, bugs, "
            "or style inconsistencies. Provide the corrected, complete code."
        )
        combined_prompt = f"{prompt_text}\n\n---\n\n{file_content}"

        logger.info("🧠 Sending file content for self-healing...")
        response = self.get_chatgpt_response(combined_prompt)

        if not response:
            logger.error("❌ Self-heal failed. No response from model.")
            return None

        logger.info("✅ Self-heal response received.")
        return response

    def select_model(self, file_content):
        """
        Dynamically select the model based on line count.
        (Extend this to consider file complexity if desired.)
        """
        lines = len(file_content.strip().splitlines())
        logger.info(f"📏 File has {lines} lines.")
        # Sort registry items by descending threshold value
        for model_name, meta in sorted(self.model_registry.items(), key=lambda x: -x[1]['threshold']):
            if lines >= meta["threshold"]:
                return model_name
        logger.warning("⚠️ No matching model found. Defaulting to first available model.")
        return next(iter(self.model_registry))

    def run_tests(self, file_path):
        """Basic test placeholder. Replace with actual test logic."""
        logger.info(f"🧪 Running tests for: {file_path}")
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info("✅ Test passed.")
                return True
        except Exception as e:
            logger.error(f"❌ Test error for {file_path}: {e}")
        return False

    def deploy_file(self, file_path):
        """Deploy and backup the file."""
        backup_path = BACKUP_FOLDER / (Path(file_path).stem + "_backup.py")
        deploy_path = DEPLOY_FOLDER / Path(file_path).name
        logger.info(f"📦 Deploying file: {file_path}")
        try:
            shutil.copy2(file_path, backup_path)
            shutil.move(file_path, deploy_path)
            logger.info(f"✅ Deployed to: {deploy_path}")
            logger.info(f"🗄️ Backup saved at: {backup_path}")
        except Exception as e:
            logger.error(f"❌ Deployment error for {file_path}: {e}")

    def prioritize_files(self):
        """
        Prioritize files based on their complexity score from the project analysis.
        Returns a list of file paths sorted in descending order of complexity.
        """
        prioritized = []
        for file_path, data in self.project_analysis.items():
            complexity = data.get("complexity", 0)
            prioritized.append((file_path, complexity))
        prioritized.sort(key=lambda x: x[1], reverse=True)
        logger.info("✅ Files prioritized based on complexity score.")
        # Convert relative paths to absolute paths.
        return [str(Path(file).resolve()) for file, _ in prioritized]

    def process_all_files(self):
        """Process all files, prioritized by complexity."""
        files = self.prioritize_files()
        for file_path in files:
            self.process_file(file_path)

    def ask_question_in_history(self, question, **kwargs):
        """Iterate through every ChatGPT conversation and ask *question* (OpenAI mode only)."""
        if self.use_local_llm or not hasattr(self, "openai_client"):
            logger.error("❌ Conversation iteration requires OpenAIClient (set use_local_llm=False).")
            return {}
        return self.openai_client.iterate_conversations(question, **kwargs)

# ------------------------------
# Entry Point
# ------------------------------
if __name__ == "__main__":
    engine = AutomationEngine(use_local_llm=True, model_name='mistral')
    
    # Option 1: Process a single file (e.g., "example.py")
    # engine.process_file("example.py")
    
    # Option 2: Process all files prioritized by complexity
    engine.process_all_files()
    
    engine.shutdown()
