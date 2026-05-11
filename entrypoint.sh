#!/bin/bash
# TrackIt Production Startup Script (Linux/macOS)
# Starts production services with Gunicorn

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
DJANGO_PORT=${DJANGO_PORT:-8000}
WORKERS=${WORKERS:-4}
THREADS=${THREADS:-2}
LOG_DIR="/app/logs"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"

# Create logs directory
mkdir -p $LOG_DIR

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  TrackIt Production Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Change to Django directory
cd trackit

# Run migrations
echo -e "${YELLOW}Running migrations...${NC}"
python manage.py migrate --noinput
echo -e "${GREEN}✓ Migrations completed${NC}"

# Collect static files
echo -e "${YELLOW}Collecting static files...${NC}"
python manage.py collectstatic --noinput --clear
echo -e "${GREEN}✓ Static files collected${NC}"
echo ""

# Start services
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Starting Production Services${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Start Celery Worker
echo -e "${YELLOW}Starting Celery Worker ($WORKERS processes)...${NC}"
touch $LOG_DIR/celery_worker.log
nohup celery -A config worker \
    --loglevel=info \
    --concurrency=$WORKERS \
    --pool=prefork \
    -Q trackit \
    > $LOG_DIR/celery_worker.log 2>&1 &
WORKER_PID=$!
echo -e "${GREEN}✓ Celery Worker started (PID: $WORKER_PID)${NC}"
echo ""

sleep 2

# Start Celery Beat
echo -e "${YELLOW}Starting Celery Beat...${NC}"
touch $LOG_DIR/celery_beat.log
nohup celery -A config beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    > $LOG_DIR/celery_beat.log 2>&1 &
BEAT_PID=$!
echo -e "${GREEN}✓ Celery Beat started (PID: $BEAT_PID)${NC}"
echo ""

sleep 2

# Start Gunicorn
echo -e "${YELLOW}Starting Gunicorn ($WORKERS workers, $THREADS threads)...${NC}"
touch $LOG_DIR/gunicorn-access.log
touch $LOG_DIR/gunicorn-error.log
nohup gunicorn config.wsgi:application \
    --bind $BIND_ADDRESS:$DJANGO_PORT \
    --workers $WORKERS \
    --threads $THREADS \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 120 \
    --access-logfile $LOG_DIR/gunicorn-access.log \
    --error-logfile $LOG_DIR/gunicorn-error.log \
    > $LOG_DIR/gunicorn.log 2>&1 &
GUNICORN_PID=$!
echo -e "${GREEN}✓ Gunicorn started (PID: $GUNICORN_PID)${NC}"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Services Running${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "🌐 Server: http://$BIND_ADDRESS:$DJANGO_PORT"
echo "📊 Dashboard: http://$BIND_ADDRESS:$DJANGO_PORT/dashboard/"
echo "🔧 Admin: http://$BIND_ADDRESS:$DJANGO_PORT/admin/"
echo "📡 API: http://$BIND_ADDRESS:$DJANGO_PORT/api/v1/"
echo ""
echo "📝 Service Logs:"
echo "   Gunicorn: $LOG_DIR/gunicorn.log"
echo "   Celery Worker: $LOG_DIR/celery_worker.log"
echo "   Celery Beat: $LOG_DIR/celery_beat.log"
echo ""
echo "🛑 To stop services:"
echo "   kill $GUNICORN_PID   # Stop Django"
echo "   kill $WORKER_PID     # Stop Worker"
echo "   kill $BEAT_PID       # Stop Beat"
echo ""
echo "Or run: pkill -f gunicorn; pkill -f 'celery worker'; pkill -f 'celery beat'"
echo ""

# Cleanup on exit
trap "echo 'Shutting down...'; kill $GUNICORN_PID $WORKER_PID $BEAT_PID 2>/dev/null || true" EXIT

# Wait for background processes
wait
