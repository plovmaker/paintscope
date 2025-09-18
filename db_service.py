"""
Database service layer for PaintScope
Provides high-level functions for database operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import SessionLocal, User, PDF, Conversation, Message, AnalysisResult


@contextmanager
def get_db_session():
    """Get database session context manager"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# User Management Functions
def create_user(username: str, email: str, password: str, 
                full_name: str = None, company: str = None) -> Optional[User]:
    """Create a new user account"""
    try:
        with get_db_session() as session:
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                company=company
            )
            user.set_password(password)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    except IntegrityError:
        return None  # Username or email already exists


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user and update last login"""
    with get_db_session() as session:
        user = session.query(User).filter(User.username == username).first()
        if user and user.verify_password(password):
            user.update_last_login()
            session.commit()
            # Return a dictionary instead of the SQLAlchemy object
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'company': user.company
            }
        return None


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID"""
    with get_db_session() as session:
        return session.query(User).filter(User.id == user_id).first()


def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email"""
    with get_db_session() as session:
        return session.query(User).filter(User.email == email).first()


def update_user_profile(user_id: int, **kwargs) -> bool:
    """Update user profile information"""
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key) and key not in ['id', 'password_hash']:
                    setattr(user, key, value)
            session.commit()
            return True
        return False


# PDF Management Functions
def save_pdf(user_id: int, filename: str, file_data: bytes,
             page_count: int = None, project_name: str = None,
             project_address: str = None, notes: str = None) -> Optional[Dict]:
    """Save PDF file to database"""
    with get_db_session() as session:
        pdf = PDF(
            user_id=user_id,
            filename=filename,
            file_data=file_data,
            file_size=len(file_data),
            page_count=page_count,
            project_name=project_name,
            project_address=project_address,
            notes=notes
        )
        session.add(pdf)
        session.commit()
        session.refresh(pdf)
        return {
            'id': pdf.id,
            'filename': pdf.filename,
            'file_size': pdf.file_size,
            'page_count': pdf.page_count,
            'project_name': pdf.project_name,
            'project_address': pdf.project_address
        }


def get_user_pdfs(user_id: int) -> List[PDF]:
    """Get all PDFs for a user (without file data for performance)"""
    with get_db_session() as session:
        pdfs = session.query(
            PDF.id, PDF.filename, PDF.file_size, PDF.page_count,
            PDF.project_name, PDF.project_address, PDF.notes,
            PDF.uploaded_at, PDF.last_accessed
        ).filter(PDF.user_id == user_id).order_by(PDF.uploaded_at.desc()).all()
        
        return [
            {
                'id': pdf.id,
                'filename': pdf.filename,
                'file_size_mb': round(pdf.file_size / (1024 * 1024), 2) if pdf.file_size else 0,
                'page_count': pdf.page_count,
                'project_name': pdf.project_name,
                'project_address': pdf.project_address,
                'notes': pdf.notes,
                'uploaded_at': pdf.uploaded_at,
                'last_accessed': pdf.last_accessed
            }
            for pdf in pdfs
        ]


def get_pdf_by_id(pdf_id: int, user_id: int) -> Optional[Dict]:
    """Get PDF by ID (with file data)"""
    with get_db_session() as session:
        pdf = session.query(PDF).filter(
            PDF.id == pdf_id,
            PDF.user_id == user_id
        ).first()
        if pdf:
            pdf.update_last_accessed()
            session.commit()
            return {
                'id': pdf.id,
                'filename': pdf.filename,
                'file_data': pdf.file_data,
                'file_size': pdf.file_size,
                'file_size_mb': round(pdf.file_size / (1024 * 1024), 2) if pdf.file_size else 0,
                'page_count': pdf.page_count,
                'project_name': pdf.project_name,
                'project_address': pdf.project_address,
                'notes': pdf.notes,
                'uploaded_at': pdf.uploaded_at,
                'last_accessed': pdf.last_accessed
            }
        return None


def update_pdf_metadata(pdf_id: int, user_id: int, **kwargs) -> bool:
    """Update PDF metadata"""
    with get_db_session() as session:
        pdf = session.query(PDF).filter(
            PDF.id == pdf_id,
            PDF.user_id == user_id
        ).first()
        if pdf:
            for key, value in kwargs.items():
                if hasattr(pdf, key) and key not in ['id', 'user_id', 'file_data']:
                    setattr(pdf, key, value)
            session.commit()
            return True
        return False


def delete_pdf(pdf_id: int, user_id: int) -> bool:
    """Delete a PDF and all associated data"""
    with get_db_session() as session:
        pdf = session.query(PDF).filter(
            PDF.id == pdf_id,
            PDF.user_id == user_id
        ).first()
        if pdf:
            session.delete(pdf)
            session.commit()
            return True
        return False


# Conversation Management Functions
def create_conversation(user_id: int, title: str = None, 
                       pdf_id: int = None, description: str = None) -> Dict:
    """Create a new conversation"""
    with get_db_session() as session:
        if not title:
            title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        conversation = Conversation(
            user_id=user_id,
            title=title,
            pdf_id=pdf_id,
            description=description
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return {
            'id': conversation.id,
            'title': conversation.title,
            'pdf_id': conversation.pdf_id,
            'description': conversation.description
        }


def get_user_conversations(user_id: int, pdf_id: int = None) -> List[Dict]:
    """Get conversations for a user, optionally filtered by PDF"""
    with get_db_session() as session:
        query = session.query(Conversation).filter(Conversation.user_id == user_id)
        
        if pdf_id:
            query = query.filter(Conversation.pdf_id == pdf_id)
        
        conversations = query.order_by(Conversation.last_updated.desc()).all()
        
        return [
            {
                'id': conv.id,
                'title': conv.title,
                'description': conv.description,
                'pdf_id': conv.pdf_id,
                'pdf_filename': conv.pdf.filename if conv.pdf else None,
                'message_count': len(conv.messages),
                'created_at': conv.created_at,
                'last_updated': conv.last_updated
            }
            for conv in conversations
        ]


def get_conversation_by_id(conversation_id: int, user_id: int) -> Optional[Dict]:
    """Get conversation by ID"""
    with get_db_session() as session:
        conversation = session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        if conversation:
            return {
                'id': conversation.id,
                'title': conversation.title,
                'pdf_id': conversation.pdf_id,
                'description': conversation.description,
                'created_at': conversation.created_at,
                'last_updated': conversation.last_updated
            }
        return None


def add_message_to_conversation(conversation_id: int, user_id: int, 
                               role: str, content: str) -> Optional[Message]:
    """Add a message to a conversation"""
    with get_db_session() as session:
        conversation = session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if conversation:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )
            conversation.last_updated = datetime.utcnow()
            session.add(message)
            session.commit()
            session.refresh(message)
            return message
        return None


def get_conversation_messages(conversation_id: int, user_id: int) -> List[Dict]:
    """Get all messages in a conversation"""
    with get_db_session() as session:
        conversation = session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if conversation:
            return [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at
                }
                for msg in conversation.messages
            ]
        return []


def delete_conversation(conversation_id: int, user_id: int) -> bool:
    """Delete a conversation and all messages"""
    with get_db_session() as session:
        conversation = session.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if conversation:
            session.delete(conversation)
            session.commit()
            return True
        return False


# Analysis Results Functions
def save_analysis_result(pdf_id: int, analysis_type: str,
                        conversation_id: int = None, **analysis_data) -> AnalysisResult:
    """Save analysis results"""
    with get_db_session() as session:
        result = AnalysisResult(
            pdf_id=pdf_id,
            conversation_id=conversation_id,
            analysis_type=analysis_type,
            scope_inclusions=json.dumps(analysis_data.get('scope_inclusions', [])),
            scope_exclusions=json.dumps(analysis_data.get('scope_exclusions', [])),
            alternates=json.dumps(analysis_data.get('alternates', [])),
            measurements=json.dumps(analysis_data.get('measurements', {})),
            cost_estimates=json.dumps(analysis_data.get('cost_estimates', {})),
            notes=analysis_data.get('notes', ''),
            confidence_score=analysis_data.get('confidence_score', 0.0)
        )
        session.add(result)
        session.commit()
        session.refresh(result)
        return result


def get_pdf_analysis_results(pdf_id: int, user_id: int) -> List[Dict]:
    """Get all analysis results for a PDF"""
    with get_db_session() as session:
        # First verify the PDF belongs to the user
        pdf = session.query(PDF).filter(
            PDF.id == pdf_id,
            PDF.user_id == user_id
        ).first()
        
        if not pdf:
            return []
        
        results = session.query(AnalysisResult).filter(
            AnalysisResult.pdf_id == pdf_id
        ).order_by(AnalysisResult.created_at.desc()).all()
        
        return [
            {
                'id': result.id,
                'analysis_type': result.analysis_type,
                'scope_inclusions': json.loads(result.scope_inclusions) if result.scope_inclusions else [],
                'scope_exclusions': json.loads(result.scope_exclusions) if result.scope_exclusions else [],
                'alternates': json.loads(result.alternates) if result.alternates else [],
                'measurements': json.loads(result.measurements) if result.measurements else {},
                'cost_estimates': json.loads(result.cost_estimates) if result.cost_estimates else {},
                'notes': result.notes,
                'confidence_score': result.confidence_score,
                'created_at': result.created_at
            }
            for result in results
        ]


# Session State Management
def get_user_session_data(user_id: int) -> Dict:
    """Get comprehensive user session data for Streamlit"""
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {}
        
        recent_pdfs = session.query(PDF).filter(
            PDF.user_id == user_id
        ).order_by(PDF.last_accessed.desc().nullslast(), PDF.uploaded_at.desc()).limit(5).all()
        
        recent_conversations = session.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.last_updated.desc()).limit(5).all()
        
        return {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'company': user.company
            },
            'recent_pdfs': [
                {
                    'id': pdf.id,
                    'filename': pdf.filename,
                    'project_name': pdf.project_name,
                    'uploaded_at': pdf.uploaded_at
                }
                for pdf in recent_pdfs
            ],
            'recent_conversations': [
                {
                    'id': conv.id,
                    'title': conv.title,
                    'pdf_filename': conv.pdf.filename if conv.pdf else None,
                    'last_updated': conv.last_updated
                }
                for conv in recent_conversations
            ]
        }
