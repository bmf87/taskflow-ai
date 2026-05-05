import os, logging
import json
import time
import threading
import base64
import requests
import streamlit as st
from typing import Any, Dict, List
from pathlib import Path
from st_flexible_callout_elements import flexible_callout, flexible_error
from tfai.http import http_client
from tfai.orchestrator.agent_orchestrator import AgentOrchestrator, OrchestrationTrace
from tfai.util import constants

log = st.logger.get_logger(__name__)

#
#  Functions 
#
def get_token():
    if "token" not in st.session_state:
        st.session_state.token = None
        try:
            st.session_state.token = http_client.get_bearer_token(
                constants.OROUTER_CLIENT_ID, constants.OROUTER_CLIENT_SECRET)
        except Exception as e:
            st.error(f"Error getting token: {e}")
    else:
        log.debug("Token already in session state")
    
    return st.session_state.token
    
def list_models_local(free_models: bool = True):
    token = get_token()
    models = http_client.list_models(token, free_models)
  
    return models

def model_test_completion_local(model_id: str, text: str, free_models: bool = True):
    token = get_token()
    try:
        response = http_client.model_test_completion(token, model_id, text, free_models)
        log.debug(f"Type of response: {type(response)}")
        log.debug(f"Response: {response}")

    except requests.HTTPError as e:
        st.error(f"HTTP error: {e}")
    except Exception as e:
        st.error(f"Error: {e}")
    return response

def show_errors(title: str, errors: str):  
    log.error(f"[UI ERROR] - {errors}")
    flexible_error(
        message=f"<b>{title}</b>: {errors}<br><br><i>Please try again!</i>",
        container=st,
        font_size=16,
        alignment="left", 
    )
    st.stop()

def get_image_path(image_key: str) -> str:
    if os.environ.get("SPACE_ID"):
        #  On Hugging Face Spaces - extract filename and point to GitHub raw
        filename = Path(constants.IMAGE_LKP[image_key]).name
        return f"https://github.com/bmf87/taskflow-ai/blob/main/ui/images/{filename}?raw=true"
    else:
        # Developing locally
        return constants.IMAGE_LKP[image_key]
    
def get_image_src(image_key: str) -> str:
    logo_src = get_image_path("logo")
    if logo_src.startswith("http"):
        return logo_src
    else:
        logo_img_bytes = Path(logo_src).read_bytes()
        logo_img_b64 = base64.b64encode(logo_img_bytes).decode("utf-8")
        return f"data:image/png;base64,{logo_img_b64}"

def clear_goal():
    st.session_state.goal_ta = ""