# TaskFlow AI

TaskFlow AI is an interactive, multi-agent orchestration application that breaks down complex user goals into concrete tasks, researches them, and iteratively refines a final comprehensive report. The application serves as the frontend client to the [orouter-service](https://github.com/bmf87/orouter-service) backend, which acts as an authentication and proxy gateway to OpenRouter's LLM models. Together, they demonstrate a decoupled architecture where a lightweight Streamlit frontend drives complex, multi-stage LLM prompting workflows against a secured RESTful API.

## Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3** | Core language used for application logic and orchestration. |
| **Streamlit** | Powers the interactive web application, UI components, and real-time state management. |
| **Requests / urllib3** | Handles HTTP communication with the `orouter-service` backend, including robust retry mechanisms. |
| **Graphviz** | Renders dynamic flowcharts of the agentic pipeline directly in the UI. *(Requires the OS-level `graphviz` dependency)* |
| **Threading** | Manages asynchronous background tasks (like real-time UI timers) alongside Streamlit's synchronous execution model. |

## Technical Architecture

The core of TaskFlow AI revolves around the `AgentOrchestrator` and the `http_client`, working in tandem to execute a 5-stage pipeline: **Plan → Research → Write → Review → Refine**. 

### The `AgentOrchestrator`
The orchestrator manages the lifecycle of a user's goal by passing state forward through a series of discrete agent roles. All state is captured in an `OrchestrationTrace` object, allowing the Streamlit UI to render the inputs and outputs of every stage.

To ensure a performant and stable application—especially when utilizing rate-limited free-tier LLMs—several critical architectural tradeoffs and clever heuristics were made:
1. **Task Batching:** The Planner agent breaks a goal down into sub-tasks. Instead of sending each task to a separate Researcher agent (which sometimes results in massive API queue times), tasks are batched together. This reduces network latency and queue wait times, with a minor tradeoff in the depth of research per specific topic.
2. **Sequential vs. Concurrent Execution:** While firing all Researcher tasks concurrently via a `ThreadPoolExecutor` would theoretically be faster, it was found to cause orphaned background threads and UI crashes in Streamlit. Furthermore, free-tier LLM API endpoints tend to reject concurrent requests. As a tradeoff for stability, the Orchestrator runs Researchers sequentially, guaranteeing successful completion without dropping WebSocket connections.
3. **Planner Constraints:** The Planner is strictly constrained via `prompt_kwargs` to output a maximum of 4 high-level tasks. This hard limit prevents runaway execution times, ensuring the pipeline completes within a practical UX timeframe (under 4-5 minutes) while still guaranteeing there is time to complete the final Refiner step.
4. **Reviewer Heuristics:** To provide actionable feedback without requiring strict JSON structural validation from the external API, the Orchestrator appends a strict "bulleted list" constraint to the Reviewer's prompt. The Streamlit UI then uses a lightweight Regex heuristic to count the bullet points on the fly and dynamically update the UI with the number of generated suggestions.

### The `http_client`
The `http_client.py` module handles all external communication with the `orouter-service`.
- **Durability & Retries:** It utilizes a custom `requests.Session` with `urllib3.util.retry.Retry` to gracefully handle transient 500, 502, 503, and 504 errors from the LLM provider.
- **Graceful Degradation:** The LLM generation space is prone to provider timeouts (e.g., Cloudflare 524 errors). The client explicitly catches all `requests.exceptions.RequestException`s so that instead of bubbling up and crashing the Streamlit UI, the application gracefully reports the API error and allows the user to easily retry. 
- **Non-blocking UI Components:** Because the `http_client` makes synchronous, blocking network calls, long LLM generation times would typically freeze the Streamlit UI. To counter this, a background thread attached to Streamlit's `ScriptRunContext` (`add_script_run_ctx`) continuously updates a live wall-clock timer, keeping the user interface active and informative while the main thread waits for the HTTP response.

## Demo App

[![Open in HF Spaces](https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-sm.svg)](https://huggingface.co/spaces/bfavro73/taskflow-ai)