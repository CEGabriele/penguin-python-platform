# Load Testing Guide

This guide explains how to run comprehensive load tests on the Penguin Coding School dashboard and editor.

## What's Included

- **`setup_load_test.py`** — Django management command that creates realistic test data
- **`locustfile.py`** — Comprehensive Locust load test that simulates real user workflows

## Setup

### 1. Create Test Data

First, set up the test data with realistic classes, assignments, students, and projects:

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
python manage.py setup_load_test --num-students 10 --num-classes 2
```

This creates:
- 1 test teacher: `loadtest_teacher1`
- N test students: `loadtest_student1` through `loadtest_studentN`
- M test classes with assignments
- Pre-created projects for each student/assignment/class combination

All test accounts use password: `<removed>`

### 2. Start Django Dev Server

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
python manage.py runserver
```

Keep this running in one terminal.

### 3. Run Load Test

In another terminal:

```bash
locust -f locustfile.py --host=http://localhost:8000
```

This starts the Locust web UI at `http://localhost:8000:8089`

## Load Test Workflow

The load test simulates two types of users:

### StudentLoadTestUser (Primary)
Students perform these realistic tasks:
1. **View Dashboard** — Browse their enrolled classes and assignments
2. **View Class** — View class assignments and extract assignment IDs
3. **Open Editor & Work** — Open a code editor for an assignment and:
   - Auto-create a project for the assignment
   - Write and autosave code samples
4. **Create New Files** — Add new `.py` files to projects
5. **List Project Files** — See all files in a project

### TeacherLoadTestUser (Secondary)
Teachers perform these tasks:
1. **View Dashboard** — See all their classes
2. **View Class** — View class details and assignments
3. **View Submissions** — See student submissions for assignments
4. **View Student Code** — Review student project code

## What Gets Tested

✓ **Authentication** — Login for multiple concurrent users  
✓ **Session Management** — Proper CSRF tokens and cookies  
✓ **Dashboard Performance** — Multiple students/teachers viewing dashboards simultaneously  
✓ **Editor Functionality** — Code autosave, file creation, file listing  
✓ **Access Control** — Students can only access their own projects  
✓ **Database Queries** — Class/assignment/project lookups under load  

## Running the Test

### From Locust Web UI (Recommended)

1. Open http://localhost:8089
2. Set **Number of users**: 50 (or more for stress testing)
3. Set **Spawn rate**: 5 (users per second)
4. Click **Start swarming**

Watch real-time stats:
- Request/sec
- Response times (P50, P95, P99)
- Error rates and failures
- Request types and their performance

### From Command Line

```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m \
  --headless
```

## Interpreting Results

### Good Signs ✓
- **Response times** < 500ms P95
- **Error rate** < 1%
- **Consistent throughput** (stable requests/sec)
- **No database timeouts**

### Red Flags ✗
- 403 errors — Access control issues
- 404 errors — URLs changed or test data missing
- 500 errors — Unhandled exceptions in views
- Increasing response times — Database bottleneck or memory leak
- High error rate under 100 users — System not production-ready

## Debugging Failed Requests

Check the Locust web UI for:
1. **Failures tab** — Click to see detailed error messages
2. **Response bodies** — What Django returned
3. **Exceptions** — Python stack traces

For more detail, check Django logs:
```bash
tail -f /path/to/django.log
```

## Scaling Up

For larger tests:

### Increase Students
```bash
python manage.py setup_load_test --num-students 100 --num-classes 5
```

### Distributed Load Testing
Run Locust across multiple machines:
```bash
# Primary machine (controller)
locust -f locustfile.py --host=http://target-app:8000 --master --web

# Other machines (workers)
locust -f locustfile.py --host=http://target-app:8000 --worker --master-host=<primary-ip>
```

## Cleanup

To reset and start over:
```bash
# Remove test data
python manage.py shell << EOF
from django.contrib.auth.models import User
User.objects.filter(username__startswith='loadtest_').delete()
EOF

# Then re-run setup
python manage.py setup_load_test --num-students 10 --num-classes 2
```

## Troubleshooting

### Users Can't Login
- Verify test data was created: `python manage.py shell`
  ```python
  from django.contrib.auth.models import User
  User.objects.filter(username__startswith='loadtest_').count()
  ```
- Check Django logs for auth errors

### Requests Hitting 403 Forbidden
- Students trying to access projects they don't own
- Teachers trying to access classes not assigned to them
- Verify test data relationships are correct

### 404 Errors on Editor
- Assignment IDs or class codes don't exist
- The locustfile needs the test data structure to discover them dynamically
- Re-run `setup_load_test` to ensure data exists

### Slow Response Times
1. Check if Django is blocking on I/O (files, database)
2. Monitor server CPU/memory during test
3. Look at database query times with Django debug toolbar
4. Check if autosave endpoint is slow (file I/O issue?)

## Performance Baseline

With default test data (10 students, 2 classes) on a modern dev machine:
- **50 users** — Should handle with <200ms P95
- **100 users** — Expect ~300-500ms P95, some errors starting
- **200+ users** — Likely to see failures (production infrastructure needed)

Your results will vary based on hardware and database performance.
