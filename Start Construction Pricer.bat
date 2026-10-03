@echo off
cd /d "F:\Downloads\OnTap hackathon"
.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8501 --browser.gatherUsageStats false
pause
