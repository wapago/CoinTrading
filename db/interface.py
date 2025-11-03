import sys
import asyncio

from typing import Iterable
from functools import reduce

from sqlalchemy import select, insert, delete, update, sql, func
from sqlalchemy.orm import joinedload, selectinload, aliased
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from . import models
from .config import DB_URI

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Interface:
    def __init__(self):
        self.engine = create_async_engine(DB_URI, echo=False)
        self.session_maker = async_sessionmaker(self.engine, autoflush=False, autocommit=False)
        self.queryset = None

    @staticmethod
    def func(name):
        return getattr(func, name)

    @staticmethod
    def alias(model, name=''):
        return aliased(model, name=name if name else model.__tablename__)

    @staticmethod
    async def encrypt_data(session: AsyncSession, data, encryption_key):
        encrypted_data = func.pgp_sym_encrypt(data, encryption_key)
        result = await session.execute(encrypted_data)
        return result.scalar()

    @staticmethod
    async def decrypt_data(session: AsyncSession, encrypted_data, encryption_key):
        decrypted_data = func.pgp_sym_decrypt(encrypted_data, encryption_key)
        result = await session.execute(decrypted_data)
        return result.scalar()

    async def create_all(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)

    async def get_session(self):
        async with self.session_maker() as session:
            yield session

    @staticmethod
    async def rollback(session: AsyncSession):
        await session.rollback()

    @staticmethod
    async def commit(session: AsyncSession):
        await session.commit()

    @staticmethod
    async def count(session: AsyncSession, model: models.User, conditions=None):
        queryset = select(sql.func.count(model.id))
        if conditions:
            queryset = queryset.where(*conditions)
        return await session.scalar(queryset)

    @staticmethod
    async def select(session: AsyncSession,
                     model: models.User,
                     columns=None,
                     conditions=None,
                     offset=None,
                     limit=None,
                     execute=True,
                     is_single=False,
                     is_subquery=False,
                     join_list=None,
                     select_in_list=None,
                     to_dict=False,
                     order_by=None):

        if join_list:
            queryset = select(model).options(*[joinedload(join) for join in join_list])
        elif select_in_list:
            queryset = select(model).options(*[reduce(lambda x, y: x.selectinload(y), sel[1:], selectinload(sel[0]))
                                               if isinstance(sel, Iterable) else selectinload(sel) for sel in select_in_list])
        else:
            queryset = select(model)

        if conditions:
            queryset = queryset.where(*conditions)
        if offset:
            queryset = queryset.offset(offset)
        if limit:
            queryset = queryset.limit(limit)
        if order_by:
            queryset = queryset.order_by(*order_by)
        if columns:
            queryset = queryset.with_only_columns(*columns)

        if execute:
            return await session.execute(queryset)
        else:
            if is_single:
                return await session.scalar(queryset)
            elif is_subquery:
                return queryset.scalar_subquery()
            elif to_dict:
                return queryset.column_descriptions
            else:
                return await session.scalars(queryset)

    @staticmethod
    async def insert(session: AsyncSession, model, flush=True, commit=True):
        session.add(model)

        if flush:
            await session.flush()

        if commit:
            await session.commit()

    @staticmethod
    async def bulk_insert(session: AsyncSession, model, *datas, flush=True, commit=True, add_all=False, or_replace=False):
        if add_all:
            session.add_all(datas)
        else:
            if or_replace:
                for data in datas:
                    queryset = pg_insert(model).values(**data)
                    queryset = queryset.on_conflict_do_update(index_elements=or_replace, set_=data)
                    await session.execute(queryset)
            else:
                queryset = (insert(model), datas)
                await session.execute(*queryset)

        if flush:
            await session.flush()

        if commit:
            await session.commit()

    @staticmethod
    async def update(session: AsyncSession, selection, flush=True, commit=True, **update_data):
        for key, value in update_data.items():
            setattr(selection, key, value)

        if flush:
            await session.flush()

        if commit:
            await session.commit()

    @staticmethod
    async def bulk_update(session: AsyncSession, model, update_data, *conditions, flush=True, commit=True):
        queryset = update(model).where(*conditions).values(**update_data)
        await session.execute(queryset)

        if flush:
            await session.flush()

        if commit:
            await session.commit()

    @staticmethod
    async def delete(session: AsyncSession, selection, flush=True, commit=True):
        await session.delete(selection)

        if flush:
            await session.flush()

        if commit:
            await session.commit()

    @staticmethod
    async def bulk_delete(session: AsyncSession, model, *conditions, flush=True, commit=True):
        queryset = delete(model).where(*conditions)
        await session.execute(queryset)

        if flush:
            await session.flush()

        if commit:
            await session.commit()


# async def main():
#     interface = Interface()
#     alias = aliased(models.State, name='state')
#     async with interface.get_session() as session:
#         users = (await interface.select(session, models.User, execute=False,
#                                         join_list=(models.User.state.of_type(alias), models.User.profile, models.User.subscription),
#                                         order_by=(models.State.is_active.asc(), ))).all()
#         # print(users)
#
# if __name__ == '__main__':
#     asyncio.run(main())
