#!/bin/bash
# Quick start script for load testing

set -e

echo "================================"
echo "Penguin Coding School Load Test"
echo "================================"
echo ""

# Check if Django settings module is set
if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    echo "Setting DJANGO_SETTINGS_MODULE to mysite.settings.dev..."
    export DJANGO_SETTINGS_MODULE=mysite.settings.dev
fi

echo "Step 1: Setting up test data..."
echo "  (Creating 10 students in 2 classes)"
python manage.py setup_load_test --num-students 10 --num-classes 2

echo ""
echo "Step 2: Starting Django server..."
echo "  Running on http://localhost:8000"
echo ""
echo "In another terminal, run:"
echo "  locust -f locustfile.py --host=http://localhost:8000"
echo ""
echo "Then open http://localhost:8089 in your browser"
echo ""

python manage.py runserver
