#!/bin/bash

echo "======================================================"
echo "Capacity Test: Finding CPU Breaking Point"
echo "======================================================"
echo ""

# Usage: LOAD_TEST_HOST=https://your-site.example.com ./capacity_test.sh
HOST="${LOAD_TEST_HOST:?Set LOAD_TEST_HOST to the site to test}"

# Test at different concurrency levels
for USERS in 10 25 50 75 100 150 200; do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Testing with $USERS concurrent users (2 min run)..."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # Run Locust test and capture output
  OUTPUT=$(locust -f locustfile_simple.py --host="$HOST" \
    --headless -u $USERS -r 10 -t 2m 2>&1)

  # Extract stats from output (look for Aggregated line)
  STATS=$(echo "$OUTPUT" | grep "Aggregated" | tail -1)

  if [ ! -z "$STATS" ]; then
    echo "Response time stats:"
    echo "$STATS" | awk '{print "  Median: " $6 "ms, 95%: " $8 "ms, 99%: " $10 "ms, Avg: " $12 "ms"}'
  fi

  # Get CPU after test
  sleep 2
  echo "Instance metrics after test:"
  CPU=$(curl -s "$HOST/dashboard/api/metrics/instance-status/" 2>/dev/null | jq -r '.cpu_percent // "N/A"')
  MEM=$(curl -s "$HOST/dashboard/api/metrics/instance-status/" 2>/dev/null | jq -r '.memory_percent // "N/A"')
  echo "  CPU: ${CPU}%"
  echo "  Memory: ${MEM}%"

  # Check if we should stop (CPU too high or response times too long)
  if (( $(echo "$CPU > 85" | bc -l 2>/dev/null) )); then
    echo ""
    echo "⚠️  CPU exceeded 85% — stopping test"
    echo ""
    break
  fi

  echo ""
  sleep 5
done

echo "======================================================"
echo "Capacity Test Complete"
echo "======================================================"
