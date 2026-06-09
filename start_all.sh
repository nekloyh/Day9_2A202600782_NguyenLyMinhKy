#!/bin/bash
set -euo pipefail

# Start all Legal Multi-Agent System services
# Registry must be first, then leaf agents, then orchestrators

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON=("$SCRIPT_DIR/.venv/bin/python")
elif command -v uv >/dev/null 2>&1; then
    PYTHON=(uv run python)
else
    echo "ERROR: No project virtualenv or uv installation found." >&2
    exit 1
fi

PIDS=()

cleanup() {
    if ((${#PIDS[@]} > 0)); then
        echo ""
        echo "Stopping services..."
        kill "${PIDS[@]}" 2>/dev/null || true
        wait "${PIDS[@]}" 2>/dev/null || true
        PIDS=()
    fi
}
trap cleanup EXIT INT TERM

wait_for_url() {
    local name="$1"
    local url="$2"
    local attempts="${3:-30}"

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
            echo "$name is ready."
            return 0
        fi
        sleep 1
    done

    echo "ERROR: $name did not become ready at $url" >&2
    return 1
}

echo "Starting Registry service on port 10000..."
("${PYTHON[@]}" -m registry) &
REGISTRY_PID=$!
PIDS+=("$REGISTRY_PID")
wait_for_url "Registry" "http://localhost:10000/health"

echo "Starting Tax Agent on port 10102..."
("${PYTHON[@]}" -m tax_agent) &
TAX_PID=$!
PIDS+=("$TAX_PID")

echo "Starting Compliance Agent on port 10103..."
("${PYTHON[@]}" -m compliance_agent) &
COMPLIANCE_PID=$!
PIDS+=("$COMPLIANCE_PID")
wait_for_url "Tax Agent" "http://localhost:10102/.well-known/agent-card.json"
wait_for_url "Compliance Agent" "http://localhost:10103/.well-known/agent-card.json"

echo "Starting Law Agent on port 10101..."
("${PYTHON[@]}" -m law_agent) &
LAW_PID=$!
PIDS+=("$LAW_PID")
wait_for_url "Law Agent" "http://localhost:10101/.well-known/agent-card.json"

echo "Starting Customer Agent on port 10100..."
("${PYTHON[@]}" -m customer_agent) &
CUSTOMER_PID=$!
PIDS+=("$CUSTOMER_PID")
wait_for_url "Customer Agent" "http://localhost:10100/.well-known/agent-card.json"

echo ""
echo "All services started:"
echo "  Registry:         http://localhost:10000"
echo "  Customer Agent:   http://localhost:10100"
echo "  Law Agent:        http://localhost:10101"
echo "  Tax Agent:        http://localhost:10102"
echo "  Compliance Agent: http://localhost:10103"
echo ""
echo "Run test_client.py to send a query:"
echo "  uv run python test_client.py"
echo ""
echo "Press Ctrl+C to stop all services."

# Wait for all background processes
wait "${PIDS[@]}"
