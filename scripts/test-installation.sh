#!/bin/bash
#
# Test MCP Trust Anchor Installation
#
# Usage: ./test-installation.sh [server-url]
#

set -e

# Configuration
SERVER_URL="${1:-http://localhost:8000}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}======================================${NC}"
echo -e "${CYAN}MCP Trust Anchor - Installation Test${NC}"
echo -e "${CYAN}======================================${NC}"
echo
echo "Server: $SERVER_URL"
echo

PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local endpoint=$2
    local expected_status=${3:-200}

    printf "Testing %-30s " "$name..."

    response=$(curl -s -w "%{http_code}" -o /tmp/test_response.json "$SERVER_URL$endpoint" 2>/dev/null)

    if [[ "$response" == "$expected_status" ]]; then
        echo -e "${GREEN}PASS${NC} (HTTP $response)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC} (HTTP $response, expected $expected_status)"
        ((FAILED++))
        return 1
    fi
}

# Test 1: Health endpoint
echo -e "${YELLOW}[1] Basic Connectivity${NC}"
test_endpoint "Health check" "/health"
echo

# Test 2: Public key endpoint
echo -e "${YELLOW}[2] Security Infrastructure${NC}"
test_endpoint "Public key endpoint" "/keys/public"

# Verify key format
if [[ -f /tmp/test_response.json ]]; then
    if grep -q "BEGIN PUBLIC KEY" /tmp/test_response.json 2>/dev/null || \
       jq -e '.public_key' /tmp/test_response.json >/dev/null 2>&1; then
        echo -e "  Key format:                       ${GREEN}VALID${NC}"
        ((PASSED++))
    else
        echo -e "  Key format:                       ${RED}INVALID${NC}"
        ((FAILED++))
    fi
fi
echo

# Test 3: Tool registry
echo -e "${YELLOW}[3] Tool Registry${NC}"
test_endpoint "List tools" "/tools/list"

# Check for sample tools
if [[ -f /tmp/test_response.json ]]; then
    tool_count=$(jq 'if type == "array" then length else .tools | length end' /tmp/test_response.json 2>/dev/null || echo "0")
    echo "  Tools registered: $tool_count"
fi
echo

# Test 4: Publisher API
echo -e "${YELLOW}[4] Publisher API${NC}"
test_endpoint "Publisher status" "/publisher/status"
echo

# Test 5: Subscriber registration
echo -e "${YELLOW}[5] Subscriber API${NC}"
test_endpoint "Subscriber endpoint" "/subscribers/register" "422"  # Expected: validation error (no body)
echo

# Test 6: Tool fetch (if tools exist)
echo -e "${YELLOW}[6] Tool Fetch${NC}"
if [[ "$tool_count" -gt 0 ]]; then
    # Get first tool ID
    first_tool=$(jq -r 'if type == "array" then .[0].canonical_id else .tools[0].canonical_id end' /tmp/test_response.json 2>/dev/null)
    if [[ -n "$first_tool" ]] && [[ "$first_tool" != "null" ]]; then
        test_endpoint "Fetch tool: $first_tool" "/tools/get/$first_tool"
    else
        echo -e "  No tools to test                  ${YELLOW}SKIP${NC}"
    fi
else
    echo -e "  No tools registered               ${YELLOW}SKIP${NC}"
fi
echo

# Summary
echo -e "${CYAN}======================================${NC}"
echo -e "${CYAN}Test Summary${NC}"
echo -e "${CYAN}======================================${NC}"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check server logs.${NC}"
    exit 1
fi
