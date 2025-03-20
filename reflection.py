import json
import os
from typing import Dict, List

class Reflection:
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
                        "goal_met": False,
                        "evaluation": "Error in parsing response",
                        "critical_flaws": "Error in parsing response",
                        "overlooked_constraints": "Error in parsing response",
                        "variables_to_exclude": [],
                        "variables_to_include": [],
                        "raw_response": response_text
                    }
            else:
                return {
                    "goal_met": False,
                    "evaluation": "Error in parsing response",
                    "critical_flaws": "Error in parsing response",
                    "overlooked_constraints": "Error in parsing response",
                    "variables_to_exclude": [],
                    "variables_to_include": [],
                    "raw_response": response_text
                }
    
    def evaluate_result(self, code: str, path_output: Dict, action_result: Dict, goal: str, iteration: int, output_path: str = None) -> Dict:
        """
        Evaluate if the action result meets the goal and provide feedback.
        Updates only case-specific memory, not global memory.
        
        Args:
            code: Original contract code
            path_output: Output from LogicExtractor
            action_result: Result from ActionGenerator
            goal: Analysis goal
            iteration: Current iteration number
            output_path: Optional path to save results
            
        Returns:
            Reflection result dictionary
        """
        
        # Get assumptions from global memory
        assumptions = self.memory_manager.get_global_assumptions("reflection")
        
        # Get false positive rules from global memory
        false_positive_rules = self.memory_manager.get_attack_patterns("reflection")
        
        prompt = f"""
        You are a security expert evaluating the findings of a smart contract audit.
        
        GOAL: {goal}
        
        ORIGINAL CONTRACT CODE:
        ```solidity
        {code}
        ```
        
        AUDIT FINDING:
        {json.dumps(action_result)}
        
        EVALUATION ASSUMPTIONS:
        {json.dumps(assumptions, indent=2)}
        
        FALSE POSITIVE RULES:
        {json.dumps(false_positive_rules, indent=2)}
        
        Evaluate whether this finding legitimately meets the goal. You must be extremely rigorous and critical.
        
        If you identify any issues, explain exactly what's wrong and why the attack wouldn't work as described.
        
        Format your response as a JSON object with:
        {{{{
            "goal_met": true/false,
            "evaluation": "detailed evaluation of the finding",
            "critical_flaws": "any critical flaws that invalidate the finding",
            "overlooked_constraints": "any constraints that were overlooked",
            "variables_to_exclude": [], 
            "variables_to_include": ["variable3", "variable4"]
        }}}}
        
        Only include variables in the variables_to_exclude field if the vulnerability analysis failed.
        The variables_to_include field should contain variables that seem promising for future analysis.
        """
        
        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the JSON from the response text using the helper method
        result = self._parse_json_response(response.choices[0].message.content)
        
        # Add metadata about the evaluation
        result["evaluation_metadata"] = {
            "iteration": iteration,
            "vulnerability_found": action_result.get('vulnerability_found', False),
            "vulnerability_type": action_result.get('vulnerability_type', 'Not specified')
        }
        
        # Update case memory based on reflection results - only if goal not met
        if not result.get("goal_met", False):
            self._update_case_memory(result)
        
        # Add this finding to previous findings in case memory
        finding_summary = {
            "iteration": iteration,
            "variables_analyzed": path_output.get("variables_analyzed", []),
            "dependencies_analyzed": path_output.get("dependencies_analyzed", []),
            "result": action_result.get("vulnerability_found", False),
            "critical_flaws": result.get("critical_flaws", None) if not result.get("goal_met", False) else None
        }
        self.memory_manager.add_previous_finding(finding_summary)
        
        # Save the reflection results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result
    
    def _update_case_memory(self, reflection_result: Dict) -> None:
        """Update case-specific memory based on reflection results - only called when goal not met"""
        
        # Update excluded variables - only when goal not met
        for var_name in reflection_result.get("variables_to_exclude", []):
            if var_name:  # Ensure we don't add empty variable names
                self.memory_manager.add_excluded_variable(var_name)
        
        # Update included variables
        for var_name in reflection_result.get("variables_to_include", []):
            if var_name:  # Ensure we don't add empty variable names
                self.memory_manager.add_included_variable(var_name)