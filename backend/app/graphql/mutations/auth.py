"""Authentication GraphQL mutations."""

from typing import Union
import strawberry
from strawberry.types import Info
from sqlalchemy.exc import IntegrityError

from app.graphql.context import GraphQLContext
from app.graphql.types.auth import (
    LoginInput,
    RegisterInput,
    ChangePasswordInput,
    UpdateProfileInput,
    LoginSuccess,
    RegisterSuccess,
    AuthError,
    AuthTokens,
    TokenRefreshSuccess
)
from app.graphql.types.user import User
from app.services.auth_service import auth_service
from app.schemas.auth import UserCreate, UserLogin, TokenRefresh


@strawberry.type
class AuthMutations:
    """Authentication-related mutations."""
    
    @strawberry.mutation
    async def login(
        self,
        info: Info[GraphQLContext],
        input: LoginInput
    ) -> Union[LoginSuccess, AuthError]:
        """Login with email and password.
        
        Args:
            info: GraphQL context info
            input: Login credentials
            
        Returns:
            LoginSuccess or AuthError
        """
        try:
            # Create pydantic model for validation
            user_login = UserLogin(
                email=input.email,
                password=input.password
            )
            
            # Authenticate user
            user = auth_service.authenticate_user(
                info.context.db,
                user_login
            )
            
            if not user:
                return AuthError(
                    message="Invalid email or password",
                    code="INVALID_CREDENTIALS"
                )
            
            # Create tokens
            tokens = auth_service.create_tokens(user)
            
            return LoginSuccess(
                user=User.from_model(user),
                tokens=AuthTokens(
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    token_type=tokens.token_type
                )
            )
            
        except Exception as e:
            return AuthError(
                message="Login failed",
                code="LOGIN_ERROR"
            )
    
    @strawberry.mutation
    async def register(
        self,
        info: Info[GraphQLContext],
        input: RegisterInput
    ) -> Union[RegisterSuccess, AuthError]:
        """Register a new user.
        
        Args:
            info: GraphQL context info
            input: Registration data
            
        Returns:
            RegisterSuccess or AuthError
        """
        try:
            # Validate passwords match
            if input.password != input.confirm_password:
                return AuthError(
                    message="Passwords do not match",
                    code="PASSWORD_MISMATCH",
                    field="confirm_password"
                )
            
            # Create pydantic model for validation
            user_create = UserCreate(
                email=input.email,
                username=input.username,
                password=input.password,
                confirm_password=input.confirm_password
            )
            
            # Register user
            user = auth_service.register_user(
                info.context.db,
                user_create
            )
            
            if not user:
                return AuthError(
                    message="Registration failed",
                    code="REGISTRATION_ERROR"
                )
            
            return RegisterSuccess(
                user=User.from_model(user)
            )
            
        except ValueError as e:
            # Extract field from error message if possible
            error_msg = str(e)
            field = None
            
            if "email" in error_msg.lower():
                field = "email"
            elif "password" in error_msg.lower():
                field = "password"
            elif "username" in error_msg.lower():
                field = "username"
            
            return AuthError(
                message=error_msg,
                code="VALIDATION_ERROR",
                field=field
            )
        except Exception as e:
            return AuthError(
                message="Registration failed",
                code="REGISTRATION_ERROR"
            )
    
    @strawberry.mutation
    async def refresh_tokens(
        self,
        info: Info[GraphQLContext],
        refresh_token: str
    ) -> Union[TokenRefreshSuccess, AuthError]:
        """Refresh access token using refresh token.
        
        Args:
            info: GraphQL context info
            refresh_token: Refresh token
            
        Returns:
            TokenRefreshSuccess or AuthError
        """
        try:
            tokens = auth_service.refresh_access_token(
                info.context.db,
                refresh_token
            )
            
            if not tokens:
                return AuthError(
                    message="Invalid refresh token",
                    code="INVALID_REFRESH_TOKEN"
                )
            
            return TokenRefreshSuccess(
                tokens=AuthTokens(
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token,
                    token_type=tokens.token_type
                )
            )
            
        except Exception as e:
            return AuthError(
                message="Token refresh failed",
                code="REFRESH_ERROR"
            )
    
    @strawberry.mutation
    async def change_password(
        self,
        info: Info[GraphQLContext],
        input: ChangePasswordInput
    ) -> Union[User, AuthError]:
        """Change current user's password.
        
        Args:
            info: GraphQL context info
            input: Password change data
            
        Returns:
            Updated User or AuthError
        """
        # Require authentication
        current_user = info.context.require_auth()
        
        try:
            # Validate passwords match
            if input.new_password != input.confirm_password:
                return AuthError(
                    message="Passwords do not match",
                    code="PASSWORD_MISMATCH",
                    field="confirm_password"
                )
            
            # Change password
            success = auth_service.change_password(
                info.context.db,
                current_user,
                input.current_password,
                input.new_password
            )
            
            if success:
                return User.from_model(current_user)
            else:
                return AuthError(
                    message="Password change failed",
                    code="PASSWORD_CHANGE_ERROR"
                )
                
        except ValueError as e:
            return AuthError(
                message=str(e),
                code="VALIDATION_ERROR",
                field="current_password" if "current" in str(e).lower() else "new_password"
            )
        except Exception as e:
            return AuthError(
                message="Password change failed",
                code="PASSWORD_CHANGE_ERROR"
            )
    
    @strawberry.mutation
    async def update_profile(
        self,
        info: Info[GraphQLContext],
        input: UpdateProfileInput
    ) -> Union[User, AuthError]:
        """Update current user's profile.
        
        Args:
            info: GraphQL context info
            input: Profile update data
            
        Returns:
            Updated User or AuthError
        """
        # Require authentication
        current_user = info.context.require_auth()
        
        try:
            # Update fields if provided
            if input.username is not None:
                current_user.username = input.username
            
            if input.email is not None:
                # Check if email is already taken
                from app.models.user import User as UserModel
                existing_user = info.context.db.query(UserModel).filter(
                    UserModel.email == input.email,
                    UserModel.id != current_user.id
                ).first()
                
                if existing_user:
                    return AuthError(
                        message="Email already in use",
                        code="EMAIL_EXISTS",
                        field="email"
                    )
                
                current_user.email = input.email
            
            info.context.db.commit()
            info.context.db.refresh(current_user)
            
            return User.from_model(current_user)
            
        except Exception as e:
            info.context.db.rollback()
            return AuthError(
                message="Profile update failed",
                code="UPDATE_ERROR"
            )
    
    @strawberry.mutation
    async def logout(
        self,
        info: Info[GraphQLContext]
    ) -> bool:
        """Logout current user.
        
        Note: With JWT tokens, logout is typically handled client-side
        by removing stored tokens.
        
        Args:
            info: GraphQL context info
            
        Returns:
            True on success
        """
        # Require authentication
        info.context.require_auth()
        
        # With JWT, we just return success
        # Client should remove tokens
        return True
    
    @strawberry.mutation
    async def deactivate_account(
        self,
        info: Info[GraphQLContext]
    ) -> Union[bool, AuthError]:
        """Deactivate current user's account.
        
        Args:
            info: GraphQL context info
            
        Returns:
            True on success or AuthError
        """
        # Require authentication
        current_user = info.context.require_auth()
        
        try:
            success = auth_service.deactivate_user(
                info.context.db,
                current_user
            )
            
            return success
            
        except Exception as e:
            return AuthError(
                message="Account deactivation failed",
                code="DEACTIVATION_ERROR"
            )
