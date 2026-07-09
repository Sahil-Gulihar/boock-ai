from __future__ import annotations
from pydantic import BaseModel


class RepairTicket(BaseModel):
    ticket_id: str
    severity: str
    scene_id: str
    entity_id: str | None
    problem: str
    recommended_action: str
    rerun_from_node: str


class RepairTicketManifest(BaseModel):
    tickets: list[RepairTicket] = []
