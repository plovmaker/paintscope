#!/bin/bash

# PaintScope - Launch Script

echo "🎯 PaintScope"
echo "============"
echo "AI-Powered Painting Scope Analysis"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📦 Checking dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file and add your OpenAI API key"
    echo "   Run: nano .env"
    echo "   Or open .env in your text editor"
    echo ""
    read -p "Press Enter after you've added your API key to continue..."
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Initialize database if needed
echo "🗄️  Initializing database..."
python -c "from models import init_db; init_db()"

# Run the application
echo ""
echo "🚀 Starting PaintScope..."
echo "   The app will open in your default browser"
echo "   Press Ctrl+C to stop the server"
echo ""
echo "   Default login: Create a new account on first run"
echo ""

streamlit run app.py
