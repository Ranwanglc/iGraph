"""Octo Memory Graph extraction protocol v1. Kept compatible by the cross-repository contract check."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Scope(StrictModel):
    kind: Literal["direct", "group", "thread", "document"]
    conversation_id: str = Field(min_length=1, max_length=512)
    parent_id: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def parent_required(self):
        if self.kind in {"thread", "document"} and not self.parent_id:
            raise ValueError("thread/document scopes require parent_id")
        return self


class MessageEvent(StrictModel):
    schema_version: Literal[1] = 1
    event_type: Literal["message.received", "assistant.delivered"]
    message_id: str = Field(min_length=1, max_length=256)
    scope: Scope
    speaker_id: str = Field(min_length=1, max_length=256)
    speaker_kind: Literal["human", "bot", "unknown"]
    text: str = Field(min_length=1, max_length=32_000)
    occurred_at: datetime
    sequence: int | None = Field(default=None, ge=0)
    reply_to_message_id: str | None = Field(default=None, max_length=256)
    trace: dict[str, str] = Field(default_factory=dict, max_length=8)

    @field_validator("occurred_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at requires a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def valid_actor(self):
        if self.event_type == "assistant.delivered" and self.speaker_kind != "bot":
            raise ValueError("assistant events require a bot speaker")
        if not self.text.strip():
            raise ValueError("text must not be blank")
        if any(len(k) > 64 or len(v) > 1024 for k, v in self.trace.items()):
            raise ValueError("trace is too large")
        return self


class FactDraft(StrictModel):
    subject: str = Field(min_length=1, max_length=256, description="$speaker for first person")
    predicate: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    object: str = Field(min_length=1, max_length=512)
    statement: str = Field(min_length=1, max_length=2000)
    evidence_quote: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    cardinality: Literal["single", "multiple"] = "multiple"
    supersedes: list[str] = Field(default_factory=list, max_length=20)


class MemoryPatch(StrictModel):
    facts: list[FactDraft] = Field(default_factory=list, max_length=20)


class ExtractionRequest(StrictModel):
    event: MessageEvent
    context: list[MessageEvent] = Field(default_factory=list, max_length=8)
    existing_facts: list[dict] = Field(default_factory=list, max_length=50)
