"""
SQLAlchemy database models for PaintScope
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.sql import func
import bcrypt
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///paintscope.db")

# Handle PostgreSQL URL from Supabase/Heroku (they use postgres:// but SQLAlchemy needs postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create base class for models
Base = declarative_base()

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    # SQLite settings
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
else:
    # PostgreSQL settings
    engine = create_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    company = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)
    is_active = Column(Integer, default=1)  # SQLite doesn't have Boolean
    
    # Relationships
    pdfs = relationship("PDF", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    
    def set_password(self, password: str):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()


class PDF(Base):
    """PDF document storage model"""
    __tablename__ = "pdfs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    file_size = Column(Integer)
    page_count = Column(Integer)
    project_name = Column(String(255))
    project_address = Column(String(500))
    notes = Column(Text)
    uploaded_at = Column(DateTime, server_default=func.now())
    last_accessed = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="pdfs")
    conversations = relationship("Conversation", back_populates="pdf")
    analysis_results = relationship("AnalysisResult", back_populates="pdf", cascade="all, delete-orphan")
    
    def update_last_accessed(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.utcnow()
    
    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0.0


class Conversation(Base):
    """Conversation/chat session model"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pdf_id = Column(Integer, ForeignKey("pdfs.id", ondelete="SET NULL"))
    title = Column(String(255))
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    pdf = relationship("PDF", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    analysis_results = relationship("AnalysisResult", back_populates="conversation")
    
    def add_message(self, role: str, content: str) -> "Message":
        """Add a message to the conversation"""
        message = Message(
            conversation_id=self.id,
            role=role,
            content=content
        )
        self.last_updated = datetime.utcnow()
        return message
    
    @property
    def message_count(self) -> int:
        """Get total message count"""
        return len(self.messages)


class Message(Base):
    """Individual message in a conversation"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class AnalysisResult(Base):
    """Store analysis results for PDFs"""
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey("pdfs.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"))
    analysis_type = Column(String(50))  # 'initial', 'detailed', 'takeoff', 'custom'
    
    # Analysis data fields
    scope_inclusions = Column(Text)  # JSON string
    scope_exclusions = Column(Text)  # JSON string
    alternates = Column(Text)  # JSON string
    measurements = Column(Text)  # JSON string
    cost_estimates = Column(Text)  # JSON string
    notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    confidence_score = Column(Float)  # 0.0 to 1.0
    
    # Relationships
    pdf = relationship("PDF", back_populates="analysis_results")
    conversation = relationship("Conversation", back_populates="analysis_results")


# Create all tables
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


# Database session context manager
def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
    print(f"Database initialized with SQLAlchemy at {DATABASE_URL}")
