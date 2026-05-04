from typing import Optional
from sqlalchemy.orm import Session
from app.models.all_models import Department
from app.schemas.department_schema import DepartmentCreateSchema, DepartmentUpdateSchema
from app.core.exceptions import NotFoundError, AlreadyExistsError

class DepartmentService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: DepartmentCreateSchema) -> Department:
        existing = self.db.query(Department).filter(
            (Department.code == payload.code) | (Department.name == payload.name)
        ).first()
        if existing:
            raise AlreadyExistsError(message="Department with this code or name already exists.")

        department = Department(
            name=payload.name,
            code=payload.code,
            description=payload.description,
            is_active=payload.is_active,
        )
        self.db.add(department)
        self.db.commit()
        self.db.refresh(department)
        return department

    def get(self, department_id: int) -> Department:
        department = self.db.query(Department).filter(Department.id == department_id).first()
        if not department:
            raise NotFoundError(message="Department not found.")
        return department

    def update(self, department_id: int, payload: DepartmentUpdateSchema) -> Department:
        department = self.get(department_id)
        
        if payload.code is not None or payload.name is not None:
            query = self.db.query(Department).filter(Department.id != department_id)
            if payload.code:
                query = query.filter(Department.code == payload.code)
            if payload.name:
                query = query.filter(Department.name == payload.name)
            if query.first():
                raise AlreadyExistsError(message="Department with this code or name already exists.")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(department, key, value)
            
        self.db.commit()
        self.db.refresh(department)
        return department

    def list(self, skip: int = 0, limit: int = 50) -> tuple[list[Department], int]:
        query = self.db.query(Department)
        count = query.count()
        items = query.offset(skip).limit(limit).all()
        return items, count

    def delete(self, department_id: int) -> None:
        department = self.get(department_id)
        department.is_deleted = True
        self.db.commit()
