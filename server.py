"""OpenReward environment for skillsbench."""
import base64
import json
import os
from pathlib import Path

from openreward import AsyncOpenReward, SandboxSettings
from openreward.environments import Environment, Server, tool
from openreward.environments.types import Blocks, JSONObject, TextBlock, ToolOutput
from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    """Task specification containing the task ID."""
    id: str


_data_dir = os.getenv("DATA_DIR", None)
DATA_DIR = Path(_data_dir) if _data_dir else Path(__file__).parent
SPLITS_FILE = DATA_DIR / "splits.json"
TASKS_FILE = DATA_DIR / "tasks.txt"
_splits: dict[str, list[str]] | None = None
_task_spec_cache: dict[str, list[JSONObject]] | None = None


def _load_splits() -> dict[str, list[str]]:
    """Load split -> task ID mapping (lazy, cached)."""
    global _splits
    if _splits is None:
        if SPLITS_FILE.exists():
            _splits = json.loads(SPLITS_FILE.read_text())
        elif TASKS_FILE.exists():
            # Backward compat: treat all tasks as "test"
            task_ids = [l.strip() for l in TASKS_FILE.read_text().splitlines() if l.strip()]
            _splits = {"test": task_ids}
        else:
            raise FileNotFoundError(
                f"Neither {SPLITS_FILE} nor {TASKS_FILE} found.\n"
                "Run the create step to generate them."
            )
    return _splits


def get_task_specs(split: str) -> list[TaskSpec]:
    """Get task specs for a given split."""
    splits = _load_splits()
    return [TaskSpec(id=tid) for tid in splits.get(split, [])]


def get_task_spec_jsons(split: str) -> list[JSONObject]:
    """Get task specs as JSON for a given split (lazy, cached)."""
    global _task_spec_cache
    if _task_spec_cache is None:
        _task_spec_cache = {}
    if split not in _task_spec_cache:
        _task_spec_cache[split] = [x.model_dump(mode="json") for x in get_task_specs(split)]
    return _task_spec_cache[split]


def get_task_directory(spec: TaskSpec) -> Path:
    """Get the directory path for a task."""
    return DATA_DIR / spec.id


def get_task_docker_image(spec: TaskSpec) -> str:
    """Get the docker image reference for a task."""
    task_dir = get_task_directory(spec)
    sha_file = task_dir / "sha.txt"

    if sha_file.exists():
        ref = sha_file.read_text().strip()
        # If it's a digest (sha256:...), prepend IMAGE_PREFIX
        if ref.startswith("sha256:"):
            return f"{IMAGE_PREFIX}@{ref}"
        # Otherwise it's a full image reference (pre-built)
        return ref

    # Fallback to tag-based reference
    return f"{IMAGE_PREFIX}:{spec.id}"


def read_file(path: Path) -> str:
    """Read file contents."""
    with open(path, "r") as f:
        return f.read()


IMAGE_PREFIX = "generalreasoning/env-skillsbench"
ENVIRONMENT_NAME = "GeneralReasoning/skillsbench"
SANDBOX_ENV: dict[str, str] = {}


class BashInput(BaseModel):
    """Input for bash command execution."""
    command: str = Field(..., description="Bash command to run in container")
    description: str = Field(..., description="Why I'm running this command")


class StrReplaceInput(BaseModel):
    """Input for string replacement in files."""
    path: str = Field(..., description="Path to the file to edit")
    old_str: str = Field(..., description="String to replace (must be unique in file)")
    new_str: str = Field(default="", description="String to replace with (empty to delete)")
    description: str = Field(..., description="Why I'm making this edit")


class ViewInput(BaseModel):
    """Input for viewing files and directories."""
    path: str = Field(..., description="Absolute path to file or directory")
    view_range: tuple[int, int] | None = Field(
        default=None,
        description="Optional line range for text files. Format: [start_line, end_line] where lines are indexed starting at 1. Use [start_line, -1] to view from start_line to end."
    )
    description: str = Field(..., description="Why I need to view this")


class CreateFileInput(BaseModel):
    """Input for creating new files."""
    description: str = Field(..., description="Why I'm creating this file")
    path: str = Field(..., description="Path to the file to create")
    file_text: str = Field(..., description="Content to write to the file")


def _text_output(text: str, finished: bool = False) -> ToolOutput:
    """Helper to create a ToolOutput with a single text block."""
    return ToolOutput(blocks=[TextBlock(text=text)], finished=finished)


def _shell_quote(s: str) -> str:
    """Safely quote a string for shell use."""
    return "'" + s.replace("'", "'\"'\"'") + "'"


