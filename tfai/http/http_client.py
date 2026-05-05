import os, logging
import requests
import streamlit as st
from urllib.parse import urlencode
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Dict, List
from tfai.util.constants import OROUTER_SRV_URL


log = st.logger.get_logger(__name__)
timeout_seconds = (5, 60)

def make_session(
    max_retries=5, 
    backoff_factor=1.0,
    status_forcelist=(429, 500, 502, 503, 504),
):
    """
    Create a requests.Session with retry logic. 
    Use this for durable HTTP requests (i.e., non-interactive, one-shot).
    Do NOT use this for interactive requests (e.g., with WebSockets).

    backoff=backoff_factor*2**(n-1)
    
    Args:
        max_retries: Maximum number of retries
        backoff_factor: Backoff factor
        status_forcelist: List of HTTP status codes to retry on

    Returns:
        requests.Session with retry logic
    """
    
    retry = Retry(
        total=max_retries,
        read=max_retries,
        connect=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def list_models(token: str, free_models: bool = True) -> List[Dict[str, Any]]:
    """
    Optional: call a /chat/models or similar meta endpoint.
    For now, we'll just hard-code a couple as an example.
    Args:
        token: Bearer token to use
    Returns:
        List of models
    """
    
    global timeout_seconds
    log.debug(f"Calling orouter-service for model list with timeout {timeout_seconds}")
    headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
    }
    
    resp = requests.get(
        f"{OROUTER_SRV_URL}/model/models?free_models={free_models}",
        headers=headers,
        timeout=timeout_seconds,
    )
    resp.raise_for_status()
    try:
        data = resp.json()
        #log.debug(f"Type of data: {type(data)}")
        #log.debug(f"Data: {data}")
        if isinstance(data, dict) and "response" in data:
            return data["response"]
        if isinstance(data, str):
            return data
        # return JSON list of models
        return data
    except ValueError:
        return resp.text

def model_test_completion(
    token: str,
    model_id: str, 
    text: str, 
    free_models: bool = True) -> str:
    """
    Hit /chat/completions with a basic prompt_type to test model responsiveness
    and ensure against rate limiting (Http 429)
    Args:
        token: Bearer token to use
        model_id: Model ID to use
        text: Text to test
    Returns:
        Response from the model
    """
    global timeout_seconds
    headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
    }

    payload = {
        "free_models": free_models,
        "model_id": model_id,
        "prompt_type": "basic",
        "user_prompt": text,
        "conversation_summary": None,
        "extra_system_instructions": None,
        "prompt_kwargs": {},
    }
    resp = requests.post(
        f"{OROUTER_SRV_URL}/chat/completions",
        json=payload,
        headers=headers,
        timeout=timeout_seconds,
    )
    resp.raise_for_status()
    try:
        data = resp.json()
        if isinstance(data, dict) and "response" in data:
            return data["response"]
        if isinstance(data, str):
            return data
        return str(data)
    except ValueError:
        return resp.text

def call_orouter_chat(
    prompt_type: str,
    prompt_kwargs: Dict[str, Any],
    model_id: str,
    token: str,
    free_models: bool = True,
    user_prompt: str | None = None,
    conversation_summary: str | None = None,
    extra_system_instructions: str | None = None,
    timeout: tuple[int, int] | None = timeout_seconds,
) -> str:
    """
    Thin client around /chat/completions.
    Args:
        prompt_type: Type of prompt to use
        prompt_kwargs: Keyword arguments to use for the prompt
        model_id: Model ID to use
        token: Bearer token to use
        free_models: Whether to use free models
        user_prompt: User prompt to use
        conversation_summary: Conversation summary to use
        extra_system_instructions: Extra system instructions to use
        timeout: Timeout to use
    Returns:
        Response from the model
    """
    log.debug(f"Calling orouter-service with:\nprompt_type='{prompt_type}',\nmodel_id='{model_id}',\ntimeout={timeout}")
    session = make_session()
    headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
    }
    
    payload: Dict[str, Any] = {
        "prompt_type": prompt_type,
        "model_id": model_id,
        "free_models": free_models,
        # keep these for templates that still use user_prompt / summary / extra_system_instructions
        "user_prompt": user_prompt or "",
        "conversation_summary": conversation_summary,
        "extra_system_instructions": extra_system_instructions,
        "prompt_kwargs": prompt_kwargs,
    }

    try:
        resp = session.post(
            f"{OROUTER_SRV_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()

    # Catch HTTP errors (4xx and 5xx) from cascading to UI crashes
    except requests.exceptions.RequestException as e:
        log.error(f"Error calling orouter-service: {e}")
        return f"API Error: {e}"

    # Adjust based on FastAPI response shape
    try:
        data = resp.json()
        if isinstance(data, dict) and "response" in data:
            return data["response"]
        if isinstance(data, str):
            return data
        return str(data)
    except ValueError:
        return resp.text


def get_bearer_token(client_id: str, client_secret: str) -> str:
    """
    Obtain a bearer token from the /token endpoint.
    Args:
        client_id: Client ID
        client_secret: Client Secret
    Returns:
        Bearer Token
    """
    global timeout_seconds
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "password",
    }
    
    encoded = urlencode(body)
    headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
    }
    
    resp = requests.post(
        f"{OROUTER_SRV_URL}/token",
        data=encoded,
        headers=headers,
        timeout=timeout_seconds,
    )
    resp.raise_for_status()
    
    data = resp.json()
    return data.get("access_token", "")