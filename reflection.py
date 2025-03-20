import json
import os
from typing import Dict, List

class Reflection:
    def __init__(self, openai_client, memory_manager, model="gpt-4"):
        self.client = openai_client
        self.model = model
        self.memory_manager = memory_manager
    
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
        
        Consider:
        1. Is the vulnerability real, or is it a false positive?
        2. Does the described attack scenario actually work exactly as described?
        3. Are all the prerequisites for the attack realistically achievable?
        4. Would the attacker genuinely profit from this in practice?
        5. Are there any flaws in the reasoning or overlooked constraints?
        
        If you identify any issues, explain exactly what's wrong and why the attack wouldn't work as described.
        
        Format your response as a JSON object with:
        {{
            "goal_met": true/false,
            "evaluation": "detailed evaluation of the finding",
            "critical_flaws": "any critical flaws that invalidate the finding",
            "overlooked_constraints": "any constraints that were overlooked",
            "variables_to_exclude": ["variable1", "variable2"], 
            "variables_to_include": ["variable3", "variable4"]
        }}
        
        The variables_to_exclude field should contain variables that are proven to be impossible to manipulate or irrelevant.
        The variables_to_include field should contain variables that seem promising for future analysis.
        """
        
        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the JSON from the response text
        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # If the response isn't valid JSON, try to extract JSON from the text
            content = response.choices[0].message.content
            # Attempt to find JSON-like structure
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    # If still not valid, create a basic structure
                    result = {
                        "goal_met": False,
                        "evaluation": "Error in parsing response",
                        "critical_flaws": "Error in parsing response",
                        "overlooked_constraints": "Error in parsing response",
                        "variables_to_exclude": [],
                        "variables_to_include": [],
                        "raw_response": content
                    }
            else:
                result = {
                    "goal_met": False,
                    "evaluation": "Error in parsing response",
                    "critical_flaws": "Error in parsing response",
                    "overlooked_constraints": "Error in parsing response",
                    "variables_to_exclude": [],
                    "variables_to_include": [],
                    "raw_response": content
                }
        
        # Add metadata about the evaluation
        result["evaluation_metadata"] = {
            "iteration": iteration,
            "vulnerability_found": action_result.get('vulnerability_found', False),
            "vulnerability_type": action_result.get('vulnerability_type', 'Not specified')
        }
        
        # Update case memory based on reflection results
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
        """Update case-specific memory based on reflection results"""
        
        # Update excluded variables
        for var_name in reflection_result.get("variables_to_exclude", []):
            self.memory_manager.add_excluded_variable(var_name)
        
        # Update included variables
        for var_name in reflection_result.get("variables_to_include", []):
            self.memory_manager.add_included_variable(var_name)