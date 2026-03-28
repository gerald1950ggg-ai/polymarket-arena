#!/bin/bash
# Launch Polymarket Arena Dashboard

echo "🚀 Starting Polymarket Arena Dashboard..."

# Activate virtual environment 
cd S1-sharp-wallet-copy
source venv/bin/activate
cd ..

# Launch Streamlit dashboard
echo "📊 Launching dashboard at http://localhost:8501"
streamlit run streamlit_app.py