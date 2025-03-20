import json
import os
from typing import Dict

class LogicExtractor:
    def __init__(self, openai_client, model="gpt-4"):
        self.client = openai_client
        self.model = model
        self.analysis_results = {}
        
    def preprocess_code(self, code: str, target_description: str, output_path: str = None) -> Dict:
        """Initial preprocessing of code to understand token flow, variables, and dependencies"""
        
        # Get assumptions from environment variables with defaults
        privileged_vars = os.environ.get(
            "ASSUMPTION_PRIVILEGED_VARS", 
            "Variables or external dependencies controlled by privileged accounts are impossible to manipulate"
        )
        
        user_controlled_vars = os.environ.get(
            "ASSUMPTION_USER_CONTROLLED_VARS", 
            "User-controllable variables should be considered easy to manipulate"
        )
        
        manipulation_hierarchy = os.environ.get(
            "ASSUMPTION_MANIPULATION_HIERARCHY", 
            "Variables should be categorized by manipulation difficulty (easy, medium, hard, impossible)"
        )
        
        prompt = f"""
        You are analyzing a smart contract for potential vulnerabilities in token flow.
        
        Please analyze the following code, focusing on the described target functionality:
        
        TARGET: {target_description}
        
        CODE:
        ```solidity
        {code}
        ```
        
        ANALYSIS ASSUMPTIONS:
        1. {privileged_vars}
        2. {user_controlled_vars}
        3. {manipulation_hierarchy}
        
        Provide the following analysis:
        
        1. Describe the overall token flow in the target functionality.
        
        2. Identify all variables (both state and local) that affect token flow amounts, and categorize them based on manipulation difficulty:
           - easy: Variables directly controllable by users
           - medium: Variables indirectly controllable with some prerequisites
           - hard: Variables that require complex prerequisites or exploits to manipulate
           - impossible: Variables controlled by privileged accounts or set in constructor
        
        3. Identify all dependencies (functions, modifiers, imported contracts) that the token flow relies on, and categorize them based on risk of error or manipulation using the same scale.
        
        Format your response as a JSON object with:
        {{
            "token_flow_description": "detailed description of the token flow",
            "variables": {{
                "variable_name1": {{
                    "type": "state/local", 
                    "description": "what it does", 
                    "manipulation_difficulty": "easy/medium/hard/impossible",
                    "manipulation_method": "how it could potentially be manipulated",
                    "impact_on_token_flow": "how manipulation would affect token flow"
                }}
            }},
            "dependencies": {{
                "dependency_code1": {{
                    "type": "function/modifier/contract", 
                    "description": "what it does", 
                    "manipulation_difficulty": "easy/medium/hard/impossible",
                    "manipulation_method": "how it could potentially be manipulated",
                    "impact_on_token_flow": "how manipulation would affect token flow"
                }}
            }}
        }}
        
        Include only variables and dependencies that actually impact the token flow amount.
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
                        "token_flow_description": "Error parsing response",
                        "variables": {},
                        "dependencies": {},
                        "raw_response": content
                    }
            else:
                result = {
                    "token_flow_description": "Error parsing response",
                    "variables": {},
                    "dependencies": {},
                    "raw_response": content
                }
                
        self.analysis_results = result
        
        # Save results if path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result
    
    def generate_path(self, code: str, path_context: Dict, iteration: int, output_path: str = None) -> Dict:
        """Generate a code path for analysis based on current iteration and previous findings"""
        
        # Define difficulty levels
        difficulty_levels = ["easy", "medium", "hard", "impossible"]
        
        # Filter variables and dependencies based on iteration
        excluded_vars = set(path_context.get("excluded_variables", []))
        
        if iteration == 0:
            # First iteration - focus only on easy to manipulate items
            context = "Analyze only variables and dependencies that are easy to manipulate."
            current_difficulty = difficulty_levels[0]
        elif iteration == 1:
            # Second iteration - add medium difficulty manipulations
            context = "Analyze variables and dependencies with medium manipulation difficulty."
            current_difficulty = difficulty_levels[1]
        elif iteration == 2:
            # Third iteration - add hard difficulty manipulations
            context = "Analyze variables and dependencies that are hard to manipulate."
            current_difficulty = difficulty_levels[2]
        else:
            # Later iterations - try combinations of variables and dependencies
            context = "Analyze combinations of variables and dependencies from different difficulty levels."
            current_difficulty = "combinations"
        
        # Filter variables by difficulty and exclusion list
        if current_difficulty != "combinations":
            variables_to_consider = {
                var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
                if var_info.get("manipulation_difficulty") == current_difficulty and var_name not in excluded_vars
            }
            
            deps_to_consider = {
                dep_code: dep_info for dep_code, dep_info in self.analysis_results.get("dependencies", {}).items()
                if dep_info.get("manipulation_difficulty") == current_difficulty
            }
        else:
            # Consider all non-impossible and non-excluded variables/dependencies
            variables_to_consider = {
                var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
                if var_info.get("manipulation_difficulty") != "impossible" and var_name not in excluded_vars
            }
            
            deps_to_consider = {
                dep_code: dep_info for dep_code, dep_info in self.analysis_results.get("dependencies", {}).items()
                if dep_info.get("manipulation_difficulty") != "impossible"
            }
        
        # Generate the specific path to analyze
        prompt = f"""
        You are analyzing a smart contract for potential vulnerabilities in token flow.
        
        CODE:
        ```solidity
        {code}
        ```
        
        TOKEN FLOW DESCRIPTION:
        {self.analysis_results.get('token_flow_description', 'No description available')}
        
        CONTEXT FOR THIS ANALYSIS: {context}
        
        Variables to consider:
        {json.dumps(variables_to_consider) if variables_to_consider else "None"}
        
        Dependencies to consider:
        {json.dumps(deps_to_consider) if deps_to_consider else "None"}
        
        Previous findings:
        {json.dumps(path_context.get('previous_findings', [])) if path_context.get('previous_findings') else "None"}
        
        Based on the token flow description and the variables/dependencies to consider in this iteration, identify the most promising code path for finding vulnerabilities.
        
        Format your response as a JSON object with:
        {{
            "code_path": "relevant code snippets that represent the token flow path",
            "analysis_focus": "what specific variables or dependencies should be manipulated in this path",
            "manipulation_strategy": "detailed explanation of how to manipulate these variables/dependencies",
            "expected_impact": "expected impact on token flow if manipulation is successful",
            "assumptions": "any assumptions being made in this iteration"
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
                        "code_path": "Error parsing response",
                        "analysis_focus": "Error in parsing",
                        "manipulation_strategy": "Error in parsing",
                        "expected_impact": "Error in parsing",
                        "assumptions": "Error in parsing",
                        "raw_response": content
                    }
            else:
                result = {
                    "code_path": "Error parsing response",
                    "analysis_focus": "Error in parsing",
                    "manipulation_strategy": "Error in parsing",
                    "expected_impact": "Error in parsing",
                    "assumptions": "Error in parsing",
                    "raw_response": content
                }
        
        # Add metadata about the current iteration
        result["iteration_info"] = {
            "iteration": iteration,
            "context": context,
            "difficulty_level": current_difficulty,
            "variables_considered": list(variables_to_consider.keys()),
            "dependencies_considered": list(deps_to_consider.keys())
        }
        
        # Save results if path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result