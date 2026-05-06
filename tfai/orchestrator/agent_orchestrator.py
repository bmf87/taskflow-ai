from typing import List, Any
from tfai.steps import (
    PlannerStep, ResearchStep, WriterStep, 
    ReviewerStep, OrchestrationTrace
)

from tfai.http.http_client import call_orouter_chat
from tfai.util import constants

# HTTP Request Timeouts: Set per request for robustness.
# (connect_timeout, read_timeout)
# - 5 seconds connect: Fast failure if connection can't be established.
# - 180 seconds read: Allows plenty of time for large LLM responses + free-tier latency.
timeout_seconds: tuple[int, int] = (5, 180)


class AgentOrchestrator:
    """
    Runs a planner -> researcher -> writer -> reviewer pipeline
    using the orouter-service's /chat/completions endpoint.

    All prompt wording is defined in orouter-service's prompts.py; this orchestrator 
    only passes structured kwargs (goal, task, plan, notes, draft, etc.).
    
    """

    def __init__(self, bearer_token: str, model_id: str = constants.DEFAULT_FREE_MODEL, 
                free_models: bool = True, ui_ctx: dict[str, Any] | None = None):
        self.bearer_token = bearer_token
        self.model_id = model_id
        self.free_models = free_models
        self.ui_ctx = ui_ctx

    def run(self, goal: str) -> OrchestrationTrace:
        progress_bar = self.ui_ctx["progress_bar"]
        status_text = self.ui_ctx["status_text"]
        progress_bar.progress(0)
        status_text.text(f"Starting Agent Orchestration...")
        
        trace = OrchestrationTrace(goal=goal, model_id=self.model_id)

        # 1. Planner
        status_text.text(f"Running Planner")
        trace.planner = self._run_planner(goal)
        # Batch tasks into groups of 2 to speed up free-tier processing
        # This helps mitigate against LLM "laziness" and the lack of parallel processing
        batch_size = 2
        task_batches = []
        for i in range(0, len(trace.planner.tasks), batch_size):
            batch = trace.planner.tasks[i:i + batch_size]
            batch_str = "\n".join([f"{i+j+1}. {t}" for j, t in enumerate(batch)])
            task_batches.append(batch_str)

        total_tasks = 4 + len(task_batches) # 1 (Planner) + len(batches) + 1 (Writer) + 1 (Reviewer) + 1 (Refiner) = 4 + len(batches)
        tasks_complete = 1
        progress_bar.progress(tasks_complete/total_tasks)

        research_results = []

        # 2. Sequential Researchers
        status_text.text(f"Starting Researchers")
        for idx, batch_str in enumerate(task_batches):
            status_text.text(f"Running Researcher {idx+1}/{len(task_batches)}")
            res = self._run_researcher(goal, batch_str)
            research_results.append(res)
            tasks_complete += 1
            progress_bar.progress(tasks_complete/total_tasks)

        trace.research = [r for r in research_results if r is not None]
        
        # 3. Writer
        status_text.text(f"Running Writer")
        trace.writer = self._run_writer(trace)
        tasks_complete += 1
        progress_bar.progress(tasks_complete/total_tasks)

        # 4. Reviewer
        status_text.text(f"Running Reviewer")
        trace.reviewer = self._run_reviewer(trace)
        tasks_complete += 1
        progress_bar.progress(tasks_complete/total_tasks)

        # 5. Refiner
        status_text.text(f"Running Refiner")
        trace.refiner = self._run_refiner(trace)
        tasks_complete += 1
        progress_bar.progress(tasks_complete/total_tasks)
        status_text.text("Done!")

        return trace

    # ---------- Internal helpers ----------

    def _run_planner(self, goal: str) -> PlannerStep:
        """
        Calls prompt_type='planner' with kwargs expected by PLANNER_PROMPT:
        {goal}
        """
        global timeout_seconds
        planner_kwargs = {
            "goal": goal + "\n\nIMPORTANT: Limit your plan to a maximum of 4 high-level tasks."
        }

        resp_text = call_orouter_chat(
            prompt_type="planner",
            prompt_kwargs=planner_kwargs,
            model_id=self.model_id,
            free_models=self.free_models,
            token=self.bearer_token,
            user_prompt="",  # planner template uses {goal}, not {user_prompt}
            timeout=timeout_seconds,
        )

        tasks = self._parse_tasks_from_text(resp_text)
        return PlannerStep(prompt_kwargs=planner_kwargs, response=resp_text, tasks=tasks)

    def _run_researcher(self, goal: str, task: str) -> ResearchStep:
        """
        Calls prompt_type='researcher' with kwargs expected by RESEARCHER_PROMPT:
        {goal, task}
        """
        global timeout_seconds
        researcher_kwargs = {"goal": goal, "task": task}

        resp_text = call_orouter_chat(
            prompt_type="researcher",
            prompt_kwargs=researcher_kwargs,
            model_id=self.model_id,
            free_models=self.free_models,
            token=self.bearer_token,
            user_prompt="",
            timeout=timeout_seconds,
        )

        return ResearchStep(
            task=task,
            prompt_kwargs=researcher_kwargs,
            response=resp_text,
            notes=resp_text,
        )

    def _run_writer(self, trace: OrchestrationTrace) -> WriterStep:
        """
        Calls prompt_type='writer' with kwargs expected by WRITER_PROMPT:
        {goal, plan, notes}
        """
        global timeout_seconds
        plan_str = "\n".join(f"- {t}" for t in trace.planner.tasks)
        notes_str = "\n\n".join(
            f"Task: {r.task}\nNotes:\n{r.notes}" for r in trace.research
        )

        writer_kwargs = {
            "goal": trace.goal,
            "plan": plan_str,
            "notes": notes_str,
        }

        resp_text = call_orouter_chat(
            prompt_type="writer",
            prompt_kwargs=writer_kwargs,
            model_id=self.model_id,
            free_models=self.free_models,
            token=self.bearer_token,
            user_prompt="",
            timeout=timeout_seconds,
        )

        return WriterStep(prompt_kwargs=writer_kwargs, response=resp_text)

    def _run_reviewer(self, trace: OrchestrationTrace) -> ReviewerStep:
        """
        Calls prompt_type='reviewer' with kwargs expected by REVIEWER_PROMPT:
        {goal, draft}
        """
        global timeout_seconds
        reviewer_kwargs = {
            "goal": trace.goal,
            "draft": trace.writer.response + "\n\nIMPORTANT: You must format your critique as a numbered list of high-level refinements. You may include supporting text under each point.",
        }

        resp_text = call_orouter_chat(
            prompt_type="reviewer",
            prompt_kwargs=reviewer_kwargs,
            model_id=self.model_id,
            free_models=self.free_models,
            token=self.bearer_token,
            user_prompt="",
            timeout=timeout_seconds,
        )

        tasks = self._parse_tasks_from_text(resp_text)

        return ReviewerStep(prompt_kwargs=reviewer_kwargs, response=resp_text, tasks=tasks)

    def _run_refiner(self, trace: OrchestrationTrace) -> WriterStep:
        """
        Calls prompt_type='writer' with kwargs expected by WRITER_PROMPT:
        {goal, plan, notes}
        We inject the reviewer feedback into the 'plan' and the original draft into 'notes'
        """
        global timeout_seconds
        
        plan_str = f"Please refine the draft by incorporating the following Reviewer's Feedback:\n\n{trace.reviewer.response}"
        notes_str = f"--- ORIGINAL DRAFT ---\n\n{trace.writer.response}"

        refiner_kwargs = {
            "goal": trace.goal,
            "plan": plan_str,
            "notes": notes_str,
        }

        resp_text = call_orouter_chat(
            prompt_type="writer",
            prompt_kwargs=refiner_kwargs,
            model_id=self.model_id,
            free_models=self.free_models,
            token=self.bearer_token,
            user_prompt="",
            timeout=timeout_seconds,
        )

        return WriterStep(prompt_kwargs=refiner_kwargs, response=resp_text)

    # ---------- Utility ----------

    @staticmethod
    def _parse_tasks_from_text(text: str) -> list[str]:
        lines = text.splitlines()
        tasks: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Only extract lines that explicitly start with a number or bullet
            if line[0].isdigit() and "." in line[:3]:
                tasks.append(line.split(".", 1)[1].strip())
            elif line.startswith("- ") or line.startswith("* "):
                tasks.append(line[2:])
        return tasks

