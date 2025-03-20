import json
import os
from typing import Dict

class Reflection:
    def __init__(self, openai_client, model="gpt-4"):
        self.client = openai_client
        self.model = model
    
    def evaluate_result(self, code: str, action_result: Dict, goal: str, iteration: int, output_path: str = None) -> Dict:
        """Evaluate if the action result meets the goal and provide feedback"""
        
        # Get assumptions from environment variables with defaults
        strict_evaluation = os.environ.get(
            "ASSUMPTION_STRICT_EVALUATION", 
            "Strictly verify whether a variable is truly manipulable to achieve the goal"
        )
        
        false_positive_handling = os.environ.get(
            "ASSUMPTION_FALSE_POSITIVE_HANDLING", 
            "Identify if a manipulation is a false positive and should be excluded"
        )
        
        # Get additional assumptions
        privileged_vars_assumption = os.environ.get(
            "ASSUMPTION_PRIVILEGED_VARS", 
            "Variables controlled by privileged accounts should be considered impossible to manipulate"
        )
        
        prompt = f"""
        You are a security expert evaluating the findings of a smart contract audit.
        
        GOAL: {goal}
        
        CODE SNIPPET:
        ```solidity
        {code}
        ```
        
        AUDIT FINDING:
        {json.dumps(action_result)}
        
        EVALUATION ASSUMPTIONS:
        1. {strict_evaluation}
        2. {false_positive_handling}
        3. {privileged_vars_assumption}
        
        Evaluate whether this finding legitimately meets the goal. Be extremely rigorous and critical.
        
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
            "finding_quality": "high/medium/low",
            "evaluation": "detailed evaluation of the finding",
            "critical_flaws": "any critical flaws that invalidate the finding",
            "overlooked_constraints": "any constraints that were overlooked",
            "variables_to_exclude": "variables that should be excluded from future analysis due to false positives",
            "additional_conditions": "additional conditions required for a successful attack",
            "suggestions": "suggestions for further analysis if the goal is not met",
            "new_focus_areas": "specific areas to focus on in the next iteration if needed"
        }}
        """
        
        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse the JSON response
        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            # Extract JSON from text if not valid JSON
            content = response.choices[0].message.content
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    result = json.loads(content[start_idx:end_idx])
                except json.JSONDecodeError:
                    result = {
                        "goal_met": False,
                        "finding_quality": "low",
                        "evaluation": "Error in parsing response",
                        "critical_flaws": "Error in parsing response",
                        "overlooked_constraints": "Error in parsing response",
                        "variables_to_exclude": [],
                        "additional_conditions": "Error in parsing response",
                        "suggestions": "Try a different approach",
                        "new_focus_areas": "Error in parsing response",
                        "raw_response": content
                    }
            else:
                result = {
                    "goal_met": False,
                    "finding_quality": "low",
                    "evaluation": "Error in parsing response",
                    "critical_flaws": "Error in parsing response",
                    "overlooked_constraints": "Error in parsing response",
                    "variables_to_exclude": [],
                    "additional_conditions": "Error in parsing response",
                    "suggestions": "Try a different approach",
                    "new_focus_areas": "Error in parsing response",
                    "raw_response": content
                }
        
        # Add metadata about the evaluation
        result["evaluation_metadata"] = {
            "iteration": iteration,
            "vulnerability_found": action_result.get('vulnerability_found', False),
            "vulnerability_type": action_result.get('vulnerability_type', 'Not specified')
        }
        
        # Ensure variables_to_exclude is always a list
        if "variables_to_exclude" not in result:
            result["variables_to_exclude"] = []
        elif not isinstance(result["variables_to_exclude"], list):
            if isinstance(result["variables_to_exclude"], str):
                # Try to convert string to list if it looks like a list
                if result["variables_to_exclude"].startswith('[') and result["variables_to_exclude"].endswith(']'):
                    try:
                        result["variables_to_exclude"] = json.loads(result["variables_to_exclude"])
                    except:
                        result["variables_to_exclude"] = [result["variables_to_exclude"]]
                else:
                    result["variables_to_exclude"] = [result["variables_to_exclude"]]
            else:
                result["variables_to_exclude"] = []
        
        # Save the results if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result