#!/bin/bash
# Setup GitHub Labels for fullon_master_api

set -e

echo "=========================================="
echo "Creating GitHub Labels"
echo "=========================================="
echo ""

# Phase labels
gh label create "phase-2-jwt" --description "Phase 2: JWT Authentication" --color "0E8A16" || echo "Label phase-2-jwt already exists"
gh label create "phase-3-orm" --description "Phase 3: ORM Routes" --color "1D76DB" || echo "Label phase-3-orm already exists"
gh label create "phase-4-ohlcv" --description "Phase 4: OHLCV Routes" --color "5319E7" || echo "Label phase-4-ohlcv already exists"
gh label create "phase-5-cache" --description "Phase 5: Cache WebSocket" --color "D93F0B" || echo "Label phase-5-cache already exists"
gh label create "phase-6-health" --description "Phase 6: Health Monitoring" --color "FBCA04" || echo "Label phase-6-health already exists"

# Component labels
gh label create "auth" --description "Authentication/Authorization" --color "FF6B6B" || echo "Label auth already exists"
gh label create "middleware" --description "Middleware components" --color "FF8B94" || echo "Label middleware already exists"
gh label create "endpoint" --description "API endpoints" --color "4ECDC4" || echo "Label endpoint already exists"
gh label create "database" --description "Database operations" --color "44A08D" || echo "Label database already exists"
gh label create "websocket" --description "WebSocket functionality" --color "9B59B6" || echo "Label websocket already exists"
gh label create "integration" --description "Integration tasks" --color "3498DB" || echo "Label integration already exists"

# Priority labels
gh label create "baseline" --description "Foundation/baseline code" --color "006B75" || echo "Label baseline already exists"
gh label create "critical" --description "Critical functionality" --color "B60205" || echo "Label critical already exists"
gh label create "dependency" --description "FastAPI dependencies" --color "C5DEF5" || echo "Label dependency already exists"

# Type labels
gh label create "function" --description "Function/method implementation" --color "BFD4F2" || echo "Label function already exists"
gh label create "example-validation" --description "Example validation" --color "D4C5F9" || echo "Label example-validation already exists"

echo ""
echo "=========================================="
echo "✅ Labels created successfully"
echo "=========================================="
