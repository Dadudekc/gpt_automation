import os
import ast
import json
import hashlib
import threading
import queue
from pathlib import Path
from typing import Dict, Union

# Try importing tree-sitter for Rust/JS/TS parsing
try:
    from tree_sitter import Language, Parser
except ImportError:
    Language = None
    Parser = None
    print("⚠️ tree-sitter not installed. Rust/JS/TS AST parsing will be partially disabled.")

CACHE_FILE = "dependency_cache.json"


class ProjectScanner:
    """
    A universal project scanner that:
      - Identifies Python, Rust, JavaScript, and TypeScript files.
      - Extracts functions, classes, and naive route definitions.
      - Caches file hashes to skip unchanged files.
      - Detects moved files by matching file hashes.
      - Writes a single JSON report (project_analysis.json) at the end.
      - Processes files asynchronously via background workers (BotWorker/MultibotManager).
      
    Extend or refactor `_save_report()` for modular outputs (e.g., routes.json, summary.md, etc.).
    """
    def __init__(self, project_root: Union[str, Path] = "."):
        """
        :param project_root: The root directory of the project to scan.
        """
        self.project_root = Path(project_root).resolve()
        self.analysis: Dict[str, Dict] = {}
        self.cache = self.load_cache()
        self.cache_lock = threading.Lock()  # Protect cache updates in a threaded context
        # Additional ignore directories provided interactively by the user.
        self.additional_ignore_dirs = set()

        # Initialize tree-sitter parsers for Rust and JS (if available)
        self.rust_parser = self._init_tree_sitter_language("rust")
        self.js_parser = self._init_tree_sitter_language("javascript")

    def _init_tree_sitter_language(self, lang_name: str):
        """
        Initializes and returns a Parser for the given language name (e.g. "rust", "javascript")
        if we have a compiled tree-sitter grammar.

        Adjust the grammar_paths to point to your actual .so/.dll/.dylib files.
        """
        if not Language or not Parser:
            print(f"⚠️ tree-sitter not available. Skipping {lang_name} parser.")
            return None

        # Example paths to compiled grammars - update these to match your environment
        grammar_paths = {
            "rust": "path/to/tree-sitter-rust.so",
            "javascript": "path/to/tree-sitter-javascript.so",
        }

        if lang_name not in grammar_paths:
            print(f"⚠️ No grammar path for {lang_name}. Skipping.")
            return None

        grammar_path = grammar_paths[lang_name]
        if not Path(grammar_path).exists():
            print(f"⚠️ {lang_name} grammar not found at {grammar_path}")
            return None

        try:
            lang_lib = Language(grammar_path, lang_name)
            parser = Parser()
            parser.set_language(lang_lib)
            return parser
        except Exception as e:
            print(f"⚠️ Failed to initialize tree-sitter {lang_name} parser: {e}")
            return None

    def load_cache(self) -> Dict:
        """
        Loads a JSON cache from disk if present.
        The cache stores file paths, hashes, etc. to skip re-analysis of unchanged files.
        """
        if Path(CACHE_FILE).exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_cache(self):
        """
        Writes the updated cache to disk so subsequent runs can detect unchanged or moved files quickly.
        """
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=4)

    def hash_file(self, file_path: Path) -> str:
        """
        Calculates an MD5 hash of a file's content.
        :param file_path: Path to the file to hash.
        :return: Hex digest string, or "" if an error occurs.
        """
        try:
            with file_path.open("rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def scan_project(self):
        """
        Orchestrates the project scan:
        - Finds Python, Rust, JS, and TS files using os.walk().
        - Excludes certain directories.
        - Detects moved files by comparing cached hashes.
        - Offloads file analysis to background workers.
        - Saves a single JSON report 'project_analysis.json'.
        """
        print(f"🔍 Scanning project: {self.project_root} ...")

        # Collect files using os.walk to capture all files (even in hidden directories)
        file_extensions = {'.py', '.rs', '.js', '.ts'}
        valid_files = []
        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)
            # Skip directories that should be excluded
            if self._should_exclude(root_path):
                continue
            for file in files:
                file_path = root_path / file
                if file_path.suffix.lower() in file_extensions and not self._should_exclude(file_path):
                    valid_files.append(file_path)
        
        print(f"📝 Found {len(valid_files)} valid files for analysis.")

        # Track old vs. new paths for cache update
        previous_files = set(self.cache.keys())
        current_files = {str(f.relative_to(self.project_root)) for f in valid_files}
        moved_files = {}
        missing_files = previous_files - current_files

        # Detect moved files by matching file hashes
        for old_path in previous_files:
            old_hash = self.cache.get(old_path, {}).get("hash")
            if not old_hash:
                continue
            for new_path in current_files:
                new_file = self.project_root / new_path
                if self.hash_file(new_file) == old_hash:
                    moved_files[old_path] = new_path
                    break

        # Remove truly missing files from cache
        for missing_file in missing_files:
            if missing_file not in moved_files:
                with self.cache_lock:
                    if missing_file in self.cache:
                        del self.cache[missing_file]

        # Update cache for moved files
        for old_path, new_path in moved_files.items():
            with self.cache_lock:
                self.cache[new_path] = self.cache.pop(old_path)

        # --- Asynchronous processing with BotWorker/MultibotManager ---
        print("⏱️  Processing files asynchronously...")
        num_workers = os.cpu_count() or 4
        manager = MultibotManager(scanner=self, num_workers=num_workers,
                                status_callback=lambda fp, res: print(f"Processed: {fp}"))
        for file_path in valid_files:
            manager.add_task(file_path)
        manager.wait_for_completion()
        manager.stop_workers()
        for result in manager.results_list:
            if result is not None:
                file_path, analysis_result = result
                self.analysis[file_path] = analysis_result

        # Write final report and cache
        self._save_report()
        self.save_cache()
        print(f"✅ Scan complete. Results saved to {self.project_root / 'project_analysis.json'}")


    def _should_exclude(self, file_path: Path) -> bool:
        """
        Excludes files that are located inside certain directories.
        Combines a default list of excluded directory names with any additional
        directories specified by the user. For additional directories, if the user
        provides an absolute path, the file's absolute path is checked against it.
        Otherwise, the path is assumed to be relative to the project root.
        """
        default_exclude_dirs = {"venv", "__pycache__", "node_modules", "migrations", "build", "target", ".git", "coverage", "chrome_profile"}
        file_abs = file_path.resolve()
        for ignore in self.additional_ignore_dirs:
            ignore_path = Path(ignore)
            if not ignore_path.is_absolute():
                ignore_path = (self.project_root / ignore_path).resolve()
            try:
                file_abs.relative_to(ignore_path)
                return True
            except ValueError:
                continue
        if any(excluded in file_path.parts for excluded in default_exclude_dirs):
            return True
        return False

    def _process_file(self, file_path: Path):
        """
        Handles analysis of a single file:
          - Skips if the file is unchanged (hash match).
          - Reads its source, dispatches to the appropriate parser.
          - Updates the cache with the new hash.
        Returns a tuple (relative_path, analysis_result) or None on error/skip.
        """
        file_hash = self.hash_file(file_path)
        relative_path = str(file_path.relative_to(self.project_root))
        with self.cache_lock:
            if relative_path in self.cache and self.cache[relative_path]["hash"] == file_hash:
                return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            analysis_result = self._analyze_file_by_language(file_path, source_code)
            with self.cache_lock:
                self.cache[relative_path] = {"hash": file_hash}
            return (relative_path, analysis_result)
        except Exception as e:
            print(f"❌ Error analyzing {file_path}: {e}")
            return None

    def _analyze_file_by_language(self, file_path: Path, source_code: str) -> Dict:
        """
        Dispatches analysis based on file extension and available parsers.
        Returns a dictionary with keys like:
          {
            "language": "python"|"rust"|"javascript"|...,
            "functions": [...],
            "classes": {...},
            "routes": [...],
            "complexity": <int>
          }
        """
        suffix = file_path.suffix.lower()
        if suffix == ".py":
            data = self._analyze_python(source_code)
            complexity = len(data["functions"]) + sum(len(methods) for methods in data["classes"].values())
            return {
                "language": "python",
                "functions": data["functions"],
                "classes": data["classes"],
                "routes": data.get("routes", []),
                "complexity": complexity,
            }
        elif suffix == ".rs" and self.rust_parser:
            data = self._analyze_rust(source_code)
            complexity = len(data["functions"]) + sum(len(methods) for methods in data["classes"].values())
            return {
                "language": "rust",
                "functions": data["functions"],
                "classes": data["classes"],
                "complexity": complexity,
            }
        elif suffix in [".js", ".ts"] and self.js_parser:
            data = self._analyze_javascript(source_code)
            complexity = len(data["functions"]) + sum(len(methods) for methods in data["classes"].values())
            return {
                "language": "javascript",
                "functions": data["functions"],
                "classes": data["classes"],
                "routes": data["routes"],
                "complexity": complexity,
            }
        else:
            return {"language": suffix, "functions": [], "classes": {}, "routes": [], "complexity": 0}

    def _analyze_python(self, source_code: str) -> Dict:
        """
        Uses Python's ast to extract:
          - function names
          - class names and method names
          - Naive route detection (Flask-like decorators)
        """
        tree = ast.parse(source_code)
        functions = []
        classes = {}
        routes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and hasattr(decorator.func, 'attr'):
                        func_attr = decorator.func.attr.lower()
                        if func_attr in {"route", "get", "post", "put", "delete", "patch"}:
                            path_arg = "/unknown"
                            methods = [func_attr.upper()]
                            if decorator.args:
                                arg0 = decorator.args[0]
                                if isinstance(arg0, ast.Str):
                                    path_arg = arg0.s
                            for kw in decorator.keywords:
                                if kw.arg == "methods" and isinstance(kw.value, ast.List):
                                    extracted_methods = []
                                    for elt in kw.value.elts:
                                        if isinstance(elt, ast.Str):
                                            extracted_methods.append(elt.s.upper())
                                    if extracted_methods:
                                        methods = extracted_methods
                            for m in methods:
                                routes.append({
                                    "function": node.name,
                                    "method": m,
                                    "path": path_arg
                                })
            elif isinstance(node, ast.ClassDef):
                method_names = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                classes[node.name] = method_names
        return {"functions": functions, "classes": classes, "routes": routes}

    def _analyze_rust(self, source_code: str) -> Dict:
        """
        Uses tree-sitter to extract functions and struct methods from Rust code.
        """
        if not self.rust_parser:
            return {"functions": [], "classes": {}}
        tree = self.rust_parser.parse(bytes(source_code, "utf-8"))
        functions = []
        classes = {}

        def _traverse(node):
            if node.type == "function_item":
                fn_name_node = node.child_by_field_name("name")
                if fn_name_node:
                    functions.append(fn_name_node.text.decode("utf-8"))
            elif node.type == "struct_item":
                struct_name_node = node.child_by_field_name("name")
                if struct_name_node:
                    classes[struct_name_node.text.decode("utf-8")] = []
            elif node.type == "impl_item":
                impl_type_node = node.child_by_field_name("type")
                if impl_type_node:
                    impl_name = impl_type_node.text.decode("utf-8")
                    if impl_name not in classes:
                        classes[impl_name] = []
                    for child in node.children:
                        if child.type == "function_item":
                            method_node = child.child_by_field_name("name")
                            if method_node:
                                classes[impl_name].append(method_node.text.decode("utf-8"))
            for child in node.children:
                _traverse(child)

        _traverse(tree.root_node)
        return {"functions": functions, "classes": classes}

    def _analyze_javascript(self, source_code: str) -> Dict:
        """
        Uses tree-sitter to extract functions, classes, and basic Express-style routes from JavaScript/TypeScript code.
        """
        if not self.js_parser:
            return {"functions": [], "classes": {}, "routes": []}
        tree = self.js_parser.parse(bytes(source_code, "utf-8"))
        root = tree.root_node
        functions = []
        classes = {}
        routes = []

        def get_node_text(node):
            return node.text.decode("utf-8")

        def _traverse(node):
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    functions.append(get_node_text(name_node))
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = get_node_text(name_node)
                    classes[cls_name] = []
            elif node.type == "lexical_declaration":
                for child in node.children:
                    if child.type == "variable_declarator":
                        name_node = child.child_by_field_name("name")
                        value_node = child.child_by_field_name("value")
                        if name_node and value_node and value_node.type == "arrow_function":
                            functions.append(get_node_text(name_node))
            elif node.type == "call_expression":
                if node.child_count >= 2:
                    callee_node = node.child_by_field_name("function")
                    args_node = node.child_by_field_name("arguments")
                    if callee_node:
                        callee_text = get_node_text(callee_node)
                        parts = callee_text.split(".")
                        if len(parts) == 2:
                            obj, method = parts
                            if method.lower() in {"get", "post", "put", "delete", "patch"}:
                                path_str = "/unknown"
                                if args_node and args_node.child_count > 0:
                                    first_arg = args_node.child(0)
                                    if first_arg.type == "string":
                                        path_str = get_node_text(first_arg).strip('"\'')
                                routes.append({
                                    "object": obj,
                                    "method": method.upper(),
                                    "path": path_str
                                })
            for child in node.children:
                _traverse(child)

        _traverse(root)
        return {"functions": functions, "classes": classes, "routes": routes}

    def _save_report(self):
        """
        Writes the final analysis dictionary to a JSON file.
        """
        report_path = self.project_root / "project_analysis.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.analysis, f, indent=4)


