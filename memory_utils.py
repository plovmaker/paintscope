"""
Memory management utilities for PaintScope
Handles session state cleanup and memory monitoring
"""

import streamlit as st
import gc
import sys
from typing import Dict, Any, Optional, List
import psutil
import os

class SessionStateManager:
    """Manages Streamlit session state memory efficiently"""
    
    # Memory limits (in MB)
    MAX_SESSION_SIZE_MB = 200  # Maximum size for session state
    WARNING_THRESHOLD_MB = 160  # Show warning when approaching limit (80% of max)
    CRITICAL_THRESHOLD_MB = 180  # Critical threshold (90% of max)
    
    # Keys to preserve during cleanup
    PRESERVE_KEYS = {
        'authenticated', 'user_id', 'username', 'email', 
        'full_name', 'company', 'page', 'pdf_processor'
    }
    
    @staticmethod
    def get_session_size() -> float:
        """Get approximate size of session state in MB"""
        total_size = 0
        for key, value in st.session_state.items():
            try:
                # Get size of each item
                size = sys.getsizeof(value)
                # For complex objects, try to get deeper size
                if hasattr(value, '__dict__'):
                    size += sys.getsizeof(value.__dict__)
                total_size += size
            except:
                # Skip items that can't be measured
                continue
        return total_size / (1024 * 1024)
    
    @staticmethod
    def get_large_items() -> List[tuple]:
        """Get list of large items in session state"""
        items = []
        for key, value in st.session_state.items():
            try:
                size_mb = sys.getsizeof(value) / (1024 * 1024)
                if size_mb > 1:  # Items larger than 1MB
                    items.append((key, size_mb))
            except:
                continue
        return sorted(items, key=lambda x: x[1], reverse=True)
    
    @staticmethod
    def cleanup_session(preserve_data: bool = True):
        """
        Clean up session state to free memory
        
        Args:
            preserve_data: Whether to preserve essential user data
        """
        keys_to_remove = []
        
        for key in st.session_state.keys():
            if preserve_data and key in SessionStateManager.PRESERVE_KEYS:
                continue
            
            # Remove large non-essential items
            if key in ['pdf_images', 'messages', 'current_pdf_id', 
                      'current_conversation_id', 'temp_data']:
                keys_to_remove.append(key)
        
        # Remove identified keys
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        
        # Force garbage collection
        gc.collect()
    
    @staticmethod
    def optimize_messages(max_messages: int = 50):
        """Keep only recent messages to save memory"""
        if 'messages' in st.session_state:
            messages = st.session_state.messages
            if len(messages) > max_messages:
                # Keep system message and last N messages
                system_msg = [m for m in messages if m.get('role') == 'system']
                other_msgs = [m for m in messages if m.get('role') != 'system']
                # Keep more recent messages with higher limit
                st.session_state.messages = system_msg + other_msgs[-max_messages:]
                # Force cleanup after trimming messages
                gc.collect()
    
    @staticmethod
    def check_memory_usage() -> Dict:
        """Check current memory usage and provide recommendations"""
        session_size = SessionStateManager.get_session_size()
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        status = "normal"
        if session_size > SessionStateManager.MAX_SESSION_SIZE_MB:
            status = "critical"
        elif session_size > SessionStateManager.CRITICAL_THRESHOLD_MB:
            status = "critical"
        elif session_size > SessionStateManager.WARNING_THRESHOLD_MB:
            status = "warning"
        
        return {
            'session_size_mb': session_size,
            'process_memory_mb': memory_info.rss / (1024 * 1024),
            'status': status,
            'large_items': SessionStateManager.get_large_items(),
            'recommendation': SessionStateManager._get_recommendation(status, session_size)
        }
    
    @staticmethod
    def _get_recommendation(status: str, size: float) -> str:
        """Get memory management recommendation"""
        if status == "critical":
            return f"⚠️ Critical: Session size ({size:.1f} MB) exceeds limit. Cleanup initiated."
        elif status == "warning":
            return f"⚠️ Warning: Session size ({size:.1f} MB) approaching limit. Consider clearing old data."
        else:
            return f"✅ Normal: Session size ({size:.1f} MB) is within limits."
    
    @staticmethod
    def auto_cleanup():
        """Automatically cleanup when memory usage is high"""
        memory_status = SessionStateManager.check_memory_usage()
        
        if memory_status['status'] == 'critical':
            # Aggressive cleanup
            SessionStateManager.cleanup_session(preserve_data=True)
            SessionStateManager.optimize_messages(max_messages=10)
            
            # Clear PDF processor cache if exists
            if 'pdf_processor' in st.session_state:
                st.session_state.pdf_processor.clear_cache()
            
            gc.collect()
            return True
        
        elif memory_status['status'] == 'warning':
            # Light cleanup
            SessionStateManager.optimize_messages(max_messages=15)
            gc.collect()
            return False
        
        return False


