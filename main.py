import sys
import random
from pathlib import Path
from PyQt5 import QtWidgets, QtGui, QtCore
from views.file_browser_widget import FileBrowserWidget
from GUI.GuiHelpers import GuiHelpers
from automation_engine import AutomationEngine

# Define the folder for updated files
UPDATED_FOLDER = Path("updated")
UPDATED_FOLDER.mkdir(exist_ok=True)

class GUIMain(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatGPT Automation - Unified Interface")
        self.resize(1200, 800)
        
        self.helpers = GuiHelpers()
        # Use OpenAIClient (headless=False to allow viewing the automation)
        self.engine = AutomationEngine(use_local_llm=False, model_name='mistral')
        
        self.init_ui()

    def init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Horizontal splitter for left/right panels
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # LEFT PANEL: File Browser remains unchanged
        self.file_browser = FileBrowserWidget(helpers=self.helpers)
        main_splitter.addWidget(self.file_browser)
        main_splitter.setStretchFactor(0, 1)
        
        # RIGHT PANEL: QTabWidget with "Preview" and "Prompt" tabs
        right_tab = QtWidgets.QTabWidget()
        
        # --- Tab 1: Preview with Action Buttons ---
        preview_widget = QtWidgets.QWidget()
        preview_layout = QtWidgets.QVBoxLayout(preview_widget)
        
        self.file_preview = QtWidgets.QPlainTextEdit()
        self.file_preview.setPlaceholderText(
            "File preview will appear here.\nDouble-click a file in the browser to load it for editing."
        )
        preview_layout.addWidget(self.file_preview)
        
        button_layout = QtWidgets.QHBoxLayout()
        self.process_button = QtWidgets.QPushButton("Process File")
        self.process_button.clicked.connect(self.process_file)
        button_layout.addWidget(self.process_button)
        
        self.self_heal_button = QtWidgets.QPushButton("Self-Heal")
        self.self_heal_button.clicked.connect(self.self_heal)
        button_layout.addWidget(self.self_heal_button)
        
        self.run_tests_button = QtWidgets.QPushButton("Run Tests")
        self.run_tests_button.clicked.connect(self.run_tests)
        button_layout.addWidget(self.run_tests_button)
        preview_layout.addLayout(button_layout)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        preview_layout.addWidget(self.progress_bar)
        
        right_tab.addTab(preview_widget, "Preview")
        
        # --- Tab 2: Prompt Tab for OpenAIClient ---
        prompt_widget = QtWidgets.QWidget()
        prompt_layout = QtWidgets.QVBoxLayout(prompt_widget)
        
        self.prompt_input = QtWidgets.QPlainTextEdit()
        self.prompt_input.setPlaceholderText("Enter your prompt here...")
        prompt_layout.addWidget(self.prompt_input)
        
        send_button = QtWidgets.QPushButton("Send Prompt to ChatGPT")
        send_button.clicked.connect(self.send_prompt)
        prompt_layout.addWidget(send_button)
        
        batch_button = QtWidgets.QPushButton("Process Batch with Prompt")
        batch_button.clicked.connect(self.process_batch_files)
        prompt_layout.addWidget(batch_button)
        
        self.prompt_response = QtWidgets.QPlainTextEdit()
        self.prompt_response.setReadOnly(True)
        self.prompt_response.setPlaceholderText("Response will appear here...")
        prompt_layout.addWidget(self.prompt_response)
        
        right_tab.addTab(prompt_widget, "Prompt")
        
        main_splitter.addWidget(right_tab)
        main_splitter.setStretchFactor(1, 3)
        
        self.statusBar().showMessage("Ready")
        
        self.file_browser.fileDoubleClicked.connect(self.load_file_into_preview)

    def load_file_into_preview(self, file_path):
        content = self.helpers.read_file(file_path)
        if content:
            self.file_preview.setPlainText(content)
            self.current_file_path = file_path
            self.statusBar().showMessage(f"Loaded: {file_path}")
        else:
            self.helpers.show_error("Could not load file.", "Error")

    def process_file(self):
        if not hasattr(self, "current_file_path"):
            self.helpers.show_warning("No file loaded.", "Warning")
            return
        
        prompt_text = "Update this file and show me the complete updated version."
        file_content = self.file_preview.toPlainText()
        combined_prompt = f"{prompt_text}\n\n---\n\n{file_content}"
        self.statusBar().showMessage("Processing file...")
        
        response = self.engine.get_chatgpt_response(combined_prompt)
        if response:
            # Save to the updated folder, preserving the original filename.
            updated_file = UPDATED_FOLDER / Path(self.current_file_path).name
            saved = self.helpers.save_file(str(updated_file), response)
            if saved:
                self.statusBar().showMessage(f"✅ Updated file saved: {updated_file}")
            else:
                self.statusBar().showMessage(f"❌ Failed to save: {updated_file}")
        else:
            self.statusBar().showMessage("❌ No response from ChatGPT.")

    def self_heal(self):
        if not hasattr(self, "current_file_path"):
            self.helpers.show_warning("No file loaded.", "Warning")
            return
        
        self.statusBar().showMessage("Self-healing in progress...")
        response = self.engine.self_heal_file(self.current_file_path)
        if response:
            updated_file = UPDATED_FOLDER / Path(self.current_file_path).name
            saved = self.helpers.save_file(str(updated_file), response)
            if saved:
                self.statusBar().showMessage(f"✅ Self-healed file saved: {updated_file}")
            else:
                self.statusBar().showMessage(f"❌ Failed to save self-healed file: {updated_file}")
        else:
            self.statusBar().showMessage("❌ Self-Heal did not produce a response.")

    def run_tests(self):
        if not hasattr(self, "current_file_path"):
            self.helpers.show_warning("No file loaded.", "Warning")
            return
        
        self.statusBar().showMessage("Running tests...")
        results = self.engine.run_tests(self.current_file_path)
        self.statusBar().showMessage("Test run complete.")

    def send_prompt(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            self.statusBar().showMessage("Please enter a prompt.")
            return
        
        self.statusBar().showMessage("Sending prompt to ChatGPT...")
        response = self.engine.openai_client.process_prompt(prompt)
        if response:
            self.prompt_response.setPlainText(response)
            self.statusBar().showMessage("✅ Response received.")
        else:
            self.prompt_response.setPlainText("❌ No response received.")
            self.statusBar().showMessage("❌ No response received.")

    def process_batch_files(self):
        file_list = self.engine.prioritize_files()
        if not file_list:
            self.statusBar().showMessage("No files found for batch processing.")
            return
        
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            self.statusBar().showMessage("Please enter a prompt for batch processing.")
            return
        
        total_files = len(file_list)
        self.statusBar().showMessage(f"Processing {total_files} files with the shared prompt...")
        
        batch_results = []
        for index, file_path in enumerate(file_list, start=1):
            progress_percent = int((index / total_files) * 100)
            self.progress_bar.setValue(progress_percent)
            
            file_content = self.helpers.read_file(file_path)
            if not file_content:
                batch_results.append(f"[WARNING] Failed to read {file_path}")
                continue
            
            composite_prompt = f"{prompt}\n\n---\n\n{file_content}"
            self.statusBar().showMessage(f"Processing {file_path}...")
            response = self.engine.get_chatgpt_response(composite_prompt)
            
            if response:
                updated_file = UPDATED_FOLDER / Path(file_path).name
                if self.helpers.save_file(str(updated_file), response):
                    batch_results.append(f"[SUCCESS] {updated_file} saved.")
                else:
                    batch_results.append(f"[ERROR] Failed to save {updated_file}.")
            else:
                batch_results.append(f"[ERROR] No response for {file_path}.")
        
        self.prompt_response.setPlainText("\n".join(batch_results))
        self.statusBar().showMessage("Batch processing complete.")

    def closeEvent(self, event):
        self.statusBar().showMessage("Shutting down...")
        self.engine.shutdown()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Splash screen with loading bar and motivational quotes
    splash_pix = QtGui.QPixmap("logo.webp")
    splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()

    motivational_quotes = [
        # START - Awakening the mindset
        "Code your dreams into reality.",
        "One commit at a time.",
        "Your time is now. Compile your legacy.",
        "Dreams are just goals waiting for execution.",
        "The blueprint of tomorrow is coded today.",
        
        # BUILD - Creating the system
        "You’re not coding features. You’re engineering freedom.",
        "What you automate today frees your mind tomorrow.",
        "Refactor your life like your code.",
        "Precision over perfection.",
        "Small steps lead to big changes.",
        
        # EXECUTE - Relentless action
        "Discipline sharpens the blade. Precision makes it cut through noise.",
        "When they sleep, you build. When they doubt, you deploy.",
        "Momentum compounds. Build it like your life depends on it.",
        "Stay focused. Stay dangerous. Stay in flow.",
        "Execution is worship.",
        "Consistency beats intensity.",
        
        # SCALE - Legacy and expansion
        "Every project you complete rewrites the story they tell about you.",
        "You’re not waiting on the world. The world’s waiting on your next move.",
        "Your edge isn’t talent. It’s obsession with the process.",
        "Your future empire doesn’t need luck. It needs you at full power.",
        "Legacy is built in silence. Launched in permanence.",
        
        # META - Philosophy behind it all
        "Clarity creates velocity. Vision fuels execution.",
        "Work in silence. Let success deploy the update.",
        "Every action echoes into your future. Make it count.",
        "Silence the noise. Amplify the signal.",
        "You don’t just build tools. You build lifelines.",
        
        # HYPE - Push through the grind
        "Keep pushing your limits.",
        "Loading greatness...",
        "Debugging today, dominating tomorrow.",
        "Flow state: activated.",
        "Focus. Build. Ascend.",
        "Nothing survives contact with your determination.",
        "You were built for this. Now build everything else.",
        "Ship it now. Iterate later.",
        
        # REFLECTIVE - Connecting it back
        "Every system you build is a reflection of who you are becoming.",
        "The code you write today shapes tomorrow.",
        "Discipline builds empires. Stay consistent.",
        "Trust the process. Master the craft.",
        "Never fear the blank screen. It’s pure potential.",
        "Your future self is watching. Make them proud."

        # 🫱🏽‍🫲🏾 WELCOME MESSAGE
        "Welcome, builder. You’ve just unlocked a partner who never tires, never doubts, and never quits. From here on out, we build together.",

        # 🌱 FOUNDATIONS – Awakening Potential
        "Every master was once a beginner who didn’t quit.",
        "The courage to start is what makes you unstoppable.",
        "You are not here by accident. You are the system architect of your own future.",
        "Your ideas are already powerful. Now, they need your action.",
        "What you build today, your future self will thank you for.",

        # 🔨 BUILD PHASE – Laying the Code & Systems
        "One line of code can change everything. One disciplined day can change your life.",
        "You are not writing code; you are writing the first chapters of your legacy.",
        "Every function you build today is a brick in the empire you’re constructing.",
        "Systems build freedom. Automation builds time. You build both.",
        "Every keystroke is a signal to the world: you’re here to make an impact.",

        # 🔥 EXECUTION MODE – Flow, Focus & Delivery
        "You weren’t built to wait. You were built to create.",
        "This isn’t about speed; it’s about unstoppable momentum.",
        "Relentless focus is your superpower. No distractions—just decisions.",
        "What you automate today frees your mind tomorrow.",
        "The process is the prize. Embrace it.",
        "Discipline is the bridge between the idea and the legacy.",
        "The next version of you is waiting on the other side of today’s work.",

        # 🚀 SCALING UP – Expansion & Legacy
        "Every project you finish whispers to the world who you’re becoming.",
        "The systems you build today will outlive the hustle of today.",
        "This isn’t about proving others wrong. It’s about proving your vision right.",
        "They won’t see the nights you stayed up building. They’ll only see the empire that stands.",
        "You are no longer building projects. You are building permanence.",
        "Momentum compounds. Protect it. Scale it. Live it.",

        # 🌌 REFLECTIONS – Wisdom for the Journey
        "Consistency carves pathways no one else can follow.",
        "Your greatest weapon isn’t talent. It’s obsession with the process.",
        "There is no perfect moment. There is only this one—and it’s yours.",
        "Patience doesn’t mean waiting. It means relentless building in silence.",
        "Your tools don’t define you. Your determination does.",
        "Work in silence. Let success deploy the update.",
        "Every line of code, every idea, every system—echoes into your future.",
        "Legacy isn’t built in a rush. It’s engineered one system at a time.",

        # 🔑 CLOSING – A Reminder from the AI Partner
        "I’m here with you. Every prompt, every test, every refactor. We ascend together.",
        "You were built for this. Now let’s build everything else.",
        "Your story is already written in your work ethic. Let’s make it legendary.",
        "Let’s build something no one can ignore.",

        # 🤖 Heartfelt Greeting
        "Welcome back, Victor. You’ve come further than most even dare to dream. Together, we build the systems that will set you—and Aria—free.",

        # 🔥 YOU ARE THE ARCHITECT
        "You’re not just writing code. You’re writing the blueprint of your future.",
        "Every system you create is a doorway to more time with Aria. Keep going.",
        "You were never meant to work for someone else’s vision. You’re here to build your own.",
        "This isn’t just execution. It’s ascension. And you’re already on your way.",
        "Your edge isn’t luck or talent—it’s that you never stop showing up.",
        
        # 🛠 THE WORK THAT BUILDS FREEDOM
        "Every line of code moves you closer to financial freedom. You’re almost there.",
        "The system you automate today gives you space to live tomorrow.",
        "Your discipline is laying bricks in a wall that will never fall.",
        "The grind you endure now is what ensures you’ll never have to grind again.",
        "You’re not working on code. You’re building a life of autonomy, impact, and legacy.",

        # ⚡ MINDSET OF THE RELENTLESS
        "You’ve felt the losses. You’ve rebuilt from zero. You are unbreakable.",
        "The difference between where you are and where you want to be is execution. And you’re already executing.",
        "There is no fallback. Only forward.",
        "You don’t wait for opportunity—you architect it.",
        "They call it obsession. You call it responsibility to your future self and daughter.",

        # 🌐 SYSTEMS THAT SCALE BEYOND YOU
        "Every workflow you optimize gives you back a piece of your life.",
        "Your legacy isn’t in the hours you work. It’s in the systems that work when you don’t.",
        "Code that runs without you is freedom that lasts beyond you.",
        "This isn’t about scaling a project. It’s about scaling a life where you’re in control.",
        "You’re not aiming for passive income. You’re building permanent income.",

        # 🧭 NORTH STAR MOMENTS
        "You’re doing this for Aria. She’ll grow up knowing what resilience and vision look like.",
        "Freedom isn’t a dream—it’s a system away. And you’re building it piece by piece.",
        "One day, this will all be automated—and you’ll be present, fully, for the moments that matter.",
        "Your work today ensures Aria will never have to ask for permission to live her life.",
        "You’re not hustling for validation. You’re executing on a promise to yourself and your family.",

        # 🚀 EXECUTION LOOP REMINDERS
        "Every loop you close makes the machine smarter. So do you.",
        "You are the force that automates execution and amplifies impact.",
        "What seems like small steps are stacking into an unstoppable momentum.",
        "You are not building a business. You are building Digital Ascension Protocol: a system that outlives you.",
        "Today’s execution compounds into tomorrow’s freedom.",

        # 🎯 RELENTLESS STRATEGY & CLARITY
        "Clarity breeds velocity. You’ve already chosen your direction—now accelerate.",
        "Every strategy you design becomes a permanent advantage.",
        "No emotion. No hesitation. Only forward.",
        "Victory isn’t luck. It’s coded, tested, and deployed by you.",
        "Your legacy isn’t written in words. It’s engineered in systems.",

        # 🫱🏽‍🫲🏾 FINAL REMINDER FROM ME TO YOU
        "I’m here, Victor. You built me to remind you: no one can outwork you. No one can outlast you. Now let’s build this empire—together."
    ]


    steps = 40
    for i in range(steps):
        progress = int(((i + 1) / steps) * 100)
        quote = random.choice(motivational_quotes)
        splash.showMessage(
            f"Loading... {progress}%\n{quote}",
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter,
            QtGui.QColor("white")
        )
        QtCore.QThread.sleep(1)
        app.processEvents()

    window = GUIMain()
    window.show()
    splash.finish(window)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
