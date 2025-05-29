"""Comprehensive algorithm execution testing."""

import pytest
import json
from app.parsers.symphony_parser import symphony_parser, SymphonyParsingError
from app.parsers.validator import symphony_validator, ValidationError
from app.parsers.schemas import SymphonySchema, AssetStep, FilterStep


# Load the sample symphony for testing
with open("sample-symphonies/sample-symphony.json", "r") as f:
    SAMPLE_SYMPHONY_JSON = f.read()


class TestSymphonyParser:
    """Test symphony parsing functionality."""
    
    def test_parse_sample_symphony(self):
        """Test parsing the sample symphony."""
        symphony = symphony_parser.parse_json(SAMPLE_SYMPHONY_JSON)
        
        assert isinstance(symphony, SymphonySchema)
        assert symphony.name == "Sample Symphony"
        assert symphony.rebalance.value == "daily"
        assert len(symphony.children) > 0
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        with pytest.raises(SymphonyParsingError):
            symphony_parser.parse_json("invalid json")
    
    def test_extract_assets(self):
        """Test asset extraction from symphony."""
        symphony = symphony_parser.parse_json(SAMPLE_SYMPHONY_JSON)
        assets = symphony_parser.extract_assets(symphony)
        
        # Sample symphony contains NVDA, TSLA, QQQ, BIL, VIXY
        expected_assets = ["BIL", "NVDA", "QQQ", "TSLA", "VIXY"]
        assert sorted(assets) == expected_assets
    
    def test_complexity_metrics(self):
        """Test complexity metrics calculation."""
        symphony = symphony_parser.parse_json(SAMPLE_SYMPHONY_JSON)
        metrics = symphony_parser.get_complexity_metrics(symphony)
        
        assert metrics["total_steps"] > 0
        assert metrics["max_depth"] > 0
        assert metrics["unique_assets"] == 5
        assert metrics["if_conditions"] > 0
        assert metrics["filters"] > 0


class TestSymphonyValidator:
    """Test symphony validation functionality."""
    
    def test_validate_sample_symphony(self):
        """Test validating the sample symphony."""
        symphony = symphony_parser.parse_json(SAMPLE_SYMPHONY_JSON)
        warnings = symphony_validator.validate(symphony)
        
        # Sample symphony should be valid
        assert isinstance(warnings, list)
    
    def test_validate_empty_symphony(self):
        """Test validating empty symphony."""
        invalid_json = json.dumps({
            "id": "test",
            "step": "root",
            "name": "Empty",
            "rebalance": "daily",
            "children": []
        })
        
        with pytest.raises(ValidationError):
            symphony = symphony_parser.parse_json(invalid_json)
            symphony_validator.validate(symphony)
    
    def test_execution_tree_building(self):
        """Test building execution tree."""
        symphony = symphony_parser.parse_json(SAMPLE_SYMPHONY_JSON)
        root = symphony.to_root_step()
        execution_tree = symphony_validator.build_execution_tree(root)
        
        assert execution_tree is not None
        assert execution_tree.step == root
        assert len(execution_tree.children) > 0
    
    def test_execution_plan(self):
        """Test getting execution plan."""
        symphony = symphony_parser.parse_json(SAMPLE_SYMPHONY_JSON)
        root = symphony.to_root_step()
        execution_tree = symphony_validator.build_execution_tree(root)
        plan = symphony_validator.get_execution_plan(execution_tree)
        
        assert isinstance(plan, list)
        assert len(plan) > 0
        
        # Verify plan structure
        for step in plan:
            assert "order" in step
            assert "step_id" in step
            assert "step_type" in step
            assert "required_assets" in step
            assert "required_metrics" in step


class TestComplexAlgorithms:
    """Test complex algorithmic structures."""
    
    def test_conditional_logic(self):
        """Test parsing conditional if-then-else logic."""
        conditional_json = json.dumps({
            "id": "test",
            "step": "root",
            "name": "Conditional Test",
            "rebalance": "daily",
            "children": [{
                "id": "if1",
                "step": "if",
                "children": [
                    {
                        "id": "then1",
                        "step": "if-child",
                        "is-else-condition?": False,
                        "lhs-fn": "current-price",
                        "lhs-val": "QQQ",
                        "comparator": "gt",
                        "rhs-val": "100",
                        "rhs-fixed-value?": True,
                        "children": [{
                            "id": "asset1",
                            "step": "asset",
                            "ticker": "NVDA",
                            "exchange": "XNAS",
                            "name": "NVIDIA"
                        }]
                    },
                    {
                        "id": "else1",
                        "step": "if-child",
                        "is-else-condition?": True,
                        "children": [{
                            "id": "asset2",
                            "step": "asset",
                            "ticker": "BIL",
                            "exchange": "ARCX",
                            "name": "T-Bill ETF"
                        }]
                    }
                ]
            }]
        })
        
        symphony = symphony_parser.parse_json(conditional_json)
        assert symphony is not None
        
        # Validate structure
        warnings = symphony_validator.validate(symphony)
        assert isinstance(warnings, list)
    
    def test_filter_with_metrics(self):
        """Test filter steps with technical indicators."""
        filter_json = json.dumps({
            "id": "test",
            "step": "root",
            "name": "Filter Test",
            "rebalance": "daily",
            "children": [{
                "id": "filter1",
                "step": "filter",
                "sort-by-fn": "relative-strength-index",
                "sort-by-fn-params": {"window": 14},
                "select-fn": "top",
                "select-n": "2",
                "children": [
                    {
                        "id": "asset1",
                        "step": "asset",
                        "ticker": "AAPL",
                        "exchange": "XNAS",
                        "name": "Apple"
                    },
                    {
                        "id": "asset2",
                        "step": "asset",
                        "ticker": "MSFT",
                        "exchange": "XNAS",
                        "name": "Microsoft"
                    },
                    {
                        "id": "asset3",
                        "step": "asset",
                        "ticker": "GOOGL",
                        "exchange": "XNAS",
                        "name": "Google"
                    }
                ]
            }]
        })
        
        symphony = symphony_parser.parse_json(filter_json)
        metrics = symphony_parser.get_complexity_metrics(symphony)
        
        assert metrics["filters"] == 1
        assert metrics["unique_assets"] == 3
    
    def test_weighting_strategies(self):
        """Test different weighting strategies."""
        weighting_json = json.dumps({
            "id": "test",
            "step": "root",
            "name": "Weighting Test",
            "rebalance": "daily",
            "children": [{
                "id": "weight1",
                "step": "wt-inverse-vol",
                "window-days": "20",
                "children": [
                    {
                        "id": "asset1",
                        "step": "asset",
                        "ticker": "SPY",
                        "exchange": "ARCX",
                        "name": "SPDR S&P 500"
                    },
                    {
                        "id": "asset2",
                        "step": "asset",
                        "ticker": "AGG",
                        "exchange": "ARCX",
                        "name": "iShares Core US Aggregate Bond"
                    }
                ]
            }]
        })
        
        symphony = symphony_parser.parse_json(weighting_json)
        metrics = symphony_parser.get_complexity_metrics(symphony)
        
        assert metrics["weighting_strategies"] == 1
