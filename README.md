# PaintScope - AI-Powered Painting Scope Analysis

🎯 **PaintScope** is a professional AI-powered application that analyzes construction PDF drawings to automatically extract painting scope information, generate cost estimates, and provide detailed breakdowns for painting contractors. Features user authentication, data persistence, and intelligent conversation history.

## 📋 Requirements

- macOS (Intel or Apple Silicon)
- Python 3.8 or higher (can be installed automatically by the setup script)
- OpenAI API key
- SQLite (included with Python)

## ✨ New Features

- **🔐 User Authentication**: Secure login/signup system with password hashing
- **💾 Data Persistence**: All PDFs and conversations are saved to database
- **📚 Conversation History**: Access all your previous analyses
- **👤 User Profiles**: Manage your account and view statistics
- **🗂️ PDF Management**: Organize and access all your uploaded documents
- **🔄 Resume Sessions**: Continue where you left off

## 🚀 Quick Start

### Option 1: Automatic Setup (Recommended)

1. Open Terminal and navigate to the project folder:
   ```bash
   cd /path/to/paint-estimator
   ```

2. Make the setup script executable:
   ```bash
   chmod +x setup_and_run.sh
   ```

3. Run the application:
   ```bash
   ./run_app.sh
   ```
   
   Or for the original version without authentication:
   ```bash
   ./setup_and_run.sh
   ```

The script will:
- Check for Python 3 (and offer to install it if missing)
- Create a virtual environment
- Install all dependencies
- Prompt for OpenAI API key if not set
- Launch the Streamlit app

**Note:** If Python is not installed, the script will offer three options:
1. **Install with uv** (recommended) - Installs Python locally for this project only
2. **Install with Homebrew** - System-wide Python installation
3. **Manual installation** - Exit and install Python yourself

### Option 2: Manual Setup

1. Open Terminal and navigate to the project folder:
   ```bash
   cd /path/to/paint-estimator
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```

3. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY='your-api-key-here'
   ```

6. Run the application:
   ```bash
   streamlit run pdf_assistant_chat_v2.py
   ```

## 🔑 OpenAI API Key Setup

The application requires an OpenAI API key to function. You can set it in three ways:

### Temporary (current session only):
```bash
export OPENAI_API_KEY='your-api-key-here'
```

### Permanent (add to shell profile):
```bash
echo "export OPENAI_API_KEY='your-api-key-here'" >> ~/.zshrc
source ~/.zshrc
```

### Through the setup script:
The `setup_and_run.sh` script will prompt you to enter your API key if it's not already set.

## 📁 Files Included

### Core Application Files
- `app.py` - New main application with authentication
- `pdf_assistant_chat_v2.py` - Original Streamlit application
- `pdf_assistant_chat.py` - Alternative version
- `filter_relevant_pages.py` - PDF filtering utility

### Authentication & Database
- `models.py` - SQLAlchemy database models
- `db_service.py` - Database service layer
- `auth.py` - Authentication module
- `alembic/` - Database migrations

### Configuration & Setup
- `requirements.txt` - Python dependencies
- `.env.example` - Environment configuration template
- `run_app.sh` - Launch script for new version
- `setup_and_run.sh` - Setup script for original version
- `alembic.ini` - Database migration configuration

## 🛠️ Troubleshooting

### Python not found
The setup script will now offer to install Python automatically! When you run `./setup_and_run.sh`, if Python is not found, you'll see:
- Option 1: Install with uv (recommended - doesn't affect system Python)
- Option 2: Install with Homebrew (system-wide)
- Option 3: Manual installation

For manual installation, visit: https://www.python.org/downloads/

### Permission denied when running script
Make the script executable:
```bash
chmod +x setup_and_run.sh
```

### OpenAI API errors
- Ensure your API key is valid
- Check that you have credits in your OpenAI account
- Verify the API key is correctly set in your environment

### Port already in use
If Streamlit says the port is already in use, you can specify a different port:
```bash
streamlit run pdf_assistant_chat_v2.py --server.port 8502
```

## 🎯 About PaintScope

**PaintScope** revolutionizes the painting estimation process by:
- 🤖 Using AI to instantly analyze architectural drawings
- 📊 Extracting detailed painting scopes with precision
- 💰 Generating accurate cost estimates
- 📋 Identifying paint codes, finishes, and specifications
- 🔍 Providing page-specific references for every finding

## 🔐 First Time Setup

1. **Create an Account**
   - On first run, click "Sign Up" tab
   - Enter your details (username, email, password)
   - Password must be 8+ characters with uppercase, lowercase, and numbers

2. **Login to PaintScope**
   - Use your username and password to login
   - Your session will be remembered

3. **Upload PDFs**
   - PDFs are saved permanently to your account
   - Add project names and addresses for better organization
   - Access your PDFs anytime from the sidebar

4. **Conversations**
   - All conversations are automatically saved
   - Resume any conversation from the sidebar
   - Each PDF can have multiple conversations

## 💡 Usage Tips

1. The app can analyze PDF drawings up to 50 pages
2. It works best with architectural drawings that include:
   - Finish schedules
   - Floor plans
   - Reflected ceiling plans
   - Door/window schedules
   - Elevation drawings

3. The app will extract:
   - Bid scope inclusions
   - Exclusions
   - Alternates (ALTs)
   - Cost estimates based on unit costs
   - Specific paint/wallcovering codes (P-01, P-02, WC-01, etc.)

## 📞 Support

If you encounter any issues with PaintScope, ensure:
1. All files are in the same directory
2. Python 3.8+ is installed
3. Your OpenAI API key is valid and has credits
4. You're connected to the internet

---

**PaintScope** - Precision Painting Estimation Through AI
🎯 Scope Smarter, Bid Better
