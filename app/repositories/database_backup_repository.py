"""
Carepoint HMS - Database Backup Repository

This module handles all database persistence operations for the DatabaseBackup model.
It abstracts the SQLAlchemy queries into a clean interface for the service layer.

Responsibilities:
- Retrieval of backup history with pagination and sorting.
- Record creation for new backup attempts.
- Atomic updates for status and metadata (size, checksums, S3 URLs).
- Soft-delete aware filtering.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.all_models import DatabaseBackup

class DatabaseBackupRepository:
    """
    Repository for managing DatabaseBackup persistence.
    
    Ensures that the service layer doesn't need to interact with raw SQLAlchemy
    queries, promoting a clean separation of concerns.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.
        
        Args:
            db (Session): A tenant-scoped database session.
        """
        self.db = db

    def get_all(self, limit: int = 100) -> List[DatabaseBackup]:
        """
        Retrieve all non-deleted backups, ordered by the most recent first.
        
        Args:
            limit (int): The maximum number of records to return.
            
        Returns:
            List[DatabaseBackup]: A list of backup records.
        """
        return (
            self.db.query(DatabaseBackup)
            .filter(DatabaseBackup.is_deleted.is_(False))
            .order_by(desc(DatabaseBackup.date_created))
            .limit(limit)
            .all()
        )

    def get_by_id(self, backup_id: int) -> Optional[DatabaseBackup]:
        """
        Retrieve a specific backup by its ID, ensuring it's not soft-deleted.
        
        Args:
            backup_id (int): The primary key of the backup record.
            
        Returns:
            Optional[DatabaseBackup]: The record if found, else None.
        """
        return (
            self.db.query(DatabaseBackup)
            .filter(
                DatabaseBackup.id == backup_id,
                DatabaseBackup.is_deleted.is_(False)
            )
            .first()
        )

    def create(self, backup_data: dict) -> DatabaseBackup:
        """
        Persist a new backup attempt record.
        
        Args:
            backup_data (dict): Dictionary of field names and values for DatabaseBackup.
            
        Returns:
            DatabaseBackup: The newly created and refreshed ORM object.
        """
        backup = DatabaseBackup(**backup_data)
        self.db.add(backup)
        self.db.commit()
        self.db.refresh(backup)
        return backup

    def update(self, backup: DatabaseBackup, update_data: dict) -> DatabaseBackup:
        """
        Update an existing backup record with new metadata or status changes.
        
        This is typically called after the physical pg_dump or S3 upload completes.
        
        Args:
            backup (DatabaseBackup): The ORM object to update.
            update_data (dict): Dictionary of updates to apply.
            
        Returns:
            DatabaseBackup: The updated and refreshed ORM object.
        """
        for key, value in update_data.items():
            setattr(backup, key, value)
        self.db.commit()
        self.db.refresh(backup)
        return backup