class MemoryMonitor:
    """Monitor and display memory usage in Streamlit app"""
    
    @staticmethod
    def display_memory_widget(location: str = 'sidebar'):
        """Display memory usage widget"""
        memory_status = SessionStateManager.check_memory_usage()
        
        if location == 'sidebar':
            container = st.sidebar
        else:
            container = st
        
        with container:
            with st.expander("💾 Memory Usage", expanded=False):
                # Progress bar for session memory
                progress = min(memory_status['session_size_mb'] / SessionStateManager.MAX_SESSION_SIZE_MB, 1.0)
                color = 'normal' if memory_status['status'] == 'normal' else 'inverse'
                
                st.progress(progress, text=f"Session: {memory_status['session_size_mb']:.1f} MB")
                
                # Show process memory
                st.caption(f"Process: {memory_status['process_memory_mb']:.0f} MB")
                
                # Show recommendation
                st.info(memory_status['recommendation'])
                
                # Show large items if any
                if memory_status['large_items']:
                    st.caption("Large items in memory:")
                    for item, size in memory_status['large_items'][:3]:
                        st.caption(f"  • {item}: {size:.1f} MB")
                
                # Cleanup button
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🧹 Clean", use_container_width=True):
                        SessionStateManager.cleanup_session(preserve_data=True)
                        st.success("Memory cleaned!")
                        st.rerun()
                
                with col2:
                    if st.button("♻️ Reset", use_container_width=True):
                        SessionStateManager.cleanup_session(preserve_data=False)
                        st.success("Session reset!")
                        st.rerun()
    
    @staticmethod
    def display_inline_status():
        """Display inline memory status (compact)"""
        memory_status = SessionStateManager.check_memory_usage()
        
        icon = "🟢" if memory_status['status'] == 'normal' else "🟡" if memory_status['status'] == 'warning' else "🔴"
        
        st.caption(f"{icon} Memory: {memory_status['session_size_mb']:.1f}/{SessionStateManager.MAX_SESSION_SIZE_MB} MB")


def cleanup_old_pdfs_from_session():
    """Remove PDF data from session state"""
    pdf_keys = ['pdf_images', 'current_pdf_id', 'pdf_data', 'pdf_bytes']
    for key in pdf_keys:
        if key in st.session_state:
            del st.session_state[key]
    gc.collect()


def get_object_size(obj: Any) -> int:
    """Get deep size of an object"""
    seen_ids = set()
    
    def sizeof(o):
        if id(o) in seen_ids:
            return 0
        seen_ids.add(id(o))
        
        size = sys.getsizeof(o)
        
        if isinstance(o, dict):
            size += sum(sizeof(k) + sizeof(v) for k, v in o.items())
        elif hasattr(o, '__iter__') and not isinstance(o, (str, bytes, bytearray)):
            size += sum(sizeof(item) for item in o)
        elif hasattr(o, '__dict__'):
            size += sizeof(o.__dict__)
        
        return size
    
    return sizeof(obj)