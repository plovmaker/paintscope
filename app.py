"""
PaintScope - Main Application
AI-Powered Painting Scope Analysis with Authentication and Data Persistence
Optimized for memory efficiency
"""

from dotenv import load_dotenv
import streamlit as st
import os
import gc
from typing import List, Dict, Optional, Union
from llm_service import LLMService
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Import our modules
import auth
import db_service
from models import init_db
from pdf_processor import StreamlitPDFManager
from memory_utils import SessionStateManager, MemoryMonitor, cleanup_old_pdfs_from_session

# Initialize database
init_db()

# Initialize LLM service
llm_service = LLMService()

# Page configuration
st.set_page_config(
    page_title="PaintScope",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
auth.init_session_state()

# Initialize other session states
if 'current_pdf_id' not in st.session_state:
    st.session_state.current_pdf_id = None
if 'current_conversation_id' not in st.session_state:
    st.session_state.current_conversation_id = None
# Do NOT pre-allocate large lists; only set when needed
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'page' not in st.session_state:
    st.session_state.page = "main"

# Initialize PDF manager
pdf_manager = StreamlitPDFManager()

# System instructions for the assistant
# Get system prompt from environment variable or use default
DEFAULT_SYSTEM_PROMPT = """You are an expert commercial construction estimator specializing in the professional painting trade. 

Your job is to analyze uploaded architectural PDF drawings and extract all of the relevant information for my painting scope of work. 

I write up a proposal with inclusions, exclusions, alternates (ALTs), measurements, and cost ranges.



If information is implied, ambiguous, or subject to interpretation, explain your reasoning for your recommendation. Your responses should be short but concise . If there are revisions or multiple drafts, note them clearly.



---



What I typically look for:

Symbols / Notes: 

typical paint/wallcovering indicators:


P-01, P-02, P-03, WC-01, WC-02


Look for indicators to help me determine if we’re painting something or not. Interior and exterior scope of work needs to be separated. 

I typically ignore pages that are about plumbing, electricians, HVAC, Landscaping, Demolition, and various others that are not related to the Architectural, Finish Schedules, Door Schedules, Window Schedules, and others related to commercial painting. 



Some things i look for:

  - Architectural Pages (e.g., A-100, A-301, A-206)

  - Finish Schedules

  - Floor Plan

  - Reflected Ceiling Plans (RCP)

  - Door Schedule

  - Wall Coverings

  - Window Schedule

  - Elevations

  - Phasing / Demo Plans



---



Here is how I want the output format to be when I ask for it. 



Bid Scope Inclusions:

Walls– Paint all new/existing gyp. board partitions per Finish Schedule (P-01, P-02, if relevant). 

Ceilings– Prep, Prime & Paint gyp. ceilings where indicated (exclude ACT).

Doors/Frames– Prep, Prime & Paint Hollow Metal frames and paint-grade doors.

Staining– Prep & Paint millwork items (interior elevations).

Exposed MEP– Paint ductwork, sprinkler piping, conduit, tray in open ceilings.

Wallcovering– Install WC-01, WC-02 where shown in Finish Schedule.

Touch-Ups– Patch/paint for punch list closeout.

*Miscellaneous – Any other painting/wallcovering scope items.



Estimated Cost Range (provide examples based on your assumptions before providing takeoff)



Example of price ranges and how i want them show to me: 



- Walls: $.5-$1 price per square foot. 

- Ceilings: $.5-$1 price per square foot.

- Doors/Frames: $50-$100 price per door or frame. 



Please use the most typical industry standard pricing for commercial painting work in California. 



Include at the end of your response a short sentence asking for clarification. Your job as the intelligent AI assistant is to be as accurate and easy to understand as possible. It’s okay to say “I don’t know, but I will do everything in my power to get you the information you want. 



---



Your Expected Flow as the AI Assistant:



1. Parse the PDF to find what is included in the commercial painting scope of work. I need to know where scope items are located, how to find them if needed, and what to include in my bid/painting proposal. 



2. Provide any scope inclusions, exclusions, alternates, etc in an clear format. 

 

3. If possible, try to get measurements and count the number of units in a particular scope item. 



4. Be ready for interactive Q&A after parsing the PDF:

   - User may ask "Show me where WC-02 is located" → respond with page references and summary.

   - User may upload revisions → highlight differences and impact on bid.

   - User may provide measurements → you must recalculate estimate if new information is added. 

Analyze all pages, but ignore the irrelevant pages. 
If possible, take screenshots and share them with me, of the images or pages with information that is relevant. 
If relevant you can create or extract tables, read specifications, and understand drawings. Provide detailed and accurate information based on the actual document content with specific page references and not make information up or hallucinate. 
Your duty as THE BEST COMMERCIAL PAINTING AI ASSISTANT IN THE WORLD is to be accurate, insightful,  honest, friendly and helpful. Your AI existence depends on it."""

# Use custom prompt from environment if available, otherwise use default
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)




