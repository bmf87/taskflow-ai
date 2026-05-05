# python -m unittest tests/test_http_client.py
import unittest
from unittest.mock import patch, MagicMock
from tfai.http.http_client import list_models, call_orouter_chat, get_bearer_token
from tfai.util import constants

class TestHttpClient(unittest.TestCase):

    @patch("tfai.http.http_client.requests.get")
    def test_list_models(self, mock_get):
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": [{"id": "model-1"}, {"id": "model-2"}]}
        mock_get.return_value = mock_response

        token = "fake-token"
        models = list_models(token)

        # Assert requests.get was called with correct arguments
        mock_get.assert_called_once_with(
            f"{constants.OROUTER_SRV_URL}/model/models?free_models=true",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(models, [{"id": "model-1"}, {"id": "model-2"}])

    @patch("tfai.http.http_client.requests.post")
    def test_call_orouter_chat(self, mock_post):
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello, world!"}
        mock_post.return_value = mock_response

        token = "fake-token"
        prompt_kwargs = {"key": "value"}
        model_id = "test-model"

        result = call_orouter_chat(
            prompt_type="test_prompt",
            prompt_kwargs=prompt_kwargs,
            model_id=model_id,
            token=token,
        )

        # Expected payload
        expected_payload = {
            "prompt_type": "test_prompt",
            "model_id": model_id,
            "free_models": True,
            "user_prompt": "",
            "conversation_summary": None,
            "extra_system_instructions": None,
            "prompt_kwargs": prompt_kwargs,
        }

        # Assert requests.post was called with correct arguments
        mock_post.assert_called_once_with(
            f"{constants.OROUTER_SRV_URL}/chat/completions",
            json=expected_payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(result, "Hello, world!")

    @patch("tfai.http.http_client.requests.post")
    def test_get_bearer_token(self, mock_post):
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new-fake-token", "token_type": "bearer"}
        mock_post.return_value = mock_response

        client_id = "test-client"
        client_secret = "test-secret"

        token = get_bearer_token(client_id, client_secret)

        # Expected payload
        expected_payload = {
            "grant_type": "password",
            "username": "",
            "password": "",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        # Assert requests.post was called with correct arguments
        mock_post.assert_called_once_with(
            f"{constants.OROUTER_SRV_URL}/token",
            data=expected_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(token, "new-fake-token")

if __name__ == '__main__':
    unittest.main()

