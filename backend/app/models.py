# app/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meetings = relationship("Meeting", back_populates="host")

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    host_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    host = relationship("User", back_populates="meetings")
    transcripts = relationship("Transcript", back_populates="meeting")
    tasks = relationship("Task", back_populates="meeting")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    speaker = Column(String(255), nullable=True)
    emotion = Column(String(50), nullable=True)
    confidence = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meeting = relationship("Meeting", back_populates="transcripts")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"))
    title = Column(String(255), nullable=False)
    assignee = Column(String(255), nullable=True)
    priority = Column(String(50), default="medium")
    status = Column(String(50), default="pending")
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meeting = relationship("Meeting", back_populates="tasks")
