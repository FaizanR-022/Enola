"""Voice must not bypass the gate. A voice-initiated EXTERNAL tool call is Held exactly
like the typed one, and the text the client speaks says so before anything else."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from enola.agent import service as agent_service
from enola.agent.service import ChatMessage
from enola.agent.speech import ABORTED_NOTICE, APPROVAL_NOTICE, spoken_text_for
from enola.agent.tools import probes
from tests.agent_helpers import ScriptedModel, ai_tool_call


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> ScriptedModel:
    model = ScriptedModel(script=[
        ai_tool_call("send_probe", {"to": "ayesha@kestrellabs.io", "message": "I will send it tonight."}, "call_v1", text="Drafted a note to Ayesha."),
        AIMessage(content="Sent."),
    ])
    monkeypatch.setattr(agent_service, "make_model", lambda *a, **k: model)
    monkeypatch.setattr(agent_service, "model_available", lambda: True)
    probes.SENT.clear()
    return model


def test_voice_initiated_external_call_is_held_and_spoken_as_held(client: TestClient, scripted: ScriptedModel) -> None:
    sent = client.post("/api/chat", json={"text": "email Ayesha I will send it tonight", "thread_id": "voice-1", "source": "voice"})
    assert sent.status_code == 200, sent.text
    run = sent.json()
    assert run["source"] == "voice"
    assert run["held_approval_id"] is not None, "voice turn bypassed the gate"
    held = client.get(f"/api/approvals/{run['held_approval_id']}").json()
    assert held["state"] == "held" and held["risk"] == "external" and held["tool_name"] == "send_probe"
    assert probes.SENT == []
    # The spoken text leads with the approval notice, then the reply.
    assert run["spoken_text"].startswith(APPROVAL_NOTICE)
    assert "waiting for your approval" in run["spoken_text"]
    assert "Drafted a note to Ayesha." in run["spoken_text"]


def test_typed_turn_defaults_to_text_source(client: TestClient, scripted: ScriptedModel) -> None:
    run = client.post("/api/chat", json={"text": "email Ayesha", "thread_id": "voice-2"}).json()
    assert run["source"] == "text"
    assert run["held_approval_id"] is not None
    assert run["spoken_text"].startswith(APPROVAL_NOTICE)


def test_spoken_text_shapes() -> None:
    reply = [ChatMessage(role="you", text="hi"), ChatMessage(role="enola", text="Three things need you today.")]
    assert spoken_text_for(reply, held=False, aborted=False) == "Three things need you today."
    assert spoken_text_for(reply, held=True, aborted=False) == f"{APPROVAL_NOTICE} Three things need you today."
    assert spoken_text_for([], held=True, aborted=False) == APPROVAL_NOTICE
    assert spoken_text_for([ChatMessage(role="tool", text="x", tool_name="t")], held=False, aborted=True) == ABORTED_NOTICE
