from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.base import Base


class ProgramBroadcast(Base):
    __tablename__ = "program_broadcasts"

    id = Column(Integer, primary_key=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    venue = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    visibility = Column(String, default="network")
    status = Column(String, default="open")
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    university = relationship("University", back_populates="broadcasts")
    program = relationship("Program", back_populates="broadcasts")
    invites = relationship("BroadcastInvite", back_populates="broadcast", cascade="all, delete-orphan")


class BroadcastInvite(Base):
    __tablename__ = "broadcast_invites"
    __table_args__ = (UniqueConstraint("broadcast_id", "university_id", name="uq_broadcast_invite"),)

    id = Column(Integer, primary_key=True)
    broadcast_id = Column(Integer, ForeignKey("program_broadcasts.id"), nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    status = Column(String, default="invited")
    note = Column(Text, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    broadcast = relationship("ProgramBroadcast", back_populates="invites")
    university = relationship("University")


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    participants = relationship("ChatParticipant", back_populates="thread", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")


class ChatParticipant(Base):
    __tablename__ = "chat_participants"
    __table_args__ = (UniqueConstraint("thread_id", "user_id", name="uq_chat_participant"),)

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("ChatThread", back_populates="participants")
    user = relationship("User")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id"), nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=True)
    ciphertext = Column(Text, nullable=True)
    iv = Column(String, nullable=True)
    algorithm = Column(String, default="AES-GCM")
    key_envelopes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    thread = relationship("ChatThread", back_populates="messages")
    sender = relationship("User")
