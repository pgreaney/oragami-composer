"""Symphony management GraphQL mutations."""

from typing import Union, Optional
import strawberry
from strawberry.types import Info
from strawberry.file_uploads import Upload
import json

from app.graphql.context import GraphQLContext
from app.graphql.types.symphony import (
    Symphony,
    SymphonyUploadResult,
    SymphonyValidationResult,
    SymphonyComplexity,
    SymphonyAsset
)
from app.services.symphony_service import symphony_service, SymphonyServiceError
from app.parsers.symphony_parser import symphony_parser


@strawberry.input
class CreateSymphonyInput:
    """Input for creating a symphony."""
    
    name: str
    algorithm_json: str
    description: Optional[str] = None


@strawberry.input
class UpdateSymphonyInput:
    """Input for updating a symphony."""
    
    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    algorithm_json: Optional[str] = None
    is_active: Optional[bool] = None


@strawberry.type
class SymphonyError:
    """Symphony operation error."""
    
    message: str
    code: str
    field: Optional[str] = None


@strawberry.type
class SymphonyMutations:
    """Symphony-related mutations."""
    
    @strawberry.mutation
    async def create_symphony(
        self,
        info: Info[GraphQLContext],
        input: CreateSymphonyInput
    ) -> Union[Symphony, SymphonyError]:
        """Create a new symphony.
        
        Args:
            info: GraphQL context info
            input: Symphony creation input
            
        Returns:
            Created Symphony or SymphonyError
        """
        # Require authentication
        user = info.context.require_auth()
        
        try:
            symphony = symphony_service.create_symphony(
                db=info.context.db,
                user=user,
                name=input.name,
                algorithm_json=input.algorithm_json,
                description=input.description
            )
            
            return Symphony.from_model(symphony)
            
        except SymphonyServiceError as e:
            return SymphonyError(
                message=str(e),
                code="SYMPHONY_CREATE_ERROR"
            )
        except Exception as e:
            return SymphonyError(
                message="Failed to create symphony",
                code="UNEXPECTED_ERROR"
            )
    
    @strawberry.mutation
    async def upload_symphony_file(
        self,
        info: Info[GraphQLContext],
        file: Upload,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> SymphonyUploadResult:
        """Upload a symphony JSON file.
        
        Args:
            info: GraphQL context info
            file: Uploaded file
            name: Optional symphony name
            description: Optional description
            
        Returns:
            SymphonyUploadResult
        """
        # Require authentication
        user = info.context.require_auth()
        
        try:
            # Read file content
            content = await file.read()
            algorithm_json = content.decode('utf-8')
            
            # Validate JSON
            validation_result = symphony_service.validate_symphony_json(algorithm_json)
            
            # Create validation result
            validation = SymphonyValidationResult(
                is_valid=validation_result["is_valid"],
                errors=validation_result["errors"],
                warnings=validation_result["warnings"],
                complexity=SymphonyComplexity(
                    **validation_result["complexity"]
                ) if validation_result["complexity"] else None,
                assets=[
                    SymphonyAsset(
                        ticker=ticker,
                        exchange="",  # Will be filled from algorithm
                        name=""
                    ) for ticker in validation_result["assets"]
                ]
            )
            
            # If valid, create symphony
            if validation_result["is_valid"]:
                try:
                    symphony = symphony_service.create_symphony(
                        db=info.context.db,
                        user=user,
                        name=name or file.filename.replace('.json', ''),
                        algorithm_json=algorithm_json,
                        description=description
                    )
                    
                    return SymphonyUploadResult(
                        success=True,
                        symphony=Symphony.from_model(symphony),
                        validation=validation
                    )
                    
                except SymphonyServiceError as e:
                    return SymphonyUploadResult(
                        success=False,
                        error=str(e),
                        validation=validation
                    )
            else:
                return SymphonyUploadResult(
                    success=False,
                    error="Symphony validation failed",
                    validation=validation
                )
                
        except json.JSONDecodeError:
            return SymphonyUploadResult(
                success=False,
                error="Invalid JSON file"
            )
        except Exception as e:
            return SymphonyUploadResult(
                success=False,
                error=f"Upload failed: {str(e)}"
            )
    
    @strawberry.mutation
    async def update_symphony(
        self,
        info: Info[GraphQLContext],
        input: UpdateSymphonyInput
    ) -> Union[Symphony, SymphonyError]:
        """Update an existing symphony.
        
        Args:
            info: GraphQL context info
            input: Symphony update input
            
        Returns:
            Updated Symphony or SymphonyError
        """
        # Require authentication
        user = info.context.require_auth()
        
        # Get symphony
        symphony = symphony_service.get_symphony_by_id(
            info.context.db,
            input.id,
            user
        )
        
        if not symphony:
            return SymphonyError(
                message="Symphony not found",
                code="SYMPHONY_NOT_FOUND"
            )
        
        try:
            symphony = symphony_service.update_symphony(
                db=info.context.db,
                symphony=symphony,
                name=input.name,
                description=input.description,
                algorithm_json=input.algorithm_json,
                is_active=input.is_active
            )
            
            return Symphony.from_model(symphony)
            
        except SymphonyServiceError as e:
            return SymphonyError(
                message=str(e),
                code="SYMPHONY_UPDATE_ERROR"
            )
    
    @strawberry.mutation
    async def delete_symphony(
        self,
        info: Info[GraphQLContext],
        id: int
    ) -> Union[bool, SymphonyError]:
        """Delete a symphony.
        
        Args:
            info: GraphQL context info
            id: Symphony ID
            
        Returns:
            True if deleted or SymphonyError
        """
        # Require authentication
        user = info.context.require_auth()
        
        # Get symphony
        symphony = symphony_service.get_symphony_by_id(
            info.context.db,
            id,
            user
        )
        
        if not symphony:
            return SymphonyError(
                message="Symphony not found",
                code="SYMPHONY_NOT_FOUND"
            )
        
        try:
            return symphony_service.delete_symphony(info.context.db, symphony)
            
        except SymphonyServiceError as e:
            return SymphonyError(
                message=str(e),
                code="SYMPHONY_DELETE_ERROR"
            )
    
    @strawberry.mutation
    async def toggle_symphony_active(
        self,
        info: Info[GraphQLContext],
        id: int
    ) -> Union[Symphony, SymphonyError]:
        """Toggle symphony active status.
        
        Args:
            info: GraphQL context info
            id: Symphony ID
            
        Returns:
            Updated Symphony or SymphonyError
        """
        # Require authentication
        user = info.context.require_auth()
        
        # Get symphony
        symphony = symphony_service.get_symphony_by_id(
            info.context.db,
            id,
            user
        )
        
        if not symphony:
            return SymphonyError(
                message="Symphony not found",
                code="SYMPHONY_NOT_FOUND"
            )
        
        try:
            symphony = symphony_service.toggle_symphony_active(
                info.context.db,
                symphony
            )
            
            return Symphony.from_model(symphony)
            
        except Exception as e:
            return SymphonyError(
                message="Failed to toggle symphony status",
                code="SYMPHONY_TOGGLE_ERROR"
            )
    
    @strawberry.mutation
    async def duplicate_symphony(
        self,
        info: Info[GraphQLContext],
        id: int,
        new_name: Optional[str] = None
    ) -> Union[Symphony, SymphonyError]:
        """Duplicate an existing symphony.
        
        Args:
            info: GraphQL context info
            id: Symphony ID to duplicate
            new_name: Name for the duplicate
            
        Returns:
            New Symphony or SymphonyError
        """
        # Require authentication
        user = info.context.require_auth()
        
        # Get original symphony
        symphony = symphony_service.get_symphony_by_id(
            info.context.db,
            id,
            user
        )
        
        if not symphony:
            return SymphonyError(
                message="Symphony not found",
                code="SYMPHONY_NOT_FOUND"
            )
        
        try:
            new_symphony = symphony_service.duplicate_symphony(
                info.context.db,
                symphony,
                new_name
            )
            
            return Symphony.from_model(new_symphony)
            
        except SymphonyServiceError as e:
            return SymphonyError(
                message=str(e),
                code="SYMPHONY_DUPLICATE_ERROR"
            )
    
    @strawberry.mutation
    async def validate_symphony_json(
        self,
        info: Info[GraphQLContext],
        algorithm_json: str
    ) -> SymphonyValidationResult:
        """Validate symphony JSON without creating.
        
        Args:
            info: GraphQL context info
            algorithm_json: Algorithm JSON to validate
            
        Returns:
            SymphonyValidationResult
        """
        # Require authentication
        info.context.require_auth()
        
        # Validate
        result = symphony_service.validate_symphony_json(algorithm_json)
        
        # Create response
        return SymphonyValidationResult(
            is_valid=result["is_valid"],
            errors=result["errors"],
            warnings=result["warnings"],
            complexity=SymphonyComplexity(
                **result["complexity"]
            ) if result["complexity"] else SymphonyComplexity(
                total_steps=0,
                max_depth=0,
                unique_assets=0,
                if_conditions=0,
                filters=0,
                groups=0,
                weighting_strategies=0
            ),
            assets=[
                SymphonyAsset(
                    ticker=ticker,
                    exchange="",
                    name=""
                ) for ticker in result["assets"]
            ]
        )
