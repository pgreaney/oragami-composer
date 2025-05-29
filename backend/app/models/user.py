"""
User model with OAuth token storage for Origami Composer
Handles user authentication and Alpaca OAuth integration
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.models import BaseModel


class User(BaseModel):
    """
    User model for authentication and account management
    
    Stores user credentials and encrypted Alpaca OAuth tokens
    for paper trading API access. Supports multi-tenant architecture
    with user-specific data isolation.
    
    Attributes:
        email: Unique user email address for login
        password_hash: Bcrypt hashed password for authentication
        is_active: Flag to enable/disable user accounts
        alpaca_oauth_token: Encrypted OAuth access token for Alpaca API
        alpaca_refresh_token: Encrypted OAuth refresh token
        alpaca_token_scope: OAuth scopes granted by user
        alpaca_token_expiry: Token expiration timestamp
        oauth_connected_at: Timestamp when OAuth was connected
        
    Relationships:
        symphonies: One-to-many relationship with Symphony model
    """
    __tablename__ = "users"
    
    # Authentication fields
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Alpaca OAuth fields - tokens are encrypted at rest
    alpaca_oauth_token = Column(Text, nullable=True)  # Encrypted
    alpaca_refresh_token = Column(Text, nullable=True)  # Encrypted
    alpaca_token_scope = Column(String(255), nullable=True)
    alpaca_token_expiry = Column(DateTime(timezone=True), nullable=True)
    oauth_connected_at = Column(DateTime(timezone=True), nullable=True)
    
    # User preferences
    preferred_theme = Column(String(20), default="light", nullable=False)
    email_notifications = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    symphonies = relationship(
        "Symphony",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self):
        """String representation of User object"""
        return f"<User(email='{self.email}', alpaca_connected={self.has_alpaca_connection})>"
    
    @property
    def has_alpaca_connection(self) -> bool:
        """
        Check if user has active Alpaca OAuth connection
        
        Returns:
            bool: True if user has valid OAuth tokens
        """
        return bool(self.alpaca_oauth_token and self.oauth_connected_at)
    
    @property
    def symphony_count(self) -> int:
        """
        Get count of user's symphonies
        
        Returns:
            int: Number of symphonies owned by user
        """
        return self.symphonies.count() if self.symphonies else 0
