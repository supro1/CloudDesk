from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    Customer,
    Product,
    Profile,
    Subscription,
    Workspace,
)
from backend.app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Profile)

    async def get_by_email(self, email: str) -> Profile | None:
        statement = select(Profile).where(Profile.email == email)
        return await self.session.scalar(statement)


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Customer)

    async def list_by_email(self, email: str) -> list[Customer]:
        statement = (
            select(Customer)
            .where(Customer.email == email)
            .order_by(Customer.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Subscription)

    async def list_for_customer(self, customer_id: str) -> list[Subscription]:
        statement = (
            select(Subscription)
            .where(Subscription.customer_id == customer_id)
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def list_for_customer(self, customer_id: str) -> list[Workspace]:
        statement = (
            select(Workspace)
            .where(Workspace.customer_id == customer_id)
            .order_by(Workspace.name)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Product)

    async def get_by_slug(self, slug: str) -> Product | None:
        statement = select(Product).where(Product.slug == slug)
        return await self.session.scalar(statement)
