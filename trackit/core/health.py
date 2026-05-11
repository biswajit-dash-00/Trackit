"""Health check and status endpoints"""
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis
from django.conf import settings


def health_check(request):
    """Basic health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'TrackIt'
    })


def detailed_health_check(request):
    """Detailed health check with dependency status"""
    status = {
        'status': 'healthy',
        'timestamp': __import__('django.utils.timezone', fromlist=['now']).now().isoformat(),
        'database': check_database(),
        'redis': check_redis(),
        'cache': check_cache(),
    }
    
    # If any service is down, overall status is degraded
    if not all([
        status['database']['status'] == 'healthy',
        status['redis']['status'] == 'healthy',
    ]):
        status['status'] = 'degraded'
    
    return JsonResponse(status)


def check_database():
    """Check database connectivity"""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return {'status': 'healthy', 'message': 'Database connected'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}


def check_redis():
    """Check Redis connectivity"""
    try:
        redis_client = redis.from_url(settings.CELERY_BROKER_URL)
        redis_client.ping()
        return {'status': 'healthy', 'message': 'Redis connected'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}


def check_cache():
    """Check cache functionality"""
    try:
        cache.set('health_check', 'ok', 60)
        if cache.get('health_check') == 'ok':
            return {'status': 'healthy', 'message': 'Cache working'}
        return {'status': 'unhealthy', 'message': 'Cache read failed'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}
