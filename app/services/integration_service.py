from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.all_models import IntegrationEndpoint, IntegrationCredential
from app.schemas.integration_schemas import IntegrationEndpointCreate, IntegrationEndpointUpdate
from app.core.cryptography import encrypt_string, decrypt_string
from app.core.exceptions import NotFoundError

class IntegrationService:
    def __init__(self, db: Session):
        self.db = db

    def get_endpoints(self) -> List[IntegrationEndpoint]:
        return self.db.query(IntegrationEndpoint).all()

    def get_endpoint(self, endpoint_id: int) -> IntegrationEndpoint:
        endpoint = self.db.query(IntegrationEndpoint).filter(IntegrationEndpoint.id == endpoint_id).first()
        if not endpoint:
            raise NotFoundError(message="Integration endpoint not found.")
        return endpoint

    def create_endpoint(self, payload: IntegrationEndpointCreate) -> IntegrationEndpoint:
        endpoint = IntegrationEndpoint(
            code=payload.code,
            name=payload.name,
            base_url=payload.base_url,
            protocol=payload.protocol,
            provider_type=payload.provider_type,
            direction=payload.direction,
            is_active=payload.is_active
        )
        self.db.add(endpoint)
        self.db.flush()

        if payload.credentials:
            for cred in payload.credentials:
                # Encrypt sensitive values
                encrypted_value = encrypt_string(cred.secret_reference)
                credential = IntegrationCredential(
                    endpoint_id=endpoint.id,
                    credential_type=cred.credential_type,
                    secret_reference=encrypted_value
                )
                self.db.add(credential)
        
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def update_endpoint(self, endpoint_id: int, payload: IntegrationEndpointUpdate) -> IntegrationEndpoint:
        endpoint = self.get_endpoint(endpoint_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(endpoint, key, value)
        
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def delete_endpoint(self, endpoint_id: int) -> None:
        endpoint = self.get_endpoint(endpoint_id)
        self.db.delete(endpoint)
        self.db.commit()

    def get_decrypted_credentials(self, endpoint_id: int) -> dict:
        endpoint = self.get_endpoint(endpoint_id)
        creds = {}
        for cred in endpoint.credentials:
            creds[cred.credential_type] = decrypt_string(cred.secret_reference)
        return creds
