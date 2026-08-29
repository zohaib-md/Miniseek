import os
import json
import inspect
import subprocess
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional
from miniseek.memory import MemoryStore

class WorkspaceSandbox:
    """Controls and restricts file and command operations to the designated MiniSeek workspace."""
    
    def __init__(self, workspace_path: str = "/Users/mohammadzohaib/Desktop/Miniseek/workspace"):
        self.workspace_dir = Path(workspace_path).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def validate_path(self, relative_or_abs_path: str) -> Path:
        """Validates that a target path remains strictly within the workspace boundary."""
        p_str = relative_or_abs_path.strip()
        # If model generated a simulated path like /home/user/Workspace/foo.py, extract relative path
        if p_str.startswith("/home/") or p_str.startswith("/root/") or p_str.startswith("/workspace/"):
            parts = Path(p_str).parts
            if "Workspace" in parts:
                idx = parts.index("Workspace")
                p_str = str(Path(*parts[idx+1:]))
            elif "workspace" in parts:
                idx = parts.index("workspace")
                p_str = str(Path(*parts[idx+1:]))
            else:
                p_str = Path(p_str).name

        target_path = (self.workspace_dir / p_str).resolve()
        if not str(target_path).startswith(str(self.workspace_dir)):
            raise PermissionError(f"Security Sandbox Error: Access to path '{relative_or_abs_path}' outside workspace '{self.workspace_dir}' is forbidden.")
        return target_path

