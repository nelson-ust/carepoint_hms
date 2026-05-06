from __future__ import annotations
from sqlalchemy.orm import Session
from app.repositories.loyalty_repository import LoyaltyRepository
from app.schemas.loyalty_schemas import (
    LoyaltyProgramCreateSchema,
    FacilityNetworkCreateSchema
)

class LoyaltyService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LoyaltyRepository(db)

    def create_program(self, data: LoyaltyProgramCreateSchema):
        program = self.repository.create_program(data)
        self.db.commit()
        return program

    def create_network(self, data: FacilityNetworkCreateSchema):
        network = self.repository.create_network(data)
        self.db.commit()
        return network
