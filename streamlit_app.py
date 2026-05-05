import os, logging
import json
import time
import threading
import base64
import requests
import streamlit as st
from typing import Any, Dict, List
from tfai import st_functions as stfuncs
from tfai.orchestrator.agent_orchestrator import AgentOrchestrator, OrchestrationTrace
from tfai.util import constants


log = st.logger.get_logger(__name__)

# Load custom CSS
with open("ui/styles/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ---------- Streamlit layout ----------

st.set_page_config(
    page_title="TaskFlow AI",
    page_icon=stfuncs.get_image_src('icon'),
    layout="wide",
)

# Header: TaskFlow AI logo with title
st.markdown(
    f"""
    <div style="display: flex; align-items: center">
        <img src="{stfuncs.get_image_src('logo')}" width="150" style="margin: 4px;">
        <h3 style="margin: 0; padding: 0;">TaskFlow AI: Multi-Agent Orchestrator</h3>
    </div>
    """,
    unsafe_allow_html=True
)
phases = "Plan → Research → Write → Review → Refine"
# Top-level instructions
st.markdown(
    f":small[TaskFlow AI uses **[orouter-service](https://bfavro73-oroutersrv.hf.space/docs)** to run a multi-stage agent pipeline: **{phases}**. <br>"
    f"Both the service and application are running in free-tier mode, which ***does*** affect performance - please be patient!]", unsafe_allow_html=True
)

# ---------- LEFT: Model selection & test ----------

with st.sidebar:
    st.subheader("Model & Health Check")

    with st.expander("Admin Access", expanded=False):
        admin_password = st.text_input("Admin Password", type="password")
    
    is_admin = bool(constants.APP_ADMIN_SECRET and admin_password == constants.APP_ADMIN_SECRET)

    show_free_models_only_ui = st.checkbox("Show free models only", value=True, disabled=not is_admin)
    
    # Enforce True if not admin, to prevent any bypass
    show_free_models_only = show_free_models_only_ui if is_admin else True

    models = stfuncs.list_models_local(free_models=show_free_models_only)
    log.debug(f"Type of models: {type(models)}")
    log.debug(f"Models: {models}")
    model_options = {m: m for m in models}
    options_list = list(model_options.keys())
    default_index = 0
    if show_free_models_only and constants.DEFAULT_FREE_MODEL in options_list:
        default_index = options_list.index(constants.DEFAULT_FREE_MODEL)

    selected_label = st.selectbox(
        "Choose a model",
        options=options_list,
        index=default_index,
    )
    selected_model_id = model_options[selected_label]

    st.caption(f"Selected model ID: `{selected_model_id}`")

    st.markdown("**Model Quick Test**")
    test_input = st.text_area(
        "Test prompt",
        value="Say hello and tell me one fun fact.",
        height=80,
    )

    if st.button("Run Test"):
        if not test_input.strip():
            st.warning("Please enter a test prompt.")
        else:
            with st.spinner("Calling /chat/completions..."):
                try:
                    test_output = stfuncs.model_test_completion_local(
                        model_id=selected_model_id, 
                        text=test_input, 
                        free_models=show_free_models_only)
                    st.markdown("**Test output:**")
                    st.write(test_output)
                except requests.HTTPError as e:
                    stfuncs.show_errors("Model Test Failed", str(e))
                except Exception as e:
                    stfuncs.show_errors("Model Test Failed", str(e))


# ---------- RIGHT: Main Orchestrator UI ----------

with st.container():
    st.subheader("Goal")

    goal = st.text_area(
        f"Enter a short, clear goal for the agent to solve.",
        height=120,
        width="stretch",
        placeholder="E.g., Create a multi-year plan to complete a master's degree while working full time...",
        help="""A good goal is clear, concise, and specifies the desired outcome. Here are a couple of examples: \n
        1. 'Compare three viable GPU options for a MacBook developer workflow. Recommend the overall best value based on 
        performance, battery life, and cost.'
        2. 'Write a document explaining the complexity of Q, K, V with self-attention. Provide clear content for a non-technical 
        reader, yet also introduce enlightening material for an experienced technical reader as well.'
        """,
        key="goal_ta"
    )
    col1, col2, right1, right2 = st.columns([1,1,3,3], gap=None)
    with col1:
        run_clicked = st.button("Run Goal", width=100)
    with col2:
        st.button("Clear", on_click=stfuncs.clear_goal, width=100)
    with right1:
        pass
    with right2:
        pass
    
    if "trace" not in st.session_state:
        st.session_state.trace = None  # type: ignore

        
    ui_ctx = {
        "progress_bar": None,
        "status_text": None,
    }
    if run_clicked and goal.strip():
        token = stfuncs.get_token()
        #log.debug(f"Using token: {token}")
        progress_col, timer_col = st.columns([4, 1])
        with progress_col:
            progress_bar_placeholder = st.empty()
            progress_bar = progress_bar_placeholder.progress(0)
            status_text = st.empty()
        with timer_col:
            timer_placeholder = st.empty()

        ui_ctx["progress_bar"] = progress_bar
        ui_ctx["status_text"] = status_text
       
        orchestrator = AgentOrchestrator(
            bearer_token=token,
            model_id=selected_model_id,
            free_models=show_free_models_only,
            ui_ctx=ui_ctx,
        )

        stop_event = threading.Event()
        start_time = time.time()
        
        def update_timer():
            while not stop_event.is_set():
                elapsed = time.time() - start_time
                mins, secs = divmod(int(elapsed), 60)
                timer_placeholder.markdown(f"**⏱️ Elapsed:** {mins:02d}:{secs:02d}")
                time.sleep(1)

        t = threading.Thread(target=update_timer)
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        add_script_run_ctx(t)
        t.start()

        with progress_bar_placeholder.container():
            try:
                trace = orchestrator.run(goal)
                st.session_state.trace = trace
            except Exception as e:
                st.error(f"Error running orchestrator: {e}")
                st.session_state.trace = None
            finally:
                stop_event.set()
                t.join()
                st.session_state.total_duration = time.time() - start_time
                
        progress_bar.empty()
        status_text.empty()
        timer_placeholder.empty()

    trace: OrchestrationTrace | None = st.session_state.trace  # type: ignore

    if trace:
        if "total_duration" in st.session_state:
            mins, secs = divmod(int(st.session_state.total_duration), 60)
            st.success(f"**⏱️ Total Processing Time:** {mins:02d}:{secs:02d}")

        st.markdown("### Agent Graph")

        # Graphviz diagram of the pipeline stages
        graph_def = """
        digraph G {
            rankdir=LR;
            node [shape=box, style="filled,rounded", color="#4C78A8", fontcolor="white"];

            Planner [URL="#planner-step" target="_self"];
            Researcher [URL="#researcher-steps" target="_self"];
            Writer [URL="#writer-step" target="_self"];
            Reviewer [URL="#reviewer-step" target="_self"];
            Refiner [URL="#refiner-step" target="_self"];
            Final [shape=ellipse, style=filled, color="#2E8B57", fontcolor="white"];

            Planner -> Researcher [label="Tasks", fontsize=10, fontcolor="#4C78A8"];
            Researcher -> Writer [label="Notes", fontsize=10, fontcolor="#4C78A8"];
            Writer -> Reviewer [label="Draft", fontsize=10, fontcolor="#4C78A8"];
            Reviewer -> Refiner [label="Critique", fontsize=10, fontcolor="#4C78A8"];
            Refiner -> Final [label="Final Output", fontsize=10, fontcolor="#2E8B57"];
        }
        """
        st.graphviz_chart(graph_def)

        st.markdown("### Pipeline Detail")

        if "expand_all" not in st.session_state:
            st.session_state.expand_all = False

        if st.button("Toggle All Expanders"):
            st.session_state.expand_all = not st.session_state.expand_all
            st.rerun()

        # Planner details
        st.markdown('<div id="planner-step"></div>', unsafe_allow_html=True)
        with st.expander("Planner Step", expanded=st.session_state.expand_all):
            st.markdown("**Goal passed to planner:**")
            st.write(trace.planner.prompt_kwargs.get("goal"))  # goal string
            st.markdown("**Planner sub-tasks:**")
            for i, task in enumerate(trace.planner.tasks, start=1):
                st.write(f"{i}. {task}")

            st.markdown("**Raw planner response:**")
            st.code(trace.planner.response)

        # Researcher details
        st.markdown('<div id="researcher-steps"></div>', unsafe_allow_html=True)
        total_researcher_tasks = len(trace.research)
        with st.expander(f"Researcher Step(s) ({total_researcher_tasks})", expanded=st.session_state.expand_all):
            for idx, r in enumerate(trace.research, start=1):
                with st.expander(f"Researcher #{idx} of {total_researcher_tasks}: {r.task}", expanded=st.session_state.expand_all):
                    st.markdown("**Sub-task:**")
                    st.write(r.task)
                    st.markdown("**Notes provided to writer:**")
                    st.write(r.notes)
                    st.markdown("**Raw researcher response:**")
                    st.code(r.response)

        # Writer details
        st.markdown('<div id="writer-step"></div>', unsafe_allow_html=True)
        with st.expander("Writer Step", expanded=st.session_state.expand_all):
            st.markdown("**Writer prompt kwargs:**")
            st.json(trace.writer.prompt_kwargs)
            st.markdown("**Draft produced by writer:**")
            st.write(trace.writer.response)

        # Reviewer details
        st.markdown('<div id="reviewer-step"></div>', unsafe_allow_html=True)
        
        num_suggestions = 0
        if trace.reviewer and trace.reviewer.response:
            import re
            for line in trace.reviewer.response.splitlines():
                if re.match(r"^(\-|\*|\d+[\.\)])\s+", line.strip()):
                    num_suggestions += 1
                    
        reviewer_title = f"Reviewer Step ({num_suggestions} suggestions)" if num_suggestions > 0 else "Reviewer Step"

        with st.expander(reviewer_title, expanded=st.session_state.expand_all):
            st.markdown("**Reviewer prompt kwargs:**")
            st.json(trace.reviewer.prompt_kwargs)
            st.markdown("**Reviewer critique / suggestions:**")
            st.write(trace.reviewer.response)

        # Refiner details
        st.markdown('<div id="refiner-step"></div>', unsafe_allow_html=True)
        with st.expander("Refiner Step", expanded=st.session_state.expand_all):
            if trace.refiner:
                st.markdown("**Refiner prompt kwargs:**")
                st.json(trace.refiner.prompt_kwargs)
                st.markdown("**Refined Final Draft:**")
                st.write(trace.refiner.response)

        # Final result area with scroll + download
        st.markdown("### Final Result (Post-Review)")

        # Final result should be the output of the refiner
        final_md = trace.refiner.response if trace.refiner else trace.writer.response


        st.text_area(
            "Final markdown (scrollable)",
            value=final_md,
            height=260,
        )

        st.download_button(
            label="Download Markdown",
            data=final_md,
            file_name="taskflow-ai-output.md",
            mime="text/markdown",
        )
    else:
        st.info("Enter a goal and click **Run Goal** to see the multi-agent pipeline work.")
