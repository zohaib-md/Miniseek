import json
import re
import time
from typing import Dict, Any, List
from miniseek.llm import LLMProvider
from miniseek.tools import ToolRegistry
from miniseek.memory import MemoryStore

# ─────────────────────────────────────────────────────────────
# Shared System Prompt Components
# ─────────────────────────────────────────────────────────────

TOOL_RULES = """CRITICAL RULES:
1. You MUST respond with a SINGLE valid JSON object on EVERY turn. Never add conversational text before or after the JSON block.
2. To create or update a file, ALWAYS use `write_file` with `path` and `content`.
3. To execute tests, use `run_command` with `python3 -m unittest <test_file.py>` or `pytest <test_file.py>`.
4. Put implementation code in implementation files (e.g. `string_utils.py`) and test code in test files (e.g. `test_strings.py`).
5. You have access to persistent memory (`save_memory`, `recall_memory`). Remember key learnings across tasks.
6. In `write_file`, use single quotes inside code strings to keep JSON valid.
"""

ACTION_FORMAT = """Format for calling a tool:
```json
{{
    "thought": "Brief explanation of what tool you are calling and why",
    "action": "<tool_name>",
    "action_input": {{
        "<parameter_name>": "<parameter_value>"
    }}
}}
```

Format for final answer:
```json
{{
    "thought": "Reasoning about why the task is completed",
    "action": "final_answer",
    "action_input": {{
        "answer": "<complete answer summarizing all specific findings or results>"
    }}
}}
```
"""

# ─────────────────────────────────────────────────────────────
# Agent A: ReAct (Standard)
# ─────────────────────────────────────────────────────────────

REACT_SYSTEM_PROMPT = """You are MiniSeek, a lightweight local AI agent operating inside a sandboxed workspace.
You accomplish tasks by calling tools step-by-step.

PERSISTENT MEMORY & KNOWN FACTS:
{{memory_summary}}

Available Tools:
{{tool_descriptions}}

""" + TOOL_RULES + "\n" + ACTION_FORMAT

# ─────────────────────────────────────────────────────────────
# Agent B: Plan-First
# ─────────────────────────────────────────────────────────────

PLAN_PHASE_SYSTEM_PROMPT = """You are MiniSeek, a lightweight local AI agent operating inside a sandboxed workspace.
You are in the PLANNING phase. You must create a step-by-step plan to complete the task.

PERSISTENT MEMORY & KNOWN FACTS:
{{memory_summary}}

Available Tools:
{{tool_descriptions}}

You MUST respond with a SINGLE valid JSON object containing your numbered plan:
```json
{{
    "plan": [
        "Step 1: Use write_file to create <source_file.py>",
        "Step 2: Use write_file to create <test_file.py>",
        "Step 3: Use run_command to execute <test_file.py>"
    ]
}}
```

Keep the plan short (3-5 steps). Use only tools from Available Tools (`write_file`, `read_file`, `run_command`, `list_files`, `save_memory`).
Do NOT call any tools yet. Only output the plan.
"""

EXECUTE_PHASE_SYSTEM_PROMPT = """You are MiniSeek, a lightweight local AI agent operating inside a sandboxed workspace.
You are in the EXECUTION phase. Follow your plan step by step.

Your Plan:
{{plan_text}}

PERSISTENT MEMORY & KNOWN FACTS:
{{memory_summary}}

Available Tools:
{{tool_descriptions}}

Execute the NEXT incomplete step from your plan. Mark which plan step you are executing in your thought.

""" + TOOL_RULES + "\n" + ACTION_FORMAT


# ─────────────────────────────────────────────────────────────
# Shared JSON Parser
# ─────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> Dict[str, Any]:
    """Extracts and parses a JSON object from model output text."""
    cleaned = text.strip()

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if json_match:
        candidate = json_match.group(1)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            try:
                fixed = re.sub(r'"""(.*?)"""', r"'\1'", candidate, flags=re.DOTALL)
                return json.loads(fixed)
            except Exception:
                pass

    return {
        "thought": "Failed to parse JSON from response.",
        "action": "error",
        "action_input": {"raw_response": text, "error": "Non-JSON model output."}
    }


