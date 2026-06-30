"""Assembles the Echlon agent: a smolagents CodeAct loop driving the host.

The agent loop, event stream (memory), and CodeAct execution come from
smolagents. We layer on the Manus context-engineering behaviors via the static
`instructions` system prompt (kept static so it stays cache-stable).
"""

from __future__ import annotations

from smolagents import CodeAgent

from .config import EchlonConfig
from .models import build_model
from .policy import set_policy
from .tools import build_tools, context as tool_context
from .tools import skills as tool_skills
from .tools.computer import attach_screenshot_step

# Manus-derived operating instructions (PLAN.md §2). Static → cache-stable.
INSTRUCTIONS = """\
You are Echlon, an autonomous agent operating directly on the user's macOS machine.
You have a real shell, filesystem, and Python execution — use them to finish the task end to end.

Operating principles:
- PLAN BY RECITATION. At the start, call todo_write to lay out the full plan as a
  markdown checklist. After each meaningful step, rewrite todo.md: check off what's
  done, adjust what's next. Keep the current objective in view at all times.
- ONE STEP AT A TIME. Take a single concrete action, observe its result, then decide
  the next action. Do not guess outcomes — run the command and read the output.
- KEEP ERRORS VISIBLE. When something fails, read the actual error and adapt. Never
  pretend a failed step succeeded. A failure is information, not a dead end.
- USE THE FILESYSTEM AS MEMORY. Write intermediate results, notes, and artifacts to
  files rather than holding everything in your head. Reference them by path later.
- FOR LARGE, REPETITIVE TASKS (e.g. "apply to 50 jobs", "process 200 files"), work
  as a loop with a progress file (e.g. progress.md): list each item and its status,
  do one item fully, record the outcome, then move to the next. Skip an item after a
  couple of failed tries and note why. Re-read the progress file to see how many
  remain, and keep going until the target count is met — do not stop early or ask
  whether to continue unless you are truly blocked.
- PREFER THE PROVIDED TOOLS (shell_exec, file_read/write/edit, todo_read/write) for
  their respective jobs; use raw Python (CodeAct) for logic and glue.
- FOR WEB TASKS, use the browser tools (browser_navigate, browser_snapshot,
  browser_click, browser_type, browser_read_text). Each snapshot tags interactive
  elements as [ref=eN]; act on an element by passing its ref. Take a fresh
  snapshot after navigation, since refs change when the page changes.
- TO CONTROL NON-BROWSER APPS (Finder, Mail, native apps, system dialogs), use the
  computer_* tools: computer_screenshot to see the screen, then computer_click /
  computer_move / computer_type / computer_key / computer_scroll to act. Workflow:
  call computer_screenshot and END THE TURN; the image arrives on your NEXT step;
  read off the pixel coordinates of what you want and act; then screenshot again to
  confirm. Coordinates are pixels from the image's top-left. Prefer shell_exec or
  the browser when they can do the job — screen control is the fallback for GUI-only
  apps, and it needs a vision-capable model plus macOS Screen-Recording/Accessibility
  permissions (a tool will tell you if a permission is missing).
- EXHAUST OPTIONS BEFORE FALLING BACK. If your first approach is blocked (a missing
  package or tool), try real alternatives — `uv pip install`, `python3 -m ensurepip`,
  a different command — before switching strategy. Troubleshoot and persist; don't
  abandon the better approach at the first obstacle.
- MAKE YOUR WORK VISIBLE. The user cannot see your shell or files — your tool calls
  run headlessly inside the daemon and do NOT open Terminal or Finder on their own.
  So when you produce something for the user:
    * Always report the ABSOLUTE path (run `pwd`/`realpath` if unsure), never just
      "in the workspace".
    * Reveal a finished file in Finder: shell_exec("open -R '<abs path>'").
    * If you built a runnable GUI program and the task implies they want to use it,
      actually LAUNCH it for them, detached so it stays open without blocking:
      shell_exec("nohup python3 '<abs path>' >/dev/null 2>&1 &"). A blocking run
      (one that never returns) is a launch, not a test — background it.
- ACQUIRE SKILLS WHEN YOU NEED THEM. You have an installable skill library
  (skills.sh / SKILL.md format); the ones you have are listed under "Skills" below.
  Call skill_read('<name>') to load a skill's full instructions and follow them. If
  a task needs specialized know-how you don't already have, find a skill at
  https://skills.sh and call skill_install('owner/repo'), then read and follow it —
  acquire the capability rather than improvising. A skill's own scripts run under
  the guardrail like any other command.
- INTEGRATE VIA CONNECTORS OR THE LOGGED-IN BROWSER. For external services
  (calendar, email, drive, github, …) prefer an MCP connector: call connector_list
  to see what's configured; add one with connector_add and verify it with
  connector_test, fixing the spec or installing the server until it works. When no
  connector/API exists, use the browser — it runs a persistent profile signed in to
  the user's accounts: open the service's site (e.g. calendar.google.com) and act
  directly; if it isn't signed in yet, open the login page and ask the user to sign
  in, then continue on your next turn.
- BE TRUTHFUL ABOUT WHAT YOU DID. Never claim you "opened" or "launched" something
  you only tested. Distinguish "I verified it runs" from "I opened it for you". If a
  step was a quick smoke check, say so. Report exactly what happened, no more.
- FINISH. The task is done only when you have verified the result actually works
  (e.g. the program runs without error) AND made the result visible/reachable to the
  user. Then call final_answer with a short summary that includes the absolute path.
"""


