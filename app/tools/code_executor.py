"""Code execution tool for the developer agent."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from langchain_core.tools import tool

from app.config import get_settings


def _ensure_workspace() -> Path:
    """Ensure the workspace directory exists."""
    workspace = Path(get_settings().workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@tool
def execute_python(code: str) -> str:
    """Execute Python code in a sandboxed environment and return the output.

    Args:
        code: Python code to execute.
    """
    workspace = _ensure_workspace()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=workspace, delete=False
        ) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                ["python3", f.name],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=workspace,
            )
        os.unlink(f.name)

        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        if result.returncode != 0:
            output += f"Exit code: {result.returncode}\n"
        return output if output.strip() else "Code executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (30s limit)."
    except Exception as e:
        return f"Execution error: {str(e)}"


@tool
def execute_shell(command: str) -> str:
    """Execute a shell command and return the output. Use for npm, git, etc.

    Args:
        command: Shell command to execute.
    """
    workspace = _ensure_workspace()
    # Block dangerous commands
    blocked = ["rm -rf /", "sudo", "mkfs", "dd if=", ":(){", "fork"]
    for b in blocked:
        if b in command:
            return f"Error: Command contains blocked pattern '{b}'."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=workspace,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output[:10000] if output.strip() else "Command executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (60s limit)."
    except Exception as e:
        return f"Execution error: {str(e)}"


@tool
def write_file(filepath: str, content: str) -> str:
    """Write content to a file in the workspace.

    Args:
        filepath: Relative path within the workspace.
        content: Content to write to the file.
    """
    workspace = _ensure_workspace()
    try:
        full_path = workspace / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return f"File written successfully: {full_path}"
    except Exception as e:
        return f"Write error: {str(e)}"


@tool
def read_file(filepath: str) -> str:
    """Read content from a file in the workspace.

    Args:
        filepath: Relative path within the workspace.
    """
    workspace = _ensure_workspace()
    try:
        full_path = workspace / filepath
        if not full_path.exists():
            return f"Error: File not found: {filepath}"
        content = full_path.read_text()
        if len(content) > 20000:
            content = content[:20000] + "\n\n... [Content truncated]"
        return content
    except Exception as e:
        return f"Read error: {str(e)}"


@tool
def list_files(directory: str = ".") -> str:
    """List files in a directory within the workspace.

    Args:
        directory: Relative directory path within the workspace.
    """
    workspace = _ensure_workspace()
    try:
        target = workspace / directory
        if not target.exists():
            return f"Error: Directory not found: {directory}"

        entries = []
        for item in sorted(target.iterdir()):
            prefix = "[DIR]" if item.is_dir() else "[FILE]"
            entries.append(f"  {prefix} {item.name}")

        return f"Contents of {directory}:\n" + "\n".join(entries) if entries else "Empty directory."
    except Exception as e:
        return f"List error: {str(e)}"
