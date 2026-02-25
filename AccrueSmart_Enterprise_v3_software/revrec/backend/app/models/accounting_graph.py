# backend/app/models/accounting_graph.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text


class GraphNode(SQLModel, table=True):
    __tablename__ = "graph_nodes"

    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str = Field(index=True, unique=True)          # e.g. "deal:Q-1001"
    node_type: str = Field(index=True)                     # e.g. "deal"
    ref_id: str = Field(index=True)                        # e.g. "Q-1001"
    label: str = Field(default="")
    attrs_json: str = Field(default="{}", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GraphEdge(SQLModel, table=True):
    __tablename__ = "graph_edges"

    id: Optional[int] = Field(default=None, primary_key=True)
    edge_id: str = Field(index=True, unique=True)          # deterministic unique key
    from_node_id: str = Field(index=True)
    to_node_id: str = Field(index=True)
    edge_type: str = Field(index=True)                     # e.g. "converted_to"
    attrs_json: str = Field(default="{}", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CausalEvent(SQLModel, table=True):
    __tablename__ = "causal_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(index=True, unique=True)         # client-supplied or generated
    root_node_id: str = Field(index=True)                  # e.g. "deal:Q-1001"
    event_type: str = Field(index=True)                    # e.g. "discount_changed"
    before_json: str = Field(default="{}", sa_column=Column(Text))
    after_json: str = Field(default="{}", sa_column=Column(Text))
    impact_json: str = Field(default="{}", sa_column=Column(Text))  # deltas, risk impacts, etc.
    actor: str = Field(default="system")                   # user/email/system/ai
    source: str = Field(default="app")                     # app/integration/ai_extraction
    created_at: datetime = Field(default_factory=datetime.utcnow)
