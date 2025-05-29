"""Algorithm validation and execution tree builder."""

from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict

from app.parsers.schemas import (
    SymphonySchema,
    SymphonyStep,
    AssetStep,
    FilterStep,
    IfStep,
    IfChildStep,
    MetricFunction,
    StepType,
    RebalanceFrequency
)
from app.parsers.symphony_parser import SymphonyParsingError


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class ExecutionNode:
    """Node in the execution tree."""
    
    def __init__(self, step: SymphonyStep, parent: Optional['ExecutionNode'] = None):
        self.step = step
        self.parent = parent
        self.children: List['ExecutionNode'] = []
        self.required_assets: Set[str] = set()
        self.required_metrics: Set[Tuple[str, MetricFunction, int]] = set()
        self.execution_order: int = 0
    
    def add_child(self, child: 'ExecutionNode'):
        """Add a child node."""
        self.children.append(child)
        child.parent = self
    
    def get_depth(self) -> int:
        """Get depth of this node in the tree."""
        depth = 0
        current = self
        while current.parent:
            depth += 1
            current = current.parent
        return depth


class SymphonyValidator:
    """Validator for symphony algorithms and execution tree builder."""
    
    # Maximum allowed depth for nested structures
    MAX_DEPTH = 20
    
    # Maximum allowed number of steps
    MAX_STEPS = 1000
    
    # Maximum allowed assets per symphony
    MAX_ASSETS = 100
    
    # Valid metric function parameters
    METRIC_PARAMETERS = {
        MetricFunction.CUMULATIVE_RETURN: ["window"],
        MetricFunction.EXPONENTIAL_MOVING_AVERAGE_PRICE: ["window"],
        MetricFunction.MAX_DRAWDOWN: ["window"],
        MetricFunction.MOVING_AVERAGE_PRICE: ["window"],
        MetricFunction.MOVING_AVERAGE_RETURN: ["window"],
        MetricFunction.RELATIVE_STRENGTH_INDEX: ["window"],
        MetricFunction.STANDARD_DEVIATION_PRICE: ["window"],
        MetricFunction.STANDARD_DEVIATION_RETURN: ["window"],
        MetricFunction.SHARPE_RATIO: ["window"],
        MetricFunction.VOLATILITY: ["window"],
        MetricFunction.BETA: ["window", "benchmark"],
        MetricFunction.ALPHA: ["window", "benchmark"],
        MetricFunction.CORRELATION: ["window", "benchmark"],
    }
    
    def validate(self, symphony: SymphonySchema) -> List[str]:
        """Validate a symphony for execution.
        
        Args:
            symphony: Symphony to validate
            
        Returns:
            List of validation warnings (empty if no warnings)
            
        Raises:
            ValidationError: If symphony is invalid
        """
        warnings = []
        
        # Basic validations
        self._validate_structure(symphony)
        self._validate_complexity(symphony)
        
        # Build execution tree
        root = symphony.to_root_step()
        execution_tree = self.build_execution_tree(root)
        
        # Validate execution tree
        self._validate_execution_tree(execution_tree, warnings)
        
        # Validate asset availability
        warnings.extend(self._validate_assets(symphony))
        
        # Validate metric functions
        warnings.extend(self._validate_metrics(execution_tree))
        
        return warnings
    
    def _validate_structure(self, symphony: SymphonySchema):
        """Validate basic structure requirements."""
        if not symphony.children:
            raise ValidationError("Symphony must have at least one child step")
        
        if symphony.rebalance not in RebalanceFrequency:
            raise ValidationError(f"Invalid rebalance frequency: {symphony.rebalance}")
    
    def _validate_complexity(self, symphony: SymphonySchema):
        """Validate complexity limits."""
        from app.parsers.symphony_parser import symphony_parser
        
        metrics = symphony_parser.get_complexity_metrics(symphony)
        
        if metrics["total_steps"] > self.MAX_STEPS:
            raise ValidationError(
                f"Symphony exceeds maximum steps ({metrics['total_steps']} > {self.MAX_STEPS})"
            )
        
        if metrics["max_depth"] > self.MAX_DEPTH:
            raise ValidationError(
                f"Symphony exceeds maximum depth ({metrics['max_depth']} > {self.MAX_DEPTH})"
            )
        
        if metrics["unique_assets"] > self.MAX_ASSETS:
            raise ValidationError(
                f"Symphony exceeds maximum assets ({metrics['unique_assets']} > {self.MAX_ASSETS})"
            )
    
    def build_execution_tree(self, root: SymphonyStep) -> ExecutionNode:
        """Build execution tree from symphony structure.
        
        Args:
            root: Root step of the symphony
            
        Returns:
            Root node of execution tree
        """
        execution_root = ExecutionNode(root)
        self._build_tree_recursive(root, execution_root)
        self._calculate_execution_order(execution_root)
        self._collect_requirements(execution_root)
        
        return execution_root
    
    def _build_tree_recursive(self, step: SymphonyStep, node: ExecutionNode):
        """Recursively build execution tree."""
        if hasattr(step, 'children') and step.children:
            for child_step in step.children:
                child_node = ExecutionNode(child_step, node)
                node.add_child(child_node)
                self._build_tree_recursive(child_step, child_node)
    
    def _calculate_execution_order(self, root: ExecutionNode):
        """Calculate execution order for nodes (post-order traversal)."""
        order = [0]  # Use list to maintain reference in nested function
        
        def assign_order(node: ExecutionNode):
            # Process children first
            for child in node.children:
                assign_order(child)
            
            # Then assign order to current node
            node.execution_order = order[0]
            order[0] += 1
        
        assign_order(root)
    
    def _collect_requirements(self, root: ExecutionNode):
        """Collect required assets and metrics for each node."""
        def collect_recursive(node: ExecutionNode):
            step = node.step
            
            # Collect assets
            if isinstance(step, AssetStep):
                node.required_assets.add(step.ticker)
            
            # Collect metrics from conditions
            if isinstance(step, IfChildStep) and not step.is_else_condition:
                if step.lhs_val:
                    node.required_assets.add(step.lhs_val)
                if step.rhs_val and not step.rhs_fixed_value:
                    node.required_assets.add(step.rhs_val)
                
                # Add metric requirements
                if step.lhs_fn:
                    window = step.lhs_fn_params.get('window', 20) if step.lhs_fn_params else 20
                    node.required_metrics.add((step.lhs_val, step.lhs_fn, window))
                
                if step.rhs_fn and not step.rhs_fixed_value:
                    window = step.rhs_fn_params.get('window', 20) if step.rhs_fn_params else 20
                    node.required_metrics.add((step.rhs_val, step.rhs_fn, window))
            
            # Collect metrics from filters
            if isinstance(step, FilterStep):
                window = step.sort_by_fn_params.get('window', 20) if step.sort_by_fn_params else 20
                # For filters, metrics apply to all child assets
                for child in node.children:
                    if isinstance(child.step, AssetStep):
                        node.required_metrics.add((child.step.ticker, step.sort_by_fn, window))
            
            # Propagate requirements from children
            for child in node.children:
                collect_recursive(child)
                node.required_assets.update(child.required_assets)
                node.required_metrics.update(child.required_metrics)
        
        collect_recursive(root)
    
    def _validate_execution_tree(self, root: ExecutionNode, warnings: List[str]):
        """Validate execution tree structure."""
        visited = set()
        
        def validate_node(node: ExecutionNode):
            # Check for cycles
            if id(node) in visited:
                raise ValidationError("Circular reference detected in symphony")
            visited.add(id(node))
            
            step = node.step
            
            # Validate IF conditions
            if isinstance(step, IfStep):
                if len(node.children) != 2:
                    raise ValidationError("IF step must have exactly 2 children")
                
                # Check that children are IfChildStep
                for child in node.children:
                    if not isinstance(child.step, IfChildStep):
                        raise ValidationError("IF step children must be if-child steps")
            
            # Validate filters
            if isinstance(step, FilterStep):
                if not node.children:
                    warnings.append(f"Filter step {step.id} has no assets to filter")
                
                # Validate select_n
                try:
                    select_n = int(step.select_n) if isinstance(step.select_n, str) else step.select_n
                    if select_n > len(node.children):
                        warnings.append(
                            f"Filter step {step.id} selects {select_n} but only has {len(node.children)} children"
                        )
                except ValueError:
                    if step.select_n != "all":
                        raise ValidationError(f"Invalid select_n value: {step.select_n}")
            
            # Recursively validate children
            for child in node.children:
                validate_node(child)
        
        validate_node(root)
    
    def _validate_assets(self, symphony: SymphonySchema) -> List[str]:
        """Validate asset availability and generate warnings."""
        from app.parsers.symphony_parser import symphony_parser
        
        warnings = []
        assets = symphony_parser.extract_assets(symphony)
        
        if not assets:
            warnings.append("Symphony contains no assets")
        
        # Check for duplicate assets in same group
        # This is a simplified check - in reality would need more complex logic
        
        return warnings
    
    def _validate_metrics(self, root: ExecutionNode) -> List[str]:
        """Validate metric function usage."""
        warnings = []
        
        def validate_node_metrics(node: ExecutionNode):
            step = node.step
            
            # Validate metric parameters
            if isinstance(step, (IfChildStep, FilterStep)):
                # Get the metric function
                metric_fn = None
                params = {}
                
                if isinstance(step, IfChildStep) and step.lhs_fn:
                    metric_fn = step.lhs_fn
                    params = step.lhs_fn_params or {}
                elif isinstance(step, FilterStep):
                    metric_fn = step.sort_by_fn
                    params = step.sort_by_fn_params or {}
                
                if metric_fn:
                    # Check if parameters are valid
                    valid_params = self.METRIC_PARAMETERS.get(metric_fn, [])
                    for param in params:
                        if param not in valid_params:
                            warnings.append(
                                f"Unknown parameter '{param}' for metric {metric_fn.value}"
                            )
                    
                    # Check window ranges
                    if 'window' in params:
                        window = params['window']
                        if not isinstance(window, int) or window < 1 or window > 252:
                            warnings.append(
                                f"Window parameter should be between 1-252 days, got {window}"
                            )
            
            # Recursively check children
            for child in node.children:
                validate_node_metrics(child)
        
        validate_node_metrics(root)
        return warnings
    
    def get_execution_plan(self, root: ExecutionNode) -> List[Dict[str, Any]]:
        """Get execution plan from execution tree.
        
        Args:
            root: Root of execution tree
            
        Returns:
            List of execution steps in order
        """
        steps = []
        
        def collect_steps(node: ExecutionNode):
            for child in node.children:
                collect_steps(child)
            
            steps.append({
                "order": node.execution_order,
                "step_id": node.step.id,
                "step_type": node.step.step,
                "depth": node.get_depth(),
                "required_assets": sorted(list(node.required_assets)),
                "required_metrics": [
                    {
                        "asset": asset,
                        "function": metric.value,
                        "window": window
                    }
                    for asset, metric, window in sorted(node.required_metrics)
                ]
            })
        
        collect_steps(root)
        return sorted(steps, key=lambda x: x["order"])


# Global validator instance
symphony_validator = SymphonyValidator()
