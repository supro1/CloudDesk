from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import AuditLog
from backend.app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)
