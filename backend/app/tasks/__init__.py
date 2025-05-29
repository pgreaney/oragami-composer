"""
Celery Tasks Module for Origami Composer

This module contains all background tasks for:
- Algorithm execution
- Technical indicator calculations
- Symphony scheduling
- Error handling
- Market data operations
- Position management
"""

from app.celery_app import celery_app

__all__ = ['celery_app']
