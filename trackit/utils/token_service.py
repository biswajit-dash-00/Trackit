"""Token Service for generating and validating secure tokens"""
import jwt
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class TokenService:
    """Service to generate and validate JWT tokens"""
    
    TOKEN_EXPIRY_HOURS = 2
    
    @classmethod
    def generate_token(cls, filter_id: int, assignee_email: str) -> str:
        """
        Generate a JWT token for secure update link
        
        Args:
            filter_id: Filter ID
            assignee_email: Assignee email
            
        Returns:
            JWT token string
        """
        try:
            now = timezone.now()
            payload = {
                'filter_id': filter_id,
                'assignee_email': assignee_email,
                'iat': now,
                'exp': now + timedelta(hours=cls.TOKEN_EXPIRY_HOURS),
            }
            
            token = jwt.encode(
                payload,
                settings.SECRET_KEY,
                algorithm='HS256'
            )
            
            return token
        
        except Exception as e:
            logger.error(f"Failed to generate token: {str(e)}")
            raise
    
    @classmethod
    def validate_token(cls, token: str) -> dict:
        """
        Validate and decode JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload dictionary if valid
            
        Raises:
            Exception if token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
            return payload
        
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token has expired")
            raise Exception("Token has expired")
        
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise Exception("Invalid token")
