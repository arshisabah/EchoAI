#!/bin/bash
# Backend Verification Test
# This script verifies that the EchoAI backend is working correctly

set -e

BACKEND_URL="http://localhost:8000"
TEST_ROOM="verify-test-$(date +%s)"

echo "=========================================="
echo "EchoAI Backend Verification Test"
echo "=========================================="
echo ""

# 1. Check if backend is running
echo "✓ Step 1: Checking if backend is running..."
if curl -s -f "${BACKEND_URL}/health" > /dev/null; then
    echo "  ✅ Backend is running"
    curl -s "${BACKEND_URL}/health" | jq .
else
    echo "  ❌ Backend is not running"
    echo "  Start it with: cd backend && python3 -m app.main"
    exit 1
fi
echo ""

# 2. Check API documentation
echo "✓ Step 2: Checking API documentation..."
if curl -s -f "${BACKEND_URL}/docs" > /dev/null; then
    echo "  ✅ API docs accessible at ${BACKEND_URL}/docs"
else
    echo "  ❌ API docs not accessible"
    exit 1
fi
echo ""

# 3. Test room creation
echo "✓ Step 3: Testing room creation..."
RESPONSE=$(curl -s -X POST "${BACKEND_URL}/meeting/rooms/create" \
    -H "Content-Type: application/json" \
    -d "{
        \"room_name\": \"${TEST_ROOM}\",
        \"created_by\": \"test-user\",
        \"password\": \"test123\",
        \"max_participants\": 10
    }")

if echo "$RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo "  ✅ Room created successfully"
    echo "$RESPONSE" | jq '{room_id: .room_id, room_name: .room.room_name, has_password: .room.has_password}'
else
    echo "  ❌ Room creation failed"
    echo "$RESPONSE" | jq .
    exit 1
fi
echo ""

# 4. Test room listing
echo "✓ Step 4: Testing room listing..."
ROOMS=$(curl -s "${BACKEND_URL}/meeting/rooms")
ROOM_COUNT=$(echo "$ROOMS" | jq '.total_count')
echo "  ✅ Found ${ROOM_COUNT} active room(s)"
echo ""

# 5. Test room info retrieval
echo "✓ Step 5: Testing room info retrieval..."
ROOM_INFO=$(curl -s "${BACKEND_URL}/meeting/rooms/${TEST_ROOM}")
if echo "$ROOM_INFO" | jq -e '.room_id' > /dev/null 2>&1; then
    echo "  ✅ Room info retrieved successfully"
    echo "$ROOM_INFO" | jq '{room_id: .room_id, status: .status, participant_count: .participant_count}'
else
    echo "  ❌ Room info retrieval failed"
    echo "$ROOM_INFO" | jq .
    exit 1
fi
echo ""

# 6. Test transcript endpoint
echo "✓ Step 6: Testing transcript endpoint..."
TRANSCRIPT=$(curl -s "${BACKEND_URL}/meeting/rooms/${TEST_ROOM}/transcript")
if echo "$TRANSCRIPT" | jq -e '.room_id' > /dev/null 2>&1; then
    ENTRY_COUNT=$(echo "$TRANSCRIPT" | jq '.total_entries')
    echo "  ✅ Transcript endpoint working (${ENTRY_COUNT} entries)"
else
    echo "  ❌ Transcript endpoint failed"
    echo "$TRANSCRIPT" | jq .
    exit 1
fi
echo ""

# 7. Test metrics endpoint
echo "✓ Step 7: Testing metrics endpoint..."
METRICS=$(curl -s "${BACKEND_URL}/metrics")
if echo "$METRICS" | jq -e '.application_metrics' > /dev/null 2>&1; then
    echo "  ✅ Metrics endpoint working"
    echo "$METRICS" | jq '.application_metrics'
else
    echo "  ❌ Metrics endpoint failed"
    exit 1
fi
echo ""

# 8. Cleanup - delete test room
echo "✓ Step 8: Cleaning up..."
DELETE_RESPONSE=$(curl -s -X DELETE "${BACKEND_URL}/meeting/rooms/${TEST_ROOM}?ended_by=test-user")
if echo "$DELETE_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo "  ✅ Test room deleted"
else
    echo "  ⚠️ Could not delete test room (may need manual cleanup)"
fi
echo ""

# Summary
echo "=========================================="
echo "✅ All Backend Tests Passed!"
echo "=========================================="
echo ""
echo "Backend Status: FULLY FUNCTIONAL ✅"
echo ""
echo "Next Steps:"
echo "1. Add OpenAI API key to backend/.env"
echo "2. Test frontend: cd frontend && npm run dev"
echo "3. Test end-to-end meeting flow"
echo ""
echo "WebSocket URL: ws://localhost:8000/meeting/rooms/{room_id}/ws"
echo "API Documentation: ${BACKEND_URL}/docs"
echo "=========================================="
