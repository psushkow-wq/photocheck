#!/bin/bash
cd "$(dirname "$0")/../photo_authenticator"
source venv/bin/activate
pip install flask --quiet
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
echo ""
echo "================================="
echo "  PhotoCheck"
echo "================================="
echo "  http://localhost:8080"
echo "  http://$LOCAL_IP:8080  (mobile)"
echo "  Admin: http://localhost:8080/admin/stats?key=admin123"
echo "================================="
sleep 1 && open "http://localhost:8080" &
cd "$(dirname "$0")"
python3 app.py