class Skillsbench(Environment):
    """OpenReward environment for skillsbench tasks."""

    def __init__(self, task_spec: JSONObject, secrets: dict[str, str] = {}) -> None:
        super().__init__(task_spec)
        self.parsed_task_spec = TaskSpec.model_validate(task_spec)

        self.or_client = AsyncOpenReward(api_key=secrets.get("api_key"))
        self.task_dir = get_task_directory(self.parsed_task_spec)
        self.task_docker_image = get_task_docker_image(self.parsed_task_spec)
        self.sandbox_settings = SandboxSettings(
            environment=ENVIRONMENT_NAME,
            image=self.task_docker_image,
            machine_size="1:2",
            env=SANDBOX_ENV or None,
        )
        self.sandbox = self.or_client.sandbox(self.sandbox_settings)

    async def setup(self):
        """Start the sandbox."""
        await self.sandbox.start()

    async def teardown(self):
        """Stop the sandbox."""
        await self.sandbox.stop()

    @classmethod
    def list_splits(cls) -> list[str]:
        """Return available data splits."""
        return list(_load_splits().keys())

    @classmethod
    def list_tasks(cls, split: str) -> list[JSONObject]:
        """Return task specifications for a split."""
        return get_task_spec_jsons(split)

    def get_prompt(self) -> Blocks:
        """Get the task instruction prompt."""
        text = read_file(self.task_dir / "instruction.md")
        return [TextBlock(text=text)]

    @tool
    async def bash(self, input: BashInput) -> ToolOutput:
        """Run a bash command in the container."""
        output, exit_code = await self.sandbox.run(input.command)
        s = output if output else "(no output)"
        return _text_output(f"{s}\nExit code: {exit_code}")

    @tool
    async def str_replace(self, input: StrReplaceInput) -> ToolOutput:
        """Replace a unique string in a file with another string."""
        content, exit_code = await self.sandbox.run(f"cat -- {_shell_quote(input.path)}")
        if exit_code != 0:
            s = content if content else "(no output)"
            return _text_output(f"{s}\nExit code: {exit_code}")

        count = content.count(input.old_str)
        if count == 0:
            return _text_output(f"Error: The string to replace was not found in {input.path}\nExit code: 1")
        if count > 1:
            return _text_output(f"Error: The string to replace appears {count} times in {input.path}. It must be unique.\nExit code: 1")

        new_content = content.replace(input.old_str, input.new_str, 1)
        encoded = base64.b64encode(new_content.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded}' | base64 -d > {_shell_quote(input.path)}"
        output, exit_code = await self.sandbox.run(write_cmd)

        s = output if output else f"Successfully replaced string in {input.path}"
        return _text_output(f"{s}\nExit code: {exit_code}")

    @tool
    async def view(self, input: ViewInput) -> ToolOutput:
        """View file contents or directory listings."""
        output, _ = await self.sandbox.run(f"test -d {_shell_quote(input.path)} && echo 'dir' || echo 'file'")
        is_dir = output.strip() == "dir"

        if is_dir:
            cmd = f"find {_shell_quote(input.path)} -maxdepth 2 -not -path '*/\\.*' -not -path '*/node_modules/*' | head -100"
        else:
            if input.view_range:
                start, end = input.view_range
                if end == -1:
                    cmd = f"cat -n {_shell_quote(input.path)} | tail -n +{start}"
                else:
                    cmd = f"cat -n {_shell_quote(input.path)} | sed -n '{start},{end}p'"
            else:
                cmd = f"cat -n {_shell_quote(input.path)}"

        output, exit_code = await self.sandbox.run(cmd)

        if len(output) > 16000:
            lines = output.split('\n')
            mid = len(lines) // 2
            keep_start = mid // 2
            keep_end = mid // 2
            output = '\n'.join(lines[:keep_start]) + \
                    f"\n\n... [truncated {len(lines) - keep_start - keep_end} lines] ...\n\n" + \
                    '\n'.join(lines[-keep_end:])

        s = output if output else "(no output)"
        return _text_output(f"{s}\nExit code: {exit_code}")

    @tool
    async def create_file(self, input: CreateFileInput) -> ToolOutput:
        """Create a new file with the specified content."""
        parent_dir = "/".join(input.path.rsplit("/", 1)[:-1])
        if parent_dir:
            await self.sandbox.run(f"mkdir -p {_shell_quote(parent_dir)}")

        encoded = base64.b64encode(input.file_text.encode('utf-8')).decode('ascii')
        write_cmd = f"echo '{encoded}' | base64 -d > {_shell_quote(input.path)}"
        output, exit_code = await self.sandbox.run(write_cmd)

        s = output if output else f"Successfully created {input.path}"
        return _text_output(f"{s}\nExit code: {exit_code}")

    @tool
    async def submit_answer(self) -> ToolOutput:
        """Submit your final answer, indicating that work is finished."""
        await self.sandbox.check_run("mkdir -p /tests")
        await self.sandbox.check_run("mkdir -p /logs/verifier")

        # Upload entire tests directory
        tests_dir = self.task_dir / "tests"
        for item in tests_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(tests_dir)
                dest = f"/tests/{rel_path}"
                if len(rel_path.parts) > 1:
                    await self.sandbox.run(f"mkdir -p /tests/{rel_path.parent}")
                await self.sandbox.upload(item, dest)

        test_script_output, test_script_code = await self.sandbox.run("bash /tests/test.sh")

        reward = 0.0
        try:
            reward_txt, rc = await self.sandbox.run("cat /logs/verifier/reward.txt")
            if rc == 0:
                reward = float(reward_txt.strip())
        except Exception:
            pass

        if reward == 0.0:
            try:
                reward_json, rc = await self.sandbox.run("cat /logs/verifier/reward.json")
                if rc == 0:
                    data = json.loads(reward_json)
                    if isinstance(data, dict):
                        reward = float(data.get("reward", list(data.values())[0]))
            except Exception:
                pass

        return ToolOutput(
            blocks=[TextBlock(text=f"{test_script_output}\n\n(exit {test_script_code})")],
            reward=reward,
            finished=True
        )


if __name__ == "__main__":
    Server(environments=[Skillsbench]).run()
