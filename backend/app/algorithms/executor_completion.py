# This completes the _get_value method and adds the _generate_allocations method

                if agg_func == 'avg':
                    return sum(values) / len(values)
                elif agg_func == 'sum':
                    return sum(values)
                elif agg_func == 'max':
                    return max(values)
                elif agg_func == 'min':
                    return min(values)
                    
        return Decimal('0')
    
    def _generate_allocations(
        self, asset_data_map: Dict[str, AssetData], allocation_config: Dict
    ) -> Dict[str, Decimal]:
        """Generate final portfolio allocations from weighted assets"""
        allocations = {}
        
        # Apply any final allocation rules
        min_allocation = Decimal(str(allocation_config.get('min_allocation', 0)))
        max_allocation = Decimal(str(allocation_config.get('max_allocation', 1)))
        cash_buffer = Decimal(str(allocation_config.get('cash_buffer', 0)))
        
        # Calculate total investable weight (1 - cash buffer)
        investable_weight = Decimal('1') - cash_buffer
        
        # Generate allocations from weights
        for symbol, asset_data in asset_data_map.items():
            allocation = asset_data.weight * investable_weight
            
            # Apply min/max constraints
            if allocation < min_allocation:
                allocation = Decimal('0')  # Drop if below minimum
            elif allocation > max_allocation:
                allocation = max_allocation
                
            if allocation > 0:
                allocations[symbol] = allocation
                
        # Add cash allocation if specified
        if cash_buffer > 0:
            allocations['CASH'] = cash_buffer
            
        # Normalize allocations to sum to 1
        total_allocation = sum(allocations.values())
        if total_allocation > 0 and abs(total_allocation - Decimal('1')) > Decimal('0.001'):
            for symbol in allocations:
                allocations[symbol] = allocations[symbol] / total_allocation
                
        # Round allocations to reasonable precision
        for symbol in allocations:
            allocations[symbol] = allocations[symbol].quantize(Decimal('0.0001'))
            
        return allocations
