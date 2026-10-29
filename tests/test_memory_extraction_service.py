import asyncio
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient

from agent_runtime.config import AgentRuntimeConfig
from agent_runtime.memory_contract import MemoryPatch
from agent_runtime.memory_service import MemoryServiceConfig, create_app

TOKEN = "memory-test-service-credential-32chars"
EVENT = {"schema_version": 1, "event_type": "message.received", "message_id": "123", "speaker_id": "alice",
         "speaker_kind": "human", "scope": {"kind": "group", "conversation_id": "g1"},
         "text": "我住在北京。", "occurred_at": "2026-01-01T00:00:00Z"}


def config(monkeypatch):
    monkeypatch.delenv("GRAPH_ENGINE_MCP_URL", raising=False)
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    return MemoryServiceConfig(service_key=TOKEN, runtime=AgentRuntimeConfig.from_env(require_graph_mcp=False))


def test_auth_and_no_chat_session_or_model_for_bot(monkeypatch):
    def forbidden():
        raise AssertionError("Bot output must not invoke the model")
    with TestClient(create_app(config(monkeypatch), agent_factory=forbidden)) as client:
        assert client.get("/internal/memory/health").status_code == 200
        assert client.post("/internal/memory/extract", json={"event": EVENT}).status_code == 401
        source = {**EVENT, "event_type": "assistant.delivered", "speaker_kind": "bot"}
        response = client.post("/internal/memory/extract", headers={"X-iGraph-Memory-Key": TOKEN}, json={"event": source})
        assert response.status_code == 200 and response.json() == {"facts": []}


def test_structured_output_and_reject_fabricated_evidence(monkeypatch):
    fact = {"subject": "$speaker", "predicate": "lives_in", "object": "北京", "statement": "用户住在北京",
            "evidence_quote": "我住在北京", "confidence": 0.95, "cardinality": "single"}
    class Agent:
        async def arun(self, value):
            assert '"speaker_id":"alice"' in value
            return SimpleNamespace(content={"facts": [fact]})
    with TestClient(create_app(config(monkeypatch), agent_factory=Agent)) as client:
        response = client.post("/internal/memory/extract", headers={"X-iGraph-Memory-Key": TOKEN}, json={"event": EVENT})
        assert response.status_code == 200 and response.json()["facts"][0]["object"] == "北京"
        fact["evidence_quote"] = "这是来源没有说过的话"
        rejected = client.post("/internal/memory/extract", headers={"X-iGraph-Memory-Key": TOKEN}, json={"event": EVENT})
        assert rejected.status_code == 502 and rejected.json()["detail"] == "INVALID_MEMORY_OUTPUT"


def test_native_config_still_requires_graph_mcp(monkeypatch):
    monkeypatch.delenv("GRAPH_ENGINE_MCP_URL", raising=False)
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    import pytest
    with pytest.raises(RuntimeError, match="GRAPH_ENGINE_MCP_URL"):
        AgentRuntimeConfig.from_env()


def test_provider_failure_never_leaks_exception_text(monkeypatch):
    class Agent:
        async def arun(self, _value):
            raise Exception("private-source-content and private-provider-secret")
    with TestClient(create_app(config(monkeypatch), agent_factory=Agent)) as client:
        result = client.post("/internal/memory/extract", headers={"X-iGraph-Memory-Key": TOKEN}, json={"event": EVENT})
        assert result.status_code == 502
        assert "private" not in result.text