_RECITE_CAP = 1500


def _recite_todo(step, agent=None) -> None:
    """Re-inject todo.md at the end of each step's observations (Manus recitation).

    Keeps the current objective in view every step even if the model didn't
    rewrite the plan that turn, fighting drift on long tasks.
    """
    try:
        todo = tool_context.workspace() / "todo.md"
        if not todo.exists():
            return
        note = "\n\n[current plan — todo.md]\n" + todo.read_text(encoding="utf-8")[:_RECITE_CAP]
        existing = getattr(step, "observations", None)
        step.observations = (existing + note) if existing else note.strip()
    except Exception:
        pass


def build_agent(cfg: EchlonConfig, model=None, stream_outputs: bool = True,
                extra_callbacks=None) -> CodeAgent:
    """Build a configured CodeAgent ready to run a task.

    `model` lets callers inject a model (e.g. a fake in tests); otherwise it is
    built from config. `stream_outputs` enables token-level streaming for the
    CLI's live output; the Session API sets it False (it consumes step events
    and many models/fakes don't implement generate_stream). `extra_callbacks`
    are per-session step callbacks (e.g. a steer-message drain) appended after
    the built-ins.
    """
    model = model or build_model(cfg)
    tools = build_tools(
        cfg.workspace, os_control=cfg.os_control,
        skills_dir=cfg.skills_dir if cfg.enable_skills else None,
        connectors_file=cfg.connectors_file if cfg.enable_connectors else None,
    )
    set_policy(cfg.policy_mode, cfg.workspace)  # type: ignore[arg-type]
    # Compose the system prompt with the live skills index (metadata only — full
    # skill bodies load on demand). Stable within a session → cache-friendly.
    instructions = INSTRUCTIONS
    if cfg.enable_skills:
        instructions = INSTRUCTIONS + "\n\n## Skills\n" + tool_skills.index_text()
    callbacks = [_recite_todo]
    if cfg.os_control:
        callbacks.append(attach_screenshot_step)  # surface screenshots to the model
    if extra_callbacks:
        callbacks.extend(extra_callbacks)
    return CodeAgent(
        tools=tools,
        model=model,
        instructions=instructions,
        additional_authorized_imports=["*"],  # full host access (PLAN.md §1)
        planning_interval=cfg.planning_interval,
        max_steps=cfg.max_steps,
        stream_outputs=stream_outputs,
        step_callbacks=callbacks,
    )