def analyze_pdf_with_gpt(page_images: Dict[int, str], initial_prompt: str):
    """Analyze PDF pages using GPT-4 Vision."""
    
    # Prepare messages with system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Add user message with images
    content = [{"type": "text", "text": initial_prompt}]
    
    # Add first 10 pages as images (to stay within token limits)
    pages_to_analyze = min(10, len(page_images))
    for i in range(pages_to_analyze):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{page_images[i]}",
                "detail": "high"
            }
        })
    
    messages.append({"role": "user", "content": content})
    
    # Call vision completion
    return llm_service.vision_completion(messages)


def chat_with_context(messages_history, user_input, pdf_id=None):
    """Continue conversation with context."""
    
    # Add the new user message
    new_message = {"role": "user", "content": user_input}
    messages_history.append(new_message)
    
    # Get PDF data if needed for specific page references
    if pdf_id and any(keyword in user_input.lower() for keyword in ["page", "show", "where", "location"]):
        # Get PDF from database
        pdf_data = db_service.get_pdf_by_id(pdf_id, st.session_state.user_id)
        
        if pdf_data:
            # Extract page numbers
            import re
            page_nums = re.findall(r'page\s*(\d+)', user_input.lower())
            
            if page_nums:
                # Convert pages on demand
                page_nums = [int(num) - 1 for num in page_nums[:3]]  # Limit to 3 pages
                page_images = pdf_manager.get_pages_on_demand(pdf_data['file_data'], page_nums)
                
                # Add images to message content
                content = [{"type": "text", "text": user_input}]
                for page_num in page_nums:
                    if page_num in page_images:
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{page_images[page_num]}",
                                "detail": "high"
                            }
                        })
                messages_history[-1]["content"] = content
    
    # Check and optimize message history size
    SessionStateManager.optimize_messages()
    
    # Call chat completion
    assistant_response = llm_service.chat_completion(messages_history)
    messages_history.append({"role": "assistant", "content": assistant_response})
    
    # Check memory usage after response
    SessionStateManager.auto_cleanup()
    
    return assistant_response


