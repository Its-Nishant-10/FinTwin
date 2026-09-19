"""SQLAlchemy ORM models — OWNER: Member 2.

TODO(member-2): define tables for users, profiles, holdings, goals, liabilities,
price_history and scenario_runs, then wire ProfileRepository to a session.
Keep the DB shape close to app/schemas/profile.py so mapping stays boring.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# class UserProfile(Base):
#     __tablename__ = "user_profiles"
#     ...