class ToolRegistry:
    """Registry for agent tools with input schemas, alias resolution, memory tools, and safe execution."""
    
    ALIASES = {
        "create_file": "write_file",
        "create_module": "write_file",
        "edit_file": "write_file",
        "save_file": "write_file",
        "exec": "run_command",
        "execute": "run_command",
        "execute_command": "run_command",
        "run": "run_command",
        "cmd": "run_command",
        "ls": "list_files",
        "dir": "list_files",
        "cat": "read_file",
        "view_file": "read_file",
        "remember": "save_memory",
        "learn": "save_memory"
    }

    def __init__(self, sandbox: WorkspaceSandbox, memory: Optional[MemoryStore] = None):
        self.sandbox = sandbox
        self.memory = memory or MemoryStore()
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], func: Callable):
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "func": func
        }

    def _register_default_tools(self):
        # 1. list_files
        self.register_tool(
            name="list_files",
            description="List all files and subdirectories inside the workspace sandbox.",
            parameters={"type": "object", "properties": {}},
            func=self.list_files
        )

        # 2. read_file
        self.register_tool(
            name="read_file",
            description="Read the text content of a file located within the workspace sandbox.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path of the file to read."}
                },
                "required": ["path"]
            },
            func=self.read_file
        )

        # 3. write_file
        self.register_tool(
            name="write_file",
            description="Write or update text content into a file located within the workspace sandbox.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path of the file to write."},
                    "content": {"type": "string", "description": "Text content to write into the file."}
                },
                "required": ["path", "content"]
            },
            func=self.write_file
        )

        # 4. run_command
        self.register_tool(
            name="run_command",
            description="Execute a shell command inside the workspace directory (e.g. 'pytest test_strings.py', 'python3 main.py').",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command line string to execute."}
                },
                "required": ["command"]
            },
            func=self.run_command
        )

        # 5. save_memory
        self.register_tool(
            name="save_memory",
            description="Save a key fact, convention, or learning into persistent memory across tasks.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category (e.g. 'conventions', 'learnings', 'environment')."},
                    "fact": {"type": "string", "description": "The exact fact or guideline to remember."}
                },
                "required": ["category", "fact"]
            },
            func=self.save_memory
        )

        # 6. recall_memory
        self.register_tool(
            name="recall_memory",
            description="Recall persistent memories and learnings stored from previous tasks.",
            parameters={"type": "object", "properties": {}},
            func=self.recall_memory
        )

    def list_files(self) -> List[str]:
        """Lists files and directories inside the workspace sandbox."""
        items = []
        for root, dirs, files in os.walk(self.sandbox.workspace_dir):
            rel_root = Path(root).relative_to(self.sandbox.workspace_dir)
            for d in dirs:
                if rel_root != Path("."):
                    items.append(str(rel_root / d) + "/")
                else:
                    items.append(f"{d}/")
            for f in files:
                if rel_root != Path("."):
                    items.append(str(rel_root / f))
                else:
                    items.append(f)
        return sorted(items)

    def read_file(self, path: str) -> str:
        """Reads text file from workspace sandbox."""
        target_file = self.sandbox.validate_path(path)
        if not target_file.exists():
            return f"Error: File '{path}' does not exist."
        if not target_file.is_file():
            return f"Error: Path '{path}' is a directory, not a file."

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file '{path}': {e}"

    def write_file(self, path: str, content: str = "") -> str:
        """Writes text file into workspace sandbox."""
        target_file = self.sandbox.validate_path(path)
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)
            return f"File '{path}' successfully written ({len(content)} bytes)."
        except Exception as e:
            return f"Error writing file '{path}': {e}"

    def run_command(self, command: str) -> str:
        """Executes shell command safely constrained to workspace directory."""
        forbidden_terms = ["rm -rf /", "rm -rf ~", "sudo", "shutdown", "reboot"]
        for term in forbidden_terms:
            if term in command:
                return f"Security Restriction: Command '{command}' contains forbidden keyword '{term}'."

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=self.sandbox.workspace_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            output = res.stdout
            if res.stderr:
                output += f"\n[STDERR]\n{res.stderr}"
            if res.returncode != 0:
                output += f"\n[EXIT CODE: {res.returncode}]"
            return output.strip() if output.strip() else "(No output returned)"
        except subprocess.TimeoutExpired:
            return "Error: Command execution timed out after 15 seconds."
        except Exception as e:
            return f"Error executing command '{command}': {e}"

    def save_memory(self, category: str, fact: str) -> str:
        """Saves fact into persistent memory."""
        self.memory.add_fact(category, fact)
        return f"Memory saved under category '{category}': {fact}"

    def recall_memory(self) -> str:
        """Returns active persistent memory summary."""
        return self.memory.get_summary()

    def normalize_action_and_args(self, action: str, arguments: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Resolves synonymous action aliases and normalizes parameter keys."""
        resolved_action = self.ALIASES.get(action.lower().strip(), action.strip())
        normalized_args = dict(arguments)

        # Normalize path parameter aliases for write_file / read_file
        if resolved_action in ["write_file", "read_file"]:
            for alt_key in ["file", "filename", "file_name", "module_name", "target"]:
                if alt_key in normalized_args and "path" not in normalized_args:
                    val = normalized_args.pop(alt_key)
                    if not val.endswith(".py") and alt_key == "module_name":
                        val += ".py"
                    normalized_args["path"] = val

            # Normalize content parameter aliases for write_file
            if resolved_action == "write_file":
                for alt_content in ["code", "text", "body", "data"]:
                    if alt_content in normalized_args and "content" not in normalized_args:
                        normalized_args["content"] = normalized_args.pop(alt_content)
                if "content" not in normalized_args:
                    normalized_args["content"] = ""

        # Normalize command parameter aliases for run_command
        if resolved_action == "run_command":
            for alt_cmd in ["cmd", "shell", "script"]:
                if alt_cmd in normalized_args and "command" not in normalized_args:
                    normalized_args["command"] = normalized_args.pop(alt_cmd)

        return resolved_action, normalized_args

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        resolved_name, clean_args = self.normalize_action_and_args(tool_name, arguments)
        if resolved_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' is not registered. Available tools: {list(self.tools.keys())}")
        
        target_func = self.tools[resolved_name]["func"]
        sig = inspect.signature(target_func)
        valid_args = {k: v for k, v in clean_args.items() if k in sig.parameters}
        return target_func(**valid_args)

    def get_tool_descriptions(self) -> str:
        descriptions = []
        for name, info in self.tools.items():
            descriptions.append(f"- Tool: {name}\n  Description: {info['description']}\n  Parameters: {json.dumps(info['parameters'])}")
        return "\n".join(descriptions)