# ─────────────────────────────────────────────────────────────
# Shared Execution Loop with Loop Detection & Alias Support
# ─────────────────────────────────────────────────────────────

def execute_loop(
    llm: LLMProvider,
    tools: ToolRegistry,
    system_prompt: str,
    messages: List[Dict[str, str]],
    max_steps: int,
    label: str,
    task_text: str
) -> Dict[str, Any]:
    """Runs the Reason→Act→Observe loop with loop detection and error recovery."""

    start_time = time.time()
    tool_calls_count = 0
    failed_tool_calls = 0

    print(f"\n────────────────────────────────────")
    print(f"MINISEEK [{label}] OBSERVABILITY LOG")
    print(f"────────────────────────────────────")
    print(f"TASK\n{task_text}\n")

    step = 0
    status = "FAILED"
    final_answer = ""
    last_actions: List[str] = []

    while step < max_steps:
        step += 1
        print(f"STEP {step}")

        response = llm.chat(messages, system=system_prompt)
        raw_content = response["content"]

        decision = parse_json_response(raw_content)
        thought = decision.get("thought", "No thought provided.")
        raw_action = decision.get("action", "unknown")
        action_input = decision.get("action_input", {})

        action, resolved_args = tools.normalize_action_and_args(raw_action, action_input)

        if action == "error":
            failed_tool_calls += 1
            err_msg = decision["action_input"].get("error", "JSON parse error")
            print(f"Thought: {thought}")
            print(f"RESULT [JSON FORMAT ERROR]: {err_msg}\n")
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({
                "role": "user",
                "content": (
                    "FORMAT ERROR: Respond with ONLY a single JSON object. Example:\n"
                    '{"thought": "...", "action": "write_file", "action_input": {"path": "...", "content": "..."}}'
                )
            })
            continue

        print(f"Thought: {thought}")
        print(f"Action : {action} (from '{raw_action}')" if action != raw_action else f"Action : {action}")
        if resolved_args:
            print(f"Input  : {json.dumps(resolved_args)}")

        if action == "final_answer":
            final_answer = resolved_args.get("answer", raw_content)
            status = "PASSED"
            print(f"\nRESULT\n{final_answer}\n")
            break

        # Repetition / Loop Detection
        action_sig = f"{action}:{json.dumps(resolved_args, sort_keys=True)}"
        last_actions.append(action_sig)
        if len(last_actions) >= 3 and last_actions[-1] == last_actions[-2] == last_actions[-3]:
            print("⚠️ [LOOP DETECTED] Agent repeated the exact same action 3 times. Injecting intervention.")
            messages.append({"role": "assistant", "content": json.dumps(decision)})
            messages.append({
                "role": "user",
                "content": "STUCK WARNING: You have repeated the exact same action 3 times in a row without making progress. Try a different action (e.g. inspect with read_file, or write the missing function correctly)."
            })
            continue

        if action in tools.tools:
            tool_calls_count += 1
            try:
                observation = tools.execute(action, resolved_args)
                obs_str = str(observation) if not isinstance(observation, (dict, list)) else json.dumps(observation)
                print(f"RESULT\n{obs_str}\n")
                messages.append({"role": "assistant", "content": json.dumps(decision)})
                messages.append({
                    "role": "user",
                    "content": f"Observation from tool '{action}':\n{obs_str}"
                })
            except Exception as err:
                failed_tool_calls += 1
                print(f"RESULT [TOOL ERROR]\n{err}\n")
                messages.append({"role": "assistant", "content": json.dumps(decision)})
                messages.append({
                    "role": "user",
                    "content": f"Error executing tool '{action}': {str(err)}"
                })
        else:
            failed_tool_calls += 1
            print(f"RESULT [INVALID ACTION]\nUnknown action '{action}'\n")
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({
                "role": "user",
                "content": f"Invalid action '{action}'. Available tools: {list(tools.tools.keys())} or 'final_answer'."
            })

    total_time = round(time.time() - start_time, 2)

    print(f"────────────────────────────────────")
    print(f"STATUS\nTask completed: {status}")
    print("\nSTATS")
    print(f"Steps            : {step}")
    print(f"Tool calls       : {tool_calls_count}")
    print(f"Failed tool calls: {failed_tool_calls}")
    print(f"Execution time   : {total_time} s")
    print("────────────────────────────────────\n")

    return {
        "status": status,
        "answer": final_answer,
        "steps": step,
        "tool_calls": tool_calls_count,
        "failed_tool_calls": failed_tool_calls,
        "execution_time_sec": total_time
    }


