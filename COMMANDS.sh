#!/bin/bash

# ============================================================================
# SIH 26188 - Border Screening System - Quick Commands
# ============================================================================

PROJECT_DIR="/Users/ravib/Desktop/SIH/sih"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "🎯 SIH 26188 - Quick Command Runner"
echo "===================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# START COMMANDS
# ============================================================================

start_backend() {
    echo -e "${YELLOW}Starting Backend...${NC}"
    cd "$BACKEND_DIR"
    python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
}

start_frontend() {
    echo -e "${YELLOW}Starting Frontend...${NC}"
    cd "$FRONTEND_DIR"
    npm run dev
}

start_both() {
    echo -e "${YELLOW}Starting Both Services...${NC}"
    echo -e "${YELLOW}Open TWO terminals and run:${NC}"
    echo ""
    echo -e "${GREEN}Terminal 1 (Backend):${NC}"
    echo "  cd $BACKEND_DIR"
    echo "  python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo -e "${GREEN}Terminal 2 (Frontend):${NC}"
    echo "  cd $FRONTEND_DIR"
    echo "  npm run dev"
    echo ""
}

# ============================================================================
# STOP COMMANDS
# ============================================================================

stop_backend() {
    echo -e "${YELLOW}Stopping Backend (port 8000)...${NC}"
    kill $(lsof -t -i:8000) 2>/dev/null && echo -e "${GREEN}✓ Backend stopped${NC}" || echo "Backend not running"
}

stop_frontend() {
    echo -e "${YELLOW}Stopping Frontend (port 3000)...${NC}"
    kill $(lsof -t -i:3000) 2>/dev/null && echo -e "${GREEN}✓ Frontend stopped${NC}" || echo "Frontend not running"
}

stop_all() {
    echo -e "${YELLOW}Stopping All Services...${NC}"
    stop_backend
    stop_frontend
}

# ============================================================================
# STATUS COMMANDS
# ============================================================================

status() {
    echo -e "${YELLOW}Checking System Status...${NC}"
    echo ""
    
    # Check backend
    if curl -s http://localhost:8000/ > /dev/null; then
        echo -e "${GREEN}✓ Backend${NC} running on http://localhost:8000"
    else
        echo -e "${RED}✗ Backend${NC} not responding"
    fi
    
    # Check frontend
    if curl -s http://localhost:3000/ > /dev/null; then
        echo -e "${GREEN}✓ Frontend${NC} running on http://localhost:3000"
    else
        echo -e "${RED}✗ Frontend${NC} not responding"
    fi
    
    echo ""
}

# ============================================================================
# TEST COMMANDS
# ============================================================================

test_api() {
    echo -e "${YELLOW}Testing API...${NC}"
    echo ""
    echo -e "${GREEN}API Health Check:${NC}"
    curl -s http://localhost:8000/ | jq '.' 2>/dev/null || curl -s http://localhost:8000/
    echo ""
}

open_dashboard() {
    echo -e "${YELLOW}Opening Dashboard...${NC}"
    open http://localhost:3000
}

open_api_docs() {
    echo -e "${YELLOW}Opening API Documentation...${NC}"
    open http://localhost:8000/docs
}

# ============================================================================
# CLEANUP COMMANDS
# ============================================================================

clean_cache() {
    echo -e "${YELLOW}Cleaning Cache...${NC}"
    npm cache clean --force
    echo -e "${GREEN}✓ NPM cache cleaned${NC}"
}

clear_db() {
    echo -e "${YELLOW}Warning: This will DELETE the database!${NC}"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$BACKEND_DIR/border_screening.db"
        echo -e "${GREEN}✓ Database deleted${NC}"
    fi
}

# ============================================================================
# INSTALL COMMANDS
# ============================================================================

install_backend() {
    echo -e "${YELLOW}Installing Backend Dependencies...${NC}"
    cd "$BACKEND_DIR"
    pip3 install -r requirements.txt
    echo -e "${GREEN}✓ Backend dependencies installed${NC}"
}

install_frontend() {
    echo -e "${YELLOW}Installing Frontend Dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
}

# ============================================================================
# LOG COMMANDS
# ============================================================================

show_menu() {
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║  SIH 26188 - Quick Command Menu        ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    echo "📊 STATUS & INFO:"
    echo "  1. Check status      - status"
    echo "  2. Test API          - test_api"
    echo "  3. Open Dashboard    - open_dashboard"
    echo "  4. Open API Docs     - open_api_docs"
    echo ""
    echo "▶️  START SERVICES:"
    echo "  5. Start Backend     - start_backend"
    echo "  6. Start Frontend    - start_frontend"
    echo "  7. Start Both        - start_both"
    echo ""
    echo "⏹️  STOP SERVICES:"
    echo "  8. Stop Backend      - stop_backend"
    echo "  9. Stop Frontend     - stop_frontend"
    echo "  10. Stop All         - stop_all"
    echo ""
    echo "🔧 MAINTENANCE:"
    echo "  11. Install Backend  - install_backend"
    echo "  12. Install Frontend - install_frontend"
    echo "  13. Clean Cache      - clean_cache"
    echo "  14. Clear Database   - clear_db"
    echo ""
    echo "📝 COMMANDS:"
    echo "  15. Show Menu        - show_menu"
    echo ""
    echo "Usage: source COMMANDS.sh && start_backend"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

if [ "$#" -eq 0 ]; then
    show_menu
else
    case "$1" in
        status)
            status
            ;;
        test_api)
            test_api
            ;;
        open_dashboard)
            open_dashboard
            ;;
        open_api_docs)
            open_api_docs
            ;;
        start_backend)
            start_backend
            ;;
        start_frontend)
            start_frontend
            ;;
        start_both)
            start_both
            ;;
        stop_backend)
            stop_backend
            ;;
        stop_frontend)
            stop_frontend
            ;;
        stop_all)
            stop_all
            ;;
        install_backend)
            install_backend
            ;;
        install_frontend)
            install_frontend
            ;;
        clean_cache)
            clean_cache
            ;;
        clear_db)
            clear_db
            ;;
        show_menu)
            show_menu
            ;;
        *)
            echo "Unknown command: $1"
            show_menu
            ;;
    esac
fi
