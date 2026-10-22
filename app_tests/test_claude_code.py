"""Claude Code CLI connector on the user's Claude subscription, with a stub CLI."""
import json
import sys

import pytest

from tests_app.test_provider_hub import hub  # noqa: F401  (fixture)
from visual_learning import providers
from visual_learning.providers import ClaudeCodeProvider, ProviderError, SecretStore, make_provider


def claude_stub(tmp_path, monkeypatch, body):
    script = tmp_path / "fake_claude.py"
    script.write_text("import sys, json, os\nargs = sys.argv[1:]\nprompt = sys.stdin.read()\n" + body, encoding="utf-8")
    monkeypatch.setattr(providers, "_claude_command", lambda: [sys.executable, str(script)])


def result(**changes):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "", "api_error_status": None,
                       "structured_output": {"answer": "yes"}, "usage": {"input_tokens": 11, "output_tokens": 3},
                       "modelUsage": {"claude-fable-5-1": {}}, **changes})


def test_subscription_call_is_tool_free_schema_validated_and_never_gets_api_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-private-api-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.example")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "subscription-token")
    claude_stub(tmp_path, monkeypatch, f"""
assert "ANTHROPIC_API_KEY" not in os.environ and "ANTHROPIC_BASE_URL" not in os.environ
assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "subscription-token"
assert "--bare" not in args and args[args.index("--tools") + 1] == "" and args[args.index("--setting-sources") + 1] == ""
assert {{"-p", "--no-session-persistence", "--strict-mcp-config", "--disable-slash-commands"}} <= set(args)
schema = json.loads(args[args.index("--json-schema") + 1])
assert schema["additionalProperties"] is False and schema["required"] == ["answer"]
assert args[args.index("--effort") + 1] == "low" and "--model" not in args and "untrusted" in args[args.index("--system-prompt") + 1]
assert prompt == "Source passages"
print({result()!r})
""")
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    response = ClaudeCodeProvider(timeout_seconds=20).generate("Source passages", schema, tmp_path)
    assert response.data == {"answer": "yes"} and response.provider == "claude_code"
    assert response.usage == {"input_tokens": 11, "output_tokens": 3, "model": "claude-fable-5-1"}


def test_selected_model_is_passed_and_text_result_is_accepted(tmp_path, monkeypatch):
    claude_stub(tmp_path, monkeypatch, f"""
assert args[args.index("--model") + 1] == "claude-sonnet-5-5"
print({result(structured_output=None, result='{"answer": "text"}')!r})
""")
    assert ClaudeCodeProvider(model="claude-sonnet-5-5", timeout_seconds=20).generate("x", {}, tmp_path).data == {"answer": "text"}


@pytest.mark.parametrize("changes,code", [
    ({"is_error": True, "subtype": "error_during_execution", "result": "Claude AI usage limit reached|1761000000"}, "quota"),
    ({"is_error": True, "result": "You've hit your limit · resets 3pm"}, "quota"),
    ({"is_error": True, "result": "API Error", "api_error_status": 429}, "quota"),
    ({"is_error": True, "result": "Not logged in · Please run /login"}, "authentication"),
    ({"is_error": True, "subtype": "error_max_structured_output_retries", "result": ""}, "invalid_output"),
    ({"is_error": True, "result": "Something unexpected"}, "provider_failed"),
])
def test_failures_are_classified_for_the_worker(tmp_path, monkeypatch, changes, code):
    claude_stub(tmp_path, monkeypatch, f"print({result(**changes)!r})\nsys.exit(1)\n")
    with pytest.raises(ProviderError) as problem:
        ClaudeCodeProvider(timeout_seconds=20).generate("x", {}, tmp_path)
    assert problem.value.code == code
    if code == "invalid_output":
        assert problem.value.diagnostics["failure"] == "invalid_json"  # the pipeline then repairs the request


def test_missing_object_and_cancellation(tmp_path, monkeypatch):
    claude_stub(tmp_path, monkeypatch, f"print({result(structured_output=None, result='not json')!r})\n")
    with pytest.raises(ProviderError) as problem:
        ClaudeCodeProvider(timeout_seconds=20).generate("x", {}, tmp_path)
    assert problem.value.code == "invalid_output"
    claude_stub(tmp_path, monkeypatch, "import time\ntime.sleep(30)\n")
    with pytest.raises(ProviderError) as problem:
        ClaudeCodeProvider(timeout_seconds=20, cancelled=lambda: True).generate("x", {}, tmp_path)
    assert problem.value.code == "cancelled"


def test_claude_subscription_is_a_built_in_unpaid_provider(hub):  # noqa: F811
    assert isinstance(make_provider({"provider": "claude_code", "claude_code_model": "claude-opus-5-5"}), ClaudeCodeProvider)
    with pytest.raises(ProviderError):
        SecretStore().get("claude_code")
    assert hub.put('/api/settings', json={'provider': 'claude_code'}).status_code == 200
    created = hub.post('/api/jobs', json={'url': 'https://youtu.be/jNQXAC9IVRw'})
    assert created.status_code in (200, 201), created.text
    assert created.json()['job']['input']['preferences']['provider'] == 'claude_code'
    assert hub.put('/api/settings', json={'api_connections': {'claude_code': {'name': 'x', 'endpoint': 'https://a.example/v1', 'model': 'm', 'protocol': 'openai'}}}).status_code == 422
    assert 'claude' in hub.get('/api/settings').json()['tools']
