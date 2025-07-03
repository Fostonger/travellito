from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeMeta

T = TypeVar('T')
ModelType = TypeVar('ModelType', bound=DeclarativeMeta)


class IRepository(ABC, Generic[ModelType]):
    """Base repository interface following Interface Segregation Principle"""
    
    @abstractmethod
    async def get(self, id: Any) -> Optional[ModelType]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def get_multi(
        self, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple entities with pagination"""
        pass
    
    @abstractmethod
    async def create(self, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create new entity"""
        pass
    
    @abstractmethod
    async def update(self, *, id: Any, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """Update existing entity"""
        pass
    
    @abstractmethod
    async def delete(self, *, id: Any) -> bool:
        """Delete entity"""
        pass
    
    @abstractmethod
    async def count(self, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities"""
        pass


class BaseRepository(IRepository[ModelType], Generic[ModelType]):
    """Base repository implementation with common CRUD operations"""
    
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: Any) -> Optional[ModelType]:
        """Get entity by ID"""
        return await self.session.get(self.model, id)
    
    async def get_multi(
        self, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple entities with pagination and filtering"""
        query = select(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create new entity"""
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj
    
    async def update(self, *, id: Any, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """Update existing entity"""
        db_obj = await self.get(id)
        if not db_obj:
            return None
        
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await self.session.flush()
        return db_obj
    
    async def delete(self, *, id: Any) -> bool:
        """Delete entity"""
        db_obj = await self.get(id)
        if not db_obj:
            return False
        
        await self.session.delete(db_obj)
        await self.session.flush()
        return True
    
    async def count(self, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities"""
        query = select(func.count()).select_from(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return result.scalar() or 0


class IService(ABC):
    """Base service interface"""
    pass


class BaseService(IService):
    """Base service implementation with common dependencies"""
    
    def __init__(self, session: AsyncSession):
        self.session = session 