class MiniSeekAgent:
    """Standard ReAct agent with persistent memory awareness."""

    MODE = "react"

    def __init__(self, llm: LLMProvider, tools: ToolRegistry, max_steps: int = 10):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps

    def run(self, user_task: str) -> Dict[str, Any]:
        system_prompt = REACT_SYSTEM_PROMPT.replace(
            "{{memory_summary}}", self.tools.memory.get_summary()
        ).replace(
            "{{tool_descriptions}}", self.tools.get_tool_descriptions()
        )
        messages = [{"role": "user", "content": user_task}]
        return execute_loop(
            llm=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
            messages=messages,
            max_steps=self.max_steps,
            label="REACT",
            task_text=user_task
        )


class PlanningAgent:
    """Plan-First agent with persistent memory awareness."""

    MODE = "planning"

    def __init__(self, llm: LLMProvider, tools: ToolRegistry, max_steps: int = 10):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps

    def _generate_plan(self, user_task: str) -> List[str]:
        """Phase 1: Ask the model to produce a numbered plan."""
        plan_prompt = PLAN_PHASE_SYSTEM_PROMPT.replace(
            "{{memory_summary}}", self.tools.memory.get_summary()
        ).replace(
            "{{tool_descriptions}}", self.tools.get_tool_descriptions()
        )
        messages = [{"role": "user", "content": user_task}]

        print(f"\n{'═' * 60}")
        print(f"MINISEEK [PLANNING] — PHASE 1: GENERATING PLAN")
        print(f"{'═' * 60}")

        response = self.llm.chat(messages, system=plan_prompt)
        raw = response["content"]
        parsed = parse_json_response(raw)
        plan = parsed.get("plan", [])

        if not plan:
            print("WARNING: Model returned empty plan. Using fallback single-step plan.")
            plan = [f"Step 1: Complete the task — {user_task}"]

        for i, step_text in enumerate(plan):
            print(f"  {i + 1}. {step_text}")
        print(f"{'═' * 60}\n")

        return plan

    def run(self, user_task: str) -> Dict[str, Any]:
        plan_start = time.time()
        plan = self._generate_plan(user_task)
        plan_time = round(time.time() - plan_start, 2)

        plan_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(plan))
        exec_prompt = EXECUTE_PHASE_SYSTEM_PROMPT.replace(
            "{{plan_text}}", plan_text
        ).replace(
            "{{memory_summary}}", self.tools.memory.get_summary()
        ).replace(
            "{{tool_descriptions}}", self.tools.get_tool_descriptions()
        )

        messages = [{"role": "user", "content": user_task}]
        result = execute_loop(
            llm=self.llm,
            tools=self.tools,
            system_prompt=exec_prompt,
            messages=messages,
            max_steps=self.max_steps,
            label="PLAN-EXEC",
            task_text=user_task
        )

        result["plan_steps"] = len(plan)
        result["plan_time_sec"] = plan_time
        result["execution_time_sec"] = round(result["execution_time_sec"] + plan_time, 2)

        return result
