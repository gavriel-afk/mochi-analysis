"""SQLAlchemy database models."""

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Job(Base):
    """Analysis job tracking and results storage."""
    __tablename__ = 'jobs'

    id = Column(String(36), primary_key=True)
    status = Column(String(20), nullable=False)  # queued, processing, completed, failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Input config
    org_id = Column(String(255))
    org_name = Column(String(255))
    timezone = Column(String(50))
    start_date = Column(Date)
    end_date = Column(Date)

    # Results (stored as JSON)
    result = Column(JSONB)  # Complete AnalysisResult as JSON
    error = Column(Text)    # Error message if failed

    # Metadata
    conversation_count = Column(Integer)
    processing_time_seconds = Column(Float)


class Chart(Base):
    """Chart images stored as base64."""
    __tablename__ = 'charts'

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    chart_id = Column(String(50), nullable=False)  # e.g., "new_leads", "funnel_overview"
    filename = Column(String(100), nullable=False)  # e.g., "01_new_leads.png"
    image_data = Column(Text, nullable=False)  # base64-encoded PNG
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Report(Base):
    """Framer CMS report queue."""
    __tablename__ = 'reports'

    slug = Column(String(36), primary_key=True)  # Unique identifier for Framer
    job_id = Column(String(36), ForeignKey('jobs.id', ondelete='SET NULL'))
    data = Column(JSONB, nullable=False)  # Report data
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Optional TTL
    accessed_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime)


class AvatarCluster(Base):
    """Avatar database."""
    __tablename__ = 'avatar_clusters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String(255), nullable=False)

    # Avatar profile
    job = Column(String(255))
    age_range = Column(String(50))
    motivation = Column(Text)
    main_objection = Column(Text)

    # Cluster info
    cluster_id = Column(Integer)
    conversation_count = Column(Integer)

    # Samples (stored as JSON array)
    sample_conversations = Column(JSONB)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