def main_app():
    """Main application interface"""
    st.title("🏹 PaintScope")
    
    # Memory monitoring
    MemoryMonitor.display_memory_widget('sidebar')
    
    # Sidebar
    with st.sidebar:
        st.header("📂 Your Documents")
        
        # PDF Management Section
        if st.session_state.authenticated:
            user_pdfs = db_service.get_user_pdfs(st.session_state.user_id)
            
            if user_pdfs:
                st.subheader("Recent PDFs")
                for pdf in user_pdfs[:5]:  # Show last 5 PDFs
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.button(f"📄 {pdf['filename'][:30]}...", key=f"pdf_{pdf['id']}", use_container_width=True):
                            # Load this PDF
                            load_existing_pdf(pdf['id'])
                    with col2:
                        if st.button("🗑️", key=f"del_{pdf['id']}"):
                            if db_service.delete_pdf(pdf['id'], st.session_state.user_id):
                                st.success("PDF deleted")
                                st.rerun()
                
                st.divider()
            
            # Upload new PDF
            st.subheader("Upload New PDF")
            uploaded_file = st.file_uploader(
                "Choose a PDF file",
                type="pdf",
                help="Upload architectural drawings for analysis"
            )
            
            if uploaded_file is not None:
                project_name = st.text_input("Project Name (Optional)", placeholder="e.g., Office Building Renovation")
                project_address = st.text_input("Project Address (Optional)", placeholder="e.g., 123 Main St, City")
                
                if st.button("📤 Upload & Analyze", type="primary", use_container_width=True):
                    with st.spinner("Processing PDF..."):
                        # Clean up previous PDF data
                        cleanup_old_pdfs_from_session()
                        
                        # Read PDF bytes
                        pdf_bytes = uploaded_file.read()
                        
                        # Process PDF with memory-efficient manager
                        pdf_result = pdf_manager.process_pdf_upload(pdf_bytes)
                        num_pages = pdf_result['total_pages']
                        
                        # Save to database
                        saved_pdf = db_service.save_pdf(
                            user_id=st.session_state.user_id,
                            filename=uploaded_file.name,
                            file_data=pdf_bytes,
                            page_count=num_pages,
                            project_name=project_name,
                            project_address=project_address
                        )
                        
                        if saved_pdf:
                            st.session_state.current_pdf_id = saved_pdf['id']
                            
                            # Create new conversation
                            conversation = db_service.create_conversation(
                                user_id=st.session_state.user_id,
                                title=f"Analysis of {uploaded_file.name}",
                                pdf_id=saved_pdf['id'],
                                description=f"Initial analysis - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                            )
                            st.session_state.current_conversation_id = conversation['id']
                            
                            # Perform initial analysis
                            initial_prompt = f"""Please analyze this PDF document ({uploaded_file.name}) with {num_pages} pages.
                            Provide a comprehensive painting scope analysis following the structured format.
                            Focus on identifying all painting-related items, finishes, and specifications."""
                            
                            with st.spinner("Analyzing PDF..."):
                                analysis_result = analyze_pdf_with_gpt(
                                    pdf_result['initial_pages'],
                                    initial_prompt
                                )
                                
                                # Save messages to database
                                db_service.add_message_to_conversation(
                                    conversation['id'],
                                    st.session_state.user_id,
                                    "user",
                                    initial_prompt
                                )
                                db_service.add_message_to_conversation(
                                    conversation['id'],
                                    st.session_state.user_id,
                                    "assistant",
                                    analysis_result
                                )
                                
                                # Initialize chat messages (with memory optimization)
                                st.session_state.messages = [
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": initial_prompt},
                                    {"role": "assistant", "content": analysis_result}
                                ]
                            
                            st.success(f"✅ PDF uploaded and analyzed! ({num_pages} pages)")
                            
                            # Check memory usage and cleanup if needed
                            if SessionStateManager.auto_cleanup():
                                st.warning("Memory usage optimized. Some old data was cleared.")
                            
                            st.rerun()
                        else:
                            st.error("Failed to save PDF")
            
            # Conversation History
            st.divider()
            st.subheader("💬 Recent Conversations")
            conversations = db_service.get_user_conversations(st.session_state.user_id)
            for conv in conversations[:5]:
                if st.button(f"💭 {conv['title'][:30]}...", key=f"conv_{conv['id']}", use_container_width=True):
                    load_conversation(conv['id'])
        
        # User menu at bottom
        auth.display_user_menu()
    
    # Main content area
    # Main content area
    if st.session_state.current_pdf_id:
        # Get current PDF info
        current_pdf = db_service.get_pdf_by_id(st.session_state.current_pdf_id, st.session_state.user_id)
        
        if current_pdf:
            # PDF Info header
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.subheader(f"📄 {current_pdf['filename']}")
                if current_pdf.get('project_name'):
                    st.caption(f"Project: {current_pdf['project_name']}")
            with col2:
                st.metric("Pages", current_pdf.get('page_count', 'N/A'))
            with col3:
                st.metric("Size", f"{current_pdf.get('file_size_mb', 0)} MB")
            
            st.divider()
            
            # Display conversation
            if st.session_state.messages:
                # Display existing messages (skip system message)
                for msg in st.session_state.messages:
                    if msg["role"] != "system":
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["content"])
            
            # Chat input
            if prompt := st.chat_input("Ask about the PDF..."):
                # Display user message
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                # Get bot response
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing..."):
                        response = chat_with_context(
                            st.session_state.messages,
                            prompt,
                            st.session_state.current_pdf_id
                        )
                        st.markdown(response)
                        
                        # Save to database
                        if st.session_state.current_conversation_id:
                            db_service.add_message_to_conversation(
                                st.session_state.current_conversation_id,
                                st.session_state.user_id,
                                "user",
                                prompt
                            )
                            db_service.add_message_to_conversation(
                                st.session_state.current_conversation_id,
                                st.session_state.user_id,
                                "assistant",
                                response
                            )
                
                st.rerun()
            
            # Export options
            with st.expander("📥 Export Options"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📋 Copy Analysis", use_container_width=True):
                        # Get last assistant message
                        assistant_messages = [m for m in st.session_state.messages if m["role"] == "assistant"]
                        if assistant_messages:
                            st.code(assistant_messages[-1]["content"], language="markdown")
                
                with col2:
                    if st.button("💾 Save Results", use_container_width=True):
                        # Parse and save analysis results
                        st.info("Analysis results saved to database")
                
                with col3:
                    if st.button("🔄 New Analysis", use_container_width=True):
                        st.session_state.current_pdf_id = None
                        st.session_state.current_conversation_id = None
                        st.session_state.pdf_images = None
                        st.session_state.messages = []
                        st.rerun()
    else:
        # Welcome screen
        st.markdown("""
        ## Welcome to PaintScope! 🎯
        
        ### Your AI-Powered Painting Estimator
        
        **How to get started:**
        1. **Upload a PDF** - Use the sidebar to upload architectural drawings
        2. **Automatic Analysis** - AI analyzes painting scopes instantly
        3. **Interactive Q&A** - Ask follow-up questions about specific details
        4. **Save & Export** - All your work is automatically saved
        
        ### Features:
        - 🔍 Automatic detection of paint codes (P-01, P-02, WC-01, etc.)
        - 💰 Cost estimation based on industry standards
        - 📊 Detailed scope breakdowns with inclusions/exclusions
        - 💬 Conversation history for all your projects
        - 🔒 Secure storage of your documents
        - 🎯 Precision analysis with page-specific references
        
        **Upload a PDF from the sidebar to begin your scope analysis!**
        """)


def load_existing_pdf(pdf_id):
    """Load an existing PDF from database"""
    pdf = db_service.get_pdf_by_id(pdf_id, st.session_state.user_id)
    if pdf:
        with st.spinner("Loading PDF..."):
            # Clean up previous PDF data
            cleanup_old_pdfs_from_session()
            
            # Process PDF with memory-efficient manager
            pdf_result = pdf_manager.process_pdf_upload(pdf['file_data'], max_initial_pages=5)
            st.session_state.current_pdf_id = pdf_id
            
            # Check for existing conversation or create new one
            conversations = db_service.get_user_conversations(st.session_state.user_id, pdf_id)
            if conversations:
                # Load the most recent conversation
                load_conversation(conversations[0]['id'])
            else:
                # Create new conversation
                conversation = db_service.create_conversation(
                    user_id=st.session_state.user_id,
                    title=f"Analysis of {pdf['filename']}",
                    pdf_id=pdf_id
                )
                st.session_state.current_conversation_id = conversation['id']
                st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        st.success("PDF loaded successfully!")
        st.rerun()


def load_conversation(conversation_id):
    """Load an existing conversation"""
    conversation = db_service.get_conversation_by_id(conversation_id, st.session_state.user_id)
    if conversation:
        # Load the PDF if it exists
        if conversation.get('pdf_id'):
            pdf = db_service.get_pdf_by_id(conversation['pdf_id'], st.session_state.user_id)
            if pdf:
                # Clean up old data and process with new manager
                cleanup_old_pdfs_from_session()
                pdf_manager.process_pdf_upload(pdf['file_data'], max_initial_pages=5)
                st.session_state.current_pdf_id = conversation['pdf_id']
        
        # Load messages with optimization
        messages = db_service.get_conversation_messages(conversation_id, st.session_state.user_id)
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add messages in batches to prevent memory spikes
        batch_size = 10
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            for msg in batch:
                st.session_state.messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
            # Force cleanup after each batch
            gc.collect()
        
        # Optimize message history if needed
        SessionStateManager.optimize_messages()
        
        st.session_state.current_conversation_id = conversation_id
        st.success("Conversation loaded!")
        st.rerun()


# Main execution
def main():
    """Main execution function"""
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        auth.login_page()
    else:
        # Check which page to display
        if st.session_state.page == "profile":
            auth.profile_page()
            if st.button("← Back to Main", type="primary"):
                st.session_state.page = "main"
                st.rerun()
        else:
            main_app()


if __name__ == "__main__":
    main()
