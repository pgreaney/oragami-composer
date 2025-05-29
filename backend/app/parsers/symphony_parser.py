"""Composer.trade complex JSON validation and parsing."""

import json
from typing import Dict, Any, List, Union, Type
from pydantic import ValidationError

from app.parsers.schemas import (
    SymphonySchema,
    SymphonyStep,
    AssetStep,
    GroupStep,
    FilterStep,
    IfStep,
    IfChildStep,
    WtCashEqualStep,
    WtCashSpecifiedStep,
    WtInverseVolStep,
    WtMarketCapStep,
    WtRiskParityStep,
    RootStep,
    StepType,
    Weight
)


class SymphonyParsingError(Exception):
    """Custom exception for symphony parsing errors."""
    pass


class SymphonyParser:
    """Parser for Composer.trade symphony JSON format."""
    
    # Map step type strings to their corresponding Pydantic models
    STEP_TYPE_MAPPING: Dict[str, Type[SymphonyStep]] = {
        "asset": AssetStep,
        "group": GroupStep,
        "filter": FilterStep,
        "if": IfStep,
        "if-child": IfChildStep,
        "wt-cash-equal": WtCashEqualStep,
        "wt-cash-specified": WtCashSpecifiedStep,
        "wt-inverse-vol": WtInverseVolStep,
        "wt-market-cap": WtMarketCapStep,
        "wt-risk-parity": WtRiskParityStep,
        "root": RootStep,
    }
    
    def parse_json(self, json_str: str) -> SymphonySchema:
        """Parse symphony JSON string.
        
        Args:
            json_str: JSON string representation of symphony
            
        Returns:
            Validated SymphonySchema object
            
        Raises:
            SymphonyParsingError: If parsing fails
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise SymphonyParsingError(f"Invalid JSON: {str(e)}")
        
        return self.parse_dict(data)
    
    def parse_dict(self, data: Dict[str, Any]) -> SymphonySchema:
        """Parse symphony dictionary.
        
        Args:
            data: Dictionary representation of symphony
            
        Returns:
            Validated SymphonySchema object
            
        Raises:
            SymphonyParsingError: If parsing fails
        """
        try:
            # Parse children recursively
            if "children" in data:
                data["children"] = self._parse_children(data["children"])
            
            # Create and validate the schema
            return SymphonySchema(**data)
            
        except ValidationError as e:
            raise SymphonyParsingError(f"Validation error: {str(e)}")
        except Exception as e:
            raise SymphonyParsingError(f"Parsing error: {str(e)}")
    
    def _parse_children(self, children: List[Dict[str, Any]]) -> List[SymphonyStep]:
        """Parse children steps recursively.
        
        Args:
            children: List of child step dictionaries
            
        Returns:
            List of parsed SymphonyStep objects
        """
        parsed_children = []
        
        for child in children:
            parsed_child = self._parse_step(child)
            if parsed_child:
                parsed_children.append(parsed_child)
        
        return parsed_children
    
    def _parse_step(self, step_data: Dict[str, Any]) -> SymphonyStep:
        """Parse individual step based on its type.
        
        Args:
            step_data: Dictionary representation of a step
            
        Returns:
            Parsed SymphonyStep object
            
        Raises:
            SymphonyParsingError: If step type is unknown
        """
        step_type = step_data.get("step")
        if not step_type:
            raise SymphonyParsingError("Step missing 'step' field")
        
        # Get the appropriate model class
        model_class = self.STEP_TYPE_MAPPING.get(step_type)
        if not model_class:
            raise SymphonyParsingError(f"Unknown step type: {step_type}")
        
        # Create a copy to avoid modifying original
        data = step_data.copy()
        
        # Parse children recursively if present
        if "children" in data and data["children"]:
            data["children"] = self._parse_children(data["children"])
        
        # Parse weight if present (for asset steps in weighted strategies)
        if "weight" in data and isinstance(data["weight"], dict):
            data["weight"] = Weight(**data["weight"])
        
        # Handle field name conversions for hyphenated fields
        self._convert_field_names(data)
        
        try:
            return model_class(**data)
        except ValidationError as e:
            raise SymphonyParsingError(f"Validation error for {step_type}: {str(e)}")
    
    def _convert_field_names(self, data: Dict[str, Any]) -> None:
        """Convert hyphenated field names to underscored versions.
        
        Args:
            data: Dictionary to convert field names in-place
        """
        conversions = {
            "is-else-condition?": "is-else-condition?",  # Keep as-is for alias
            "window-days": "window-days",  # Keep as-is for alias
            "sort-by-fn": "sort_by_fn",
            "sort-by-fn-params": "sort_by_fn_params",
            "select-fn": "select_fn",
            "select-n": "select_n",
            "lhs-fn": "lhs-fn",  # Keep as-is for alias
            "lhs-fn-params": "lhs-fn-params",  # Keep as-is for alias
            "lhs-val": "lhs-val",  # Keep as-is for alias
            "rhs-fn": "rhs-fn",  # Keep as-is for alias
            "rhs-fn-params": "rhs-fn-params",  # Keep as-is for alias
            "rhs-val": "rhs-val",  # Keep as-is for alias
            "rhs-fixed-value?": "rhs-fixed-value?",  # Keep as-is for alias
        }
        
        for old_key, new_key in conversions.items():
            if old_key in data and old_key != new_key:
                data[new_key] = data.pop(old_key)
    
    def validate_symphony(self, symphony: Union[str, Dict[str, Any], SymphonySchema]) -> SymphonySchema:
        """Validate a symphony from various input formats.
        
        Args:
            symphony: Symphony as JSON string, dict, or SymphonySchema
            
        Returns:
            Validated SymphonySchema object
            
        Raises:
            SymphonyParsingError: If validation fails
        """
        if isinstance(symphony, str):
            return self.parse_json(symphony)
        elif isinstance(symphony, dict):
            return self.parse_dict(symphony)
        elif isinstance(symphony, SymphonySchema):
            return symphony
        else:
            raise SymphonyParsingError(f"Invalid symphony type: {type(symphony)}")
    
    def to_json(self, symphony: SymphonySchema, pretty: bool = False) -> str:
        """Convert symphony to JSON string.
        
        Args:
            symphony: Symphony schema object
            pretty: Whether to pretty-print the JSON
            
        Returns:
            JSON string representation
        """
        data = symphony.dict(by_alias=True, exclude_none=True)
        
        if pretty:
            return json.dumps(data, indent=2)
        else:
            return json.dumps(data)
    
    def extract_assets(self, symphony: SymphonySchema) -> List[str]:
        """Extract all unique asset tickers from a symphony.
        
        Args:
            symphony: Symphony schema object
            
        Returns:
            List of unique ticker symbols
        """
        assets = set()
        
        def extract_from_step(step: SymphonyStep):
            if isinstance(step, AssetStep):
                assets.add(step.ticker)
            
            if hasattr(step, 'children') and step.children:
                for child in step.children:
                    extract_from_step(child)
        
        root = symphony.to_root_step()
        for child in root.children:
            extract_from_step(child)
        
        return sorted(list(assets))
    
    def get_complexity_metrics(self, symphony: SymphonySchema) -> Dict[str, int]:
        """Calculate complexity metrics for a symphony.
        
        Args:
            symphony: Symphony schema object
            
        Returns:
            Dictionary of complexity metrics
        """
        metrics = {
            "total_steps": 0,
            "max_depth": 0,
            "unique_assets": 0,
            "if_conditions": 0,
            "filters": 0,
            "groups": 0,
            "weighting_strategies": 0
        }
        
        assets = set()
        
        def analyze_step(step: SymphonyStep, depth: int = 0):
            metrics["total_steps"] += 1
            metrics["max_depth"] = max(metrics["max_depth"], depth)
            
            if isinstance(step, AssetStep):
                assets.add(step.ticker)
            elif isinstance(step, IfStep):
                metrics["if_conditions"] += 1
            elif isinstance(step, FilterStep):
                metrics["filters"] += 1
            elif isinstance(step, GroupStep):
                metrics["groups"] += 1
            elif step.step in ["wt-cash-equal", "wt-cash-specified", "wt-inverse-vol", "wt-market-cap", "wt-risk-parity"]:
                metrics["weighting_strategies"] += 1
            
            if hasattr(step, 'children') and step.children:
                for child in step.children:
                    analyze_step(child, depth + 1)
        
        root = symphony.to_root_step()
        for child in root.children:
            analyze_step(child, 1)
        
        metrics["unique_assets"] = len(assets)
        return metrics


# Global parser instance
symphony_parser = SymphonyParser()