# ----- Asynchronous Task Queue Components -----
class BotWorker(threading.Thread):
    """
    A background worker that continuously pulls file tasks from a queue,
    processes them using the scanner’s _process_file method, and stores results.
    """
    def __init__(self, task_queue: queue.Queue, results_list: list, scanner: ProjectScanner, status_callback=None):
        threading.Thread.__init__(self)
        self.task_queue = task_queue
        self.results_list = results_list
        self.scanner = scanner
        self.status_callback = status_callback
        self.daemon = True
        self.start()

    def run(self):
        while True:
            file_path = self.task_queue.get()
            if file_path is None:
                break
            result = self.scanner._process_file(file_path)
            if result is not None:
                self.results_list.append(result)
            if self.status_callback:
                self.status_callback(file_path, result)
            self.task_queue.task_done()


class MultibotManager:
    """
    Manages a pool of BotWorker threads.
    """
    def __init__(self, scanner: ProjectScanner, num_workers=4, status_callback=None):
        self.task_queue = queue.Queue()
        self.results_list = []
        self.scanner = scanner
        self.status_callback = status_callback
        self.workers = [
            BotWorker(self.task_queue, self.results_list, scanner, status_callback)
            for _ in range(num_workers)
        ]

    def add_task(self, file_path: Path):
        self.task_queue.put(file_path)

    def wait_for_completion(self):
        self.task_queue.join()

    def stop_workers(self):
        for _ in self.workers:
            self.task_queue.put(None)


# ----- Interactive Entry Point -----
if __name__ == "__main__":
    project_root = input("Enter the project root directory to scan (default '.'): ").strip() or "."
    ignore_input = input("Enter additional directories to ignore (comma separated, or leave empty): ").strip()
    additional_ignore_dirs = {d.strip() for d in ignore_input.split(",") if d.strip()} if ignore_input else set()

    scanner = ProjectScanner(project_root=project_root)
    scanner.additional_ignore_dirs = additional_ignore_dirs
    scanner.scan_project()
