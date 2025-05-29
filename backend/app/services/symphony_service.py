"""Symphony business logic and algorithm interpreter."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.models.symphony import Symphony
from app.parsers.symphony_parser import symphony_parser, SymphonyParsingError
from app.parsers.validator import symphony_validator, ValidationError
from app.parsers.schemas import SymphonySchema


class SymphonyServiceError(Exception):
    """Custom exception for symphony service errors."""
    pass


class SymphonyService:
    """Service for managing symphonies and their algorithms."""
    
    # Maximum symphonies per user (initial limit)
    MAX_SYMPHONIES_PER_USER = 40
    
    def create_symphony(
        self,
        db: Session,
        user: User,
        name: str,
        algorithm_json: str,
        description: Optional[str] = None
    ) -> Symphony:
        """Create a new symphony.
        
        Args:
            db: Database session
            user: Symphony owner
            name: Symphony name
            algorithm_json: Algorithm JSON string
            description: Optional description
            
        Returns:
            Created symphony
            
        Raises:
            SymphonyServiceError: If creation fails
        """
        # Check symphony limit
        if self.count_user_symphonies(db, user) >= self.MAX_SYMPHONIES_PER_USER:
            raise SymphonyServiceError(
                f"Symphony limit reached. Maximum {self.MAX_SYMPHONIES_PER_USER} symphonies allowed per user."
            )
        
        # Parse and validate algorithm
        try:
            symphony_schema = symphony_parser.parse_json(algorithm_json)
            warnings = symphony_validator.validate(symphony_schema)
        except (SymphonyParsingError, ValidationError) as e:
            raise SymphonyServiceError(f"Invalid symphony algorithm: {str(e)}")
        
        # Create symphony
        try:
            symphony = Symphony(
                user_id=user.id,
                name=name or symphony_schema.name,
                description=description or symphony_schema.description,
                rebalance_frequency=symphony_schema.rebalance.value,
                algorithm=symphony_schema.dict(by_alias=True, exclude_none=True),
                is_active=True
            )
            
            db.add(symphony)
            db.commit()
            db.refresh(symphony)
            
            return symphony
            
        except IntegrityError as e:
            db.rollback()
            raise SymphonyServiceError(f"Database error: {str(e)}")
    
    def update_symphony(
        self,
        db: Session,
        symphony: Symphony,
        name: Optional[str] = None,
        description: Optional[str] = None,
        algorithm_json: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Symphony:
        """Update an existing symphony.
        
        Args:
            db: Database session
            symphony: Symphony to update
            name: New name (optional)
            description: New description (optional)
            algorithm_json: New algorithm JSON (optional)
            is_active: New active status (optional)
            
        Returns:
            Updated symphony
            
        Raises:
            SymphonyServiceError: If update fails
        """
        # Update fields
        if name is not None:
            symphony.name = name
        
        if description is not None:
            symphony.description = description
        
        if is_active is not None:
            symphony.is_active = is_active
        
        # Update algorithm if provided
        if algorithm_json is not None:
            try:
                symphony_schema = symphony_parser.parse_json(algorithm_json)
                warnings = symphony_validator.validate(symphony_schema)
                
                symphony.algorithm = symphony_schema.dict(by_alias=True, exclude_none=True)
                symphony.rebalance_frequency = symphony_schema.rebalance.value
                
            except (SymphonyParsingError, ValidationError) as e:
                raise SymphonyServiceError(f"Invalid symphony algorithm: {str(e)}")
        
        symphony.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(symphony)
            return symphony
            
        except Exception as e:
            db.rollback()
            raise SymphonyServiceError(f"Update failed: {str(e)}")
    
    def delete_symphony(self, db: Session, symphony: Symphony) -> bool:
        """Delete a symphony.
        
        Args:
            db: Database session
            symphony: Symphony to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            SymphonyServiceError: If deletion fails
        """
        try:
            db.delete(symphony)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            raise SymphonyServiceError(f"Deletion failed: {str(e)}")
    
    def get_symphony_by_id(
        self,
        db: Session,
        symphony_id: int,
        user: Optional[User] = None
    ) -> Optional[Symphony]:
        """Get symphony by ID.
        
        Args:
            db: Database session
            symphony_id: Symphony ID
            user: Optional user for ownership check
            
        Returns:
            Symphony or None if not found
        """
        query = db.query(Symphony).filter(Symphony.id == symphony_id)
        
        if user:
            query = query.filter(Symphony.user_id == user.id)
        
        return query.first()
    
    def get_user_symphonies(
        self,
        db: Session,
        user: User,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = False
    ) -> List[Symphony]:
        """Get user's symphonies.
        
        Args:
            db: Database session
            user: Symphony owner
            limit: Maximum results
            offset: Result offset
            active_only: Only return active symphonies
            
        Returns:
            List of symphonies
        """
        query = db.query(Symphony).filter(Symphony.user_id == user.id)
        
        if active_only:
            query = query.filter(Symphony.is_active == True)
        
        return query.order_by(Symphony.created_at.desc()).offset(offset).limit(limit).all()
    
    def count_user_symphonies(self, db: Session, user: User) -> int:
        """Count user's symphonies.
        
        Args:
            db: Database session
            user: Symphony owner
            
        Returns:
            Symphony count
        """
        return db.query(Symphony).filter(Symphony.user_id == user.id).count()
    
    def validate_symphony_json(self, algorithm_json: str) -> Dict[str, Any]:
        """Validate symphony JSON and return detailed result.
        
        Args:
            algorithm_json: Algorithm JSON string
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "is_valid": False,
            "errors": [],
            "warnings": [],
            "complexity": None,
            "assets": []
        }
        
        try:
            # Parse symphony
            symphony_schema = symphony_parser.parse_json(algorithm_json)
            
            # Validate
            warnings = symphony_validator.validate(symphony_schema)
            
            # Get complexity metrics
            metrics = symphony_parser.get_complexity_metrics(symphony_schema)
            
            # Get assets
            assets = symphony_parser.extract_assets(symphony_schema)
            
            result.update({
                "is_valid": True,
                "warnings": warnings,
                "complexity": metrics,
                "assets": assets
            })
            
        except SymphonyParsingError as e:
            result["errors"].append(f"Parsing error: {str(e)}")
        except ValidationError as e:
            result["errors"].append(f"Validation error: {str(e)}")
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def duplicate_symphony(
        self,
        db: Session,
        symphony: Symphony,
        new_name: Optional[str] = None
    ) -> Symphony:
        """Duplicate an existing symphony.
        
        Args:
            db: Database session
            symphony: Symphony to duplicate
            new_name: Name for the duplicate
            
        Returns:
            New symphony
            
        Raises:
            SymphonyServiceError: If duplication fails
        """
        # Generate new name if not provided
        if not new_name:
            new_name = f"{symphony.name} (Copy)"
        
        # Create duplicate
        return self.create_symphony(
            db=db,
            user=symphony.user,
            name=new_name,
            algorithm_json=symphony.algorithm_json,
            description=symphony.description
        )
    
    def toggle_symphony_active(
        self,
        db: Session,
        symphony: Symphony
    ) -> Symphony:
        """Toggle symphony active status.
        
        Args:
            db: Database session
            symphony: Symphony to toggle
            
        Returns:
            Updated symphony
        """
        symphony.is_active = not symphony.is_active
        symphony.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(symphony)
        
        return symphony
    
    def record_execution(
        self,
        db: Session,
        symphony: Symphony,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Record symphony execution.
        
        Args:
            db: Database session
            symphony: Executed symphony
            success: Whether execution was successful
            error: Error message if failed
        """
        symphony.last_executed_at = datetime.utcnow()
        symphony.execution_count += 1
        
        if not success and error:
            symphony.last_execution_error = error
        
        db.commit()
    
    def get_active_symphonies_for_execution(
        self,
        db: Session,
        rebalance_frequency: Optional[str] = None
    ) -> List[Symphony]:
        """Get all active symphonies ready for execution.
        
        Args:
            db: Database session
            rebalance_frequency: Filter by rebalance frequency
            
        Returns:
            List of symphonies to execute
        """
        query = db.query(Symphony).filter(Symphony.is_active == True)
        
        if rebalance_frequency:
            query = query.filter(Symphony.rebalance_frequency == rebalance_frequency)
        
        # TODO: Add additional filters based on last execution time
        # and rebalance frequency to avoid over-execution
        
        return query.all()


# Global service instance
symphony_service = SymphonyService()
