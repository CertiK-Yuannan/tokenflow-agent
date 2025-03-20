import json
import os
from typing import Dict

class ActionGenerator:
    def __init__(self, openai_client, memory_manager, model="gpt-4"):
        self.client = openai_client
        self.model = model
        self.memory_manager = memory_manager
    
    def _parse_json_response(self, response_text):
        """Helper method to parse JSON from response text with error handling"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If the response isn't valid JSON, try to extract JSON from the text
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # If still not valid, create a basic structure
                    return {
                        "vulnerability_found": False,
                        "vulnerability_type": "Error in parsing response",
                        "attack_scenario": "Error in parsing response",
                        "exploit_code": "Error in parsing response",
                        "profit_mechanism": "Error in parsing response",
                        "attack_prerequisites": "Error in parsing response",
                        "attack_limitations": "Error in parsing response",
                        "edge_cases": "Error in parsing response",
                        "confidence": "low",
                        "reasons_if_not_feasible": "Error in parsing response",
                        "reasoning": "Error in parsing response",
                        "raw_response": response_text
                    }
            else:
                return {
                    "vulnerability_found": False,
                    "vulnerability_type": "Error in parsing response",
                    "attack_scenario": "Error in parsing response",
                    "exploit_code": "Error in parsing response",
                    "profit_mechanism": "Error in parsing response",
                    "attack_prerequisites": "Error in parsing response",
                    "attack_limitations": "Error in parsing response",
                    "edge_cases": "Error in parsing response",
                    "confidence": "low",
                    "reasons_if_not_feasible": "Error in parsing response",
                    "reasoning": "Error in parsing response",
                    "raw_response": response_text
                }
    
    def generate_action(self, code: str, path_output: Dict, goal: str, iteration: int, output_path: str = None) -> Dict:
        """
        Generate an action based solely on the code representation from LogicExtractor.
        
        Args:
            code: Original contract code (for reference only)
            path_output: Output from LogicExtractor containing code representation
            goal: Analysis goal
            iteration: Current iteration number
            output_path: Optional path to save results
            
        Returns:
            Action result dictionary
        """
        
        # Get assumptions from global memory
        assumptions = self.memory_manager.get_global_assumptions("action_generator")
        
        # Get attack patterns from global memory
        attack_patterns = self.memory_manager.get_attack_patterns("action_generator")
        
        # Extract code representation from path_output - this is the key input
        code_representation = path_output.get("code_representation", "")
        
        # Note: Escaped curly braces in the f-string for JSON template
        prompt = f"""
        You are an expert smart contract auditor validating a potential vulnerability.
        
        GOAL: {goal}
        
        PSEUDO-CODE TO ANALYZE:
        ```
        {code_representation}
        ```
        
        Your task is to:
        1. Carefully analyze the provided pseudo-code representation
        2. Determine if there's a way to manipulate the variables in the pseudo-code to achieve the goal
        3. If possible, provide concrete, executable transaction sequences that an attacker would use
        4. Calculate the actual profit the attacker would make, with specific token amounts when possible
        5. Consider all edge cases, preconditions, and constraints that might prevent the attack
        
        Be extremely rigorous in your analysis. The attack is only valid if all steps are feasible AND result in profit.
        
        Format your response as a JSON object with:
        {{{{
            "vulnerability_found": true/false,
            "vulnerability_type": "type of vulnerability if found",
            "attack_scenario": "detailed description of the attack scenario",
            "exploit_code": "code sample or transaction sequence demonstrating the exploit",
            "profit_mechanism": "detailed explanation of how the attacker profits",
            "attack_prerequisites": "specific conditions that must be met for the attack to succeed",
            "attack_limitations": "limitations or constraints on the attack",
            "edge_cases": "edge cases that might prevent the attack",
            "confidence": "high/medium/low confidence in this finding",
            "reasons_if_not_feasible": "detailed explanation of why the attack is not feasible if applicable",
            "reasoning": "your detailed step-by-step reasoning"
        }}}}
        
        If you determine the attack is not feasible, clearly explain why at each step where it fails.
        """
        
        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the JSON from the response text using the helper method
        result = self._parse_json_response(response.choices[0].message.content)
        
        # Add metadata about the analysis
        result["analysis_metadata"] = {
            "iteration": iteration,
            "variables_analyzed": path_output.get("variables_analyzed", []),
            "dependencies_analyzed": path_output.get("dependencies_analyzed", [])
        }
        
        # Save the action generation results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result