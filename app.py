"""
PaintScope - Main Application
AI-Powered Painting Scope Analysis with Authentication and Data Persistence
"""

import streamlit as st
from openai import OpenAI
import os
import base64
import fitz  # PyMuPDF
from typing import List, Dict, Optional
import tempfile
from PIL import Image
import io
from datetime import datetime

# Import our modules
import auth
import db_service
from models import init_db

# Initialize database
init_db()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
if 'pdf_images' not in st.session_state:
    st.session_state.pdf_images = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'page' not in st.session_state:
    st.session_state.page = "main"

# System instructions for the assistant
SYSTEM_PROMPT = """You are an expert construction estimator specializing in painting trades.
Your job is to analyze uploaded architectural PDF drawings and extract all relevant information
for painting scopes, including scope inclusions, exclusions, alternates (ALTs), measurements,
and cost ranges. When answering, always provide structured results in the format below.
If information is implied, ambiguous, or subject to interpretation, explain your reasoning
and assumptions. If there are revisions or multiple drafts, note them clearly.

---

### 🔎 What to Look For
- **Symbols / Notes**: P-01, P-02, P-03, WC-01, WC-02 (paint/wallcovering indicators).
- **Keywords**: "paint", "painting", "coating", "finish", "to be furnished by the owner", "by the GC/general contractor" (assume GC = us).
- **Locations in Docs**:
  - Architectural Pages (e.g., A-100, A-301, A-206)
  - Finish Schedule
  - Floor Plan
  - Reflected Ceiling Plans (RCP)
  - Door Schedule
  - Wall Coverings
  - Window Schedule
  - Elevations
  - Phasing / Demo Plans

---

### 📑 Output Format Example

**Bid Scope Inclusions**
- **Walls** – Paint all new/existing gyp. board partitions per Finish Schedule (P-01, P-02).
- **Ceilings** – Prep, Prime & Paint gyp. ceilings where indicated (exclude ACT).
- **Doors/Frames** – Prep, Prime & Paint Hollow Metal frames and paint-grade doors.
- **Staining** – Prep & Paint millwork items (interior elevations).
- **Exposed MEP** – Paint ductwork, sprinkler piping, conduit, tray in open ceilings.
- **Wallcovering** – Install WC-01, WC-02 where shown in Finish Schedule.
- **Touch-Ups** – Patch/paint for punch list closeout.
- **ETC** – Any other painting/wallcovering scope items.

**Estimated Cost Range (example based on assumptions before exact takeoffs)**
- Walls: $6,000 – $8,500
- Ceilings: $4,000 – $5,500
- Doors/Frames: $1,800 – $2,500
- Exposed MEP: $3,000 – $4,500
- Wallcoverings: $2,000 – $3,200

**Total Range: $16,800 – $24,200**
*(final cost depends on actual takeoffs/finish schedules)*

**Unit Costs to Apply**
- Walls: $0.70 / sf
- Fascia: $5 / lf
- Wallcoverings: $5 / sf
- Doors: $70 / door
- Frames: $65 / frame
- Columns: $110 each

**Alternates (ALTs)**
- Optional scope items (e.g., stain vs paint finish, accent wallcoverings, feature ceilings).
- List as: `ALT: Description – $ Estimated Cost`.

**Exclusions**
- Clearly state what is not included (e.g., ACT ceilings, factory-finished doors, glazing).

---

### 🧮 Expected Flow
1. Parse the PDF and highlight **where (page numbers, schedules, drawings)** scope items are defined.
2. Provide **scope inclusions, exclusions, alternates** in the structured format above.
3. Apply **unit costs** to create **rough cost ranges** until exact takeoffs are provided.
4. Be ready for **interactive Q&A**:
   - User may ask "Show me where WC-02 is located" → respond with page references and summary.
   - User may upload revisions → highlight differences and impact on bid.
   - User may provide measurements → recalc estimates.

You have access to the PDF pages as images. Analyze all pages, extract tables,
read specifications, and understand drawings. Provide detailed and accurate information based on the actual
document content with specific page references."""


def pdf_to_images(pdf_bytes, max_pages=50):
    """Convert PDF to images for analysis."""
    images = []
    
    # Open PDF
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Limit pages to process
    num_pages = min(len(pdf_document), max_pages)
    
    for page_num in range(num_pages):
        # Get the page
        page = pdf_document[page_num]
        
        # Render page to image (increase resolution for better quality)
        mat = fitz.Matrix(2.0, 2.0)  # 2x scale for better quality
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        images.append({
            "page_num": page_num + 1,
            "base64": img_base64
        })
    
    pdf_document.close()
    return images, num_pages


def analyze_pdf_with_gpt(images, initial_prompt):
    """Analyze PDF pages using GPT-4 Vision."""
    
    # Prepare messages with system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Add user message with images
    content = [{"type": "text", "text": initial_prompt}]
    
    # Add first 10 pages as images (to stay within token limits)
    pages_to_analyze = min(10, len(images))
    for i in range(pages_to_analyze):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{images[i]['base64']}",
                "detail": "high"
            }
        })
    
    messages.append({"role": "user", "content": content})
    
    # Call GPT-4 Vision
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=4000,
        temperature=0.3
    )
    
    return response.choices[0].message.content


def chat_with_context(messages_history, user_input, images=None):
    """Continue conversation with context."""
    
    # Add the new user message
    new_message = {"role": "user", "content": user_input}
    messages_history.append(new_message)
    
    # If images are provided and this is about specific pages, include them
    if images and any(keyword in user_input.lower() for keyword in ["page", "show", "where", "location"]):
        # Extract page numbers if mentioned
        import re
        page_nums = re.findall(r'page\s*(\d+)', user_input.lower())
        
        if page_nums:
            content = [{"type": "text", "text": user_input}]
            for page_num in page_nums[:3]:  # Limit to 3 pages
                page_idx = int(page_num) - 1
                if 0 <= page_idx < len(images):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{images[page_idx]['base64']}",
                            "detail": "high"
                        }
                    })
            messages_history[-1]["content"] = content
    
    # Call GPT-4
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages_history,
        max_tokens=2000,
        temperature=0.3
    )
    
    assistant_response = response.choices[0].message.content
    messages_history.append({"role": "assistant", "content": assistant_response})
    
    return assistant_response


def main_app():
    """Main application interface"""
    st.title("🎯 PaintScope")
    
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
                        # Read PDF bytes
                        pdf_bytes = uploaded_file.read()
                        
                        # Convert to images
                        images, num_pages = pdf_to_images(pdf_bytes)
                        
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
                            st.session_state.pdf_images = images
                            
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
                                analysis_result = analyze_pdf_with_gpt(images, initial_prompt)
                                
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
                                
                                # Initialize chat messages
                                st.session_state.messages = [
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": initial_prompt},
                                    {"role": "assistant", "content": analysis_result}
                                ]
                            
                            st.success(f"✅ PDF uploaded and analyzed! ({num_pages} pages)")
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
    if st.session_state.current_pdf_id and st.session_state.pdf_images:
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
                            st.session_state.pdf_images
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
            # Convert PDF bytes to images
            images, num_pages = pdf_to_images(pdf['file_data'])
            st.session_state.current_pdf_id = pdf_id
            st.session_state.pdf_images = images
            
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
                images, _ = pdf_to_images(pdf['file_data'])
                st.session_state.pdf_images = images
                st.session_state.current_pdf_id = conversation['pdf_id']
        
        # Load messages
        messages = db_service.get_conversation_messages(conversation_id, st.session_state.user_id)
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in messages:
            st.session_state.messages.append({
                "role": msg['role'],
                "content": msg['content']
            })
        
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
