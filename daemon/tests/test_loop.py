"""Offline Phase-1 verification: drive the CodeAct loop with a fake model so we
prove the loop executes our tools on the host and terminates — no API key needed.
"""

from __future__ import annotations

from pathlib import Path

from smolagents import CodeAgent
from smolagents.models import ChatMessage, TokenUsage

from echlon.tools import build_tools


class FakeModel:
    """Returns scripted CodeAct steps; mimics smolagents' model.generate contract."""

    def __init__(self, steps: list[str]) -> None:
        self._steps = steps
        self._i = 0

    def generate(self, messages, stop_sequences=None, response_format=None,
                 tools_to_call_from=None, **kwargs) -> ChatMessage:
        content = self._steps[min(self._i, len(self._steps) - 1)]
        self._i += 1
        return ChatMessage(
            role="assistant",
            content=content,
            tool_calls=None,
            raw={},
            token_usage=TokenUsage(input_tokens=0, output_tokens=0),
        )


def test_loop_executes_tools_on_host(tmp_path: Path) -> None:
    tools = build_tools(tmp_path)

    step1 = (
        "<code>\n"
        'todo_write(content="- [x] create script\\n- [ ] run it")\n'
        "file_write(path=\"hello.py\", content=\"print('hi from echlon')\")\n"
        'out = shell_exec(command="python hello.py")\n'
        "print(out)\n"
        "</code>"
    )
    step2 = "<code>\nfinal_answer(\"created and ran hello.py\")\n</code>"

    agent = CodeAgent(
        tools=tools,
        model=FakeModel([step1, step2]),
        additional_authorized_imports=["*"],
        planning_interval=None,
        max_steps=5,
    )

    result = agent.run("Create hello.py, run it, then finish.")

    # The loop actually touched the real filesystem and ran the script.
    assert (tmp_path / "hello.py").read_text() == "print('hi from echlon')"
    assert (tmp_path / "todo.md").exists()
    assert "create script" in (tmp_path / "todo.md").read_text()
    assert "ran hello.py" in str(result)
