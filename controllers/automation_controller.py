from automation_engine import AutomationEngine

class AutomationController:
    def __init__(self, helpers):
        self.helpers = helpers
        self.engine = AutomationEngine()

    def process_file(self, file_path, file_content):
        prompt_text = "Update this file and show me the complete updated version."
        combined_prompt = f"{prompt_text}\n\n---\n\n{file_content}"
        response = self.engine.get_chatgpt_response(combined_prompt)
        if response:
            updated_file = f"{file_path}.updated.py"
            if self.helpers.save_file(updated_file, response):
                return f"✅ Updated file saved: {updated_file}"
            return f"❌ Failed to save: {updated_file}"
        return "❌ No response from ChatGPT."

    def self_heal_file(self, file_path, file_content):
        response = self.engine.self_heal_file(file_path)
        if response:
            updated_file = f"{file_path}.selfhealed.py"
            if self.helpers.save_file(updated_file, response):
                return f"✅ Self-healed file saved: {updated_file}"
            return f"❌ Failed to save self-healed file: {updated_file}"
        return "❌ Self-Heal did not produce a response."

    def run_tests_on_file(self, file_path):
        results = self.engine.run_tests(file_path)
        return f"Test results for {file_path}:\n{results}"

    def shutdown(self):
        self.engine.shutdown()
