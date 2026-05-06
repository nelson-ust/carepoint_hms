from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.all_models import LoyaltyProgram, FacilityNetwork
from app.schemas.loyalty_schemas import (
    LoyaltyProgramCreateSchema,
    FacilityNetworkCreateSchema
)

class LoyaltyRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Loyalty Programs ──────────────────────────────────────────────

    def create_program(self, data: LoyaltyProgramCreateSchema) -> LoyaltyProgram:
        program = LoyaltyProgram(**data.model_dump())
        self.db.add(program)
        self.db.flush()
        self.db.refresh(program)
        return program

    def list_programs(self) -> List[LoyaltyProgram]:
        return self.db.scalars(
            select(LoyaltyProgram).where(LoyaltyProgram.is_deleted == False)
        ).all()

    # ── Facility Networks ─────────────────────────────────────────────

    def create_network(self, data: FacilityNetworkCreateSchema) -> FacilityNetwork:
        network = FacilityNetwork(**data.model_dump())
        self.db.add(network)
        self.db.flush()
        self.db.refresh(network)
        return network

    def list_networks(self) -> List[FacilityNetwork]:
        return self.db.scalars(
            select(FacilityNetwork).where(FacilityNetwork.is_deleted == False)
        ).all()
