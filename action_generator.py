import json
import os
from typing import Dict

class ActionGenerator:
    def __init__(self, openai_client, model="gpt-4"):
        self.client = openai_client
        self.model = model
    
    def generate_action(self, code: str, output: Dict, goal: str, iteration: int, output_path: str = None) -> Dict:
        """Generate an action based on the code path and goal"""
        
        # Get assumptions from environment variables or use defaults
        progressive_analysis = os.environ.get(
            "ASSUMPTION_PROGRESSIVE_ANALYSIS", 
            "Analysis should progress from easiest to hardest manipulation scenarios"
        )
        
        attacker_goal = os.environ.get(
            "ASSUMPTION_ATTACKER_GOAL", 
            "Determine what an attacker would need to do to a given variable or dependency call to achieve profit"
        )
        
        prompt = f"""
        You are an expert smart contract auditor looking for potential vulnerabilities.
        
        GOAL: {goal}
        
        CODE:
        ```solidity
        {code}
        ```
        
        TOKEN FLOW PATH FOR ANALYSIS:
        {output.get('code_path', 'No specific path provided')}
        
        ANALYSIS FOCUS:
        {output.get('analysis_focus', 'No specific focus areas provided')}
        
        MANIPULATION STRATEGY:
        {output.get('manipulation_strategy', 'No specific manipulation strategy provided')}
        
        EXPECTED IMPACT:
        {output.get('expected_impact', 'No specific expected impact provided')}
        
        ASSUMPTIONS:
        {output.get('assumptions', 'No specific assumptions provided')}
        
        ITERATION INFO:
        {json.dumps(output.get('iteration_info', {'iteration': iteration}))}
        
        ANALYSIS ASSUMPTIONS:
        1. {progressive_analysis}
        2. {attacker_goal}
        
        Your task is to:
        1. Carefully analyze the provided code path and manipulation strategy
        2. Determine if the suggested manipulation is actually feasible
        3. If feasible, describe a specific scenario where an attacker could exploit this to profit
        4. Provide concrete code examples or transaction sequences that demonstrate the exploit
        5. Explain exactly how the attacker would profit from this exploit
        
        Be extremely rigorous in your analysis. Consider all possible constraints and conditions that might prevent the exploitation.
        
        Format your response as a JSON object with:
        {{
            "vulnerability_found": true/false,
            "vulnerability_type": "type of vulnerability if found",
            "attack_scenario": "detailed description of the attack scenario",
            "exploit_code": "code sample or transaction sequence demonstrating the exploit",
            "profit_mechanism": "detailed explanation of how the attacker profits",
            "attack_prerequisites": "specific conditions that must be met for the attack to succeed",
            "attack_limitations": "limitations or constraints on the attack",
            "confidence": "high/medium/low confidence in this finding",
            "reasoning": "your detailed step-by-step reasoning"
        }}
        
        If you determine the manipulation is not feasible, clearly explain why.
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
                        "vulnerability_found": False,
                        "vulnerability_type": "Error in parsing response",
                        "attack_scenario": "Error in parsing response",
                        "exploit_code": "Error in parsing response",
                        "profit_mechanism": "Error in parsing response",
                        "attack_prerequisites": "Error in parsing response",
                        "attack_limitations": "Error in parsing response",
                        "confidence": "low",
                        "reasoning": "Error in parsing response. See raw_response for details.",
                        "raw_response": content
                    }
            else:
                result = {
                    "vulnerability_found": False,
                    "vulnerability_type": "Error in parsing response",
                    "attack_scenario": "Error in parsing response",
                    "exploit_code": "Error in parsing response",
                    "profit_mechanism": "Error in parsing response",
                    "attack_prerequisites": "Error in parsing response",
                    "attack_limitations": "Error in parsing response",
                    "confidence": "low",
                    "reasoning": "Error in parsing response. See raw_response for details.",
                    "raw_response": content
                }
        
        # Add metadata about the analysis
        result["analysis_metadata"] = {
            "iteration": iteration,
            "analysis_focus": output.get('analysis_focus', 'Not available'),
            "manipulation_strategy": output.get('manipulation_strategy', 'Not available')
        }
        
        # Save the action generation results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result