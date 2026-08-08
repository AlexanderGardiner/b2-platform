from pathlib import Path

from src.orchestrator import agent as agent_module


AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
RETIRED_MODELS = {"gemini-2.0-flash", "gemini-3.1-flash-lite-preview"}


class FakeProvider:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls.append(kwargs)


class FakeModel:
    calls = []

    def __init__(self, model_name, *, provider):
        self.model_name = model_name
        self.provider = provider
        self.calls.append((model_name, provider))


class FakePydanticAgent:
    def __init__(self, *, model, system_prompt, name, deps_type):
        self.model = model
        self.system_prompt = system_prompt
        self.name = name
        self.deps_type = deps_type
        self.tools = []

    def tool(self, fn, *, name, description):
        self.tools.append((name, description, fn))
        return fn

    def tool_plain(self, fn, *, name, description):
        self.tools.append((name, description, fn))
        return fn


def _agent_yaml_files():
    return sorted(AGENTS_DIR.glob("*.yaml"))


def test_agent_yaml_files_do_not_use_retired_gemini_models():
    for yaml_file in _agent_yaml_files():
        definition = agent_module._load_agent_definition_from_file(yaml_file)
        assert definition.provider["model"] not in RETIRED_MODELS


def test_all_agent_definitions_construct_google_vertex_models(monkeypatch):
    FakeProvider.calls = []
    FakeModel.calls = []
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr(agent_module, "GoogleProvider", FakeProvider)
    monkeypatch.setattr(agent_module, "GoogleModel", FakeModel)
    monkeypatch.setattr(agent_module, "PydanticAgent", FakePydanticAgent)

    for yaml_file in _agent_yaml_files():
        definition = agent_module._load_agent_definition_from_file(yaml_file)
        agent = agent_module.Agent(definition)
        assert agent.name == definition.name
        assert agent.pydantic_ai_agent.model.model_name == definition.provider["model"]

    assert FakeModel.calls
    assert all(model_name == "gemini-2.5-flash" for model_name, _provider in FakeModel.calls)
    assert all(call["vertexai"] is True for call in FakeProvider.calls)
    assert all(call["project"] == "test-project" for call in FakeProvider.calls)
