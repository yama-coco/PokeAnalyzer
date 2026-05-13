from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class MyParty(Base):
    __tablename__ = "my_parties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    pokemon_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    matches = relationship("MatchHistory", back_populates="party")


class MatchHistory(Base):
    __tablename__ = "match_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now())
    opponent_name = Column(String(100), nullable=True)
    my_party_id = Column(Integer, ForeignKey("my_parties.id"), nullable=False)
    enemy_party_json = Column(Text, nullable=True)
    result = Column(String(10), nullable=True)

    party = relationship("MyParty", back_populates="matches")
    action_logs = relationship("ActionLog", back_populates="match")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("match_history.id"), nullable=False)
    turn = Column(Integer, nullable=False)
    pokemon_slot = Column(Integer, nullable=False)
    action_name = Column(String(100), nullable=False)
    target_slot = Column(Integer, nullable=True)

    match = relationship("MatchHistory", back_populates="action_logs")
