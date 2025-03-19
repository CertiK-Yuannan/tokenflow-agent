import json
import os
from typing import Dict, List, Tuple, Any

class LogicExtractor:
    def __init__(self, openai_client, model="gpt-4"):
        self.client = openai_client
        self.model = model
        self.analysis_results = {}
        
    def preprocess_code(self, code: str, target_description: str, output_path: str = None) -> Dict:
        """Initial preprocessing of code to understand token flow, variables, and dependencies"""
        
        # Get assumptions from environment variables or use defaults
        privileged_vars_assumption = os.environ.get(
            "ASSUMPTION_PRIVILEGED_VARS", 
            "Variables or external dependencies controlled/configured by a privileged account or set in the constructor should be considered impossible to manipulate"
        )
        
        user_controlled_vars_assumption = os.environ.get(
            "ASSUMPTION_USER_CONTROLLED_VARS", 
            "Variables or external dependencies that users can directly control or update should be considered very easy to manipulate"
        )
        
        manipulation_hierarchy = os.environ.get(
            "ASSUMPTION_MANIPULATION_HIERARCHY", 
            "Variables should be categorized based on their manipulation difficulty (easy, medium, hard, impossible)"
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
        1. {privileged_vars_assumption}
        2. {user_controlled_vars_assumption}
        3. {manipulation_hierarchy}
        
        Provide the following analysis:
        
        1. Describe the overall token flow in the target functionality.
        
        2. Identify all variables (both state and local) that affect token flow amounts, and categorize them based on manipulation difficulty:
           - easy: Variables directly controllable by users
           - medium: Variables indirectly controllable with some prerequisites
           - hard: Variables that require complex prerequisites or exploits to manipulate
           - impossible: Variables controlled by privileged accounts or set in constructor
        
        3. Identify all dependencies (functions, modifiers, imported contracts) that the token flow relies on, and categorize them based on risk of error or manipulation using the same scale (easy, medium, hard, impossible).
        
        Format your response as a JSON object with the following structure:
        {{
            "token_flow_description": "detailed description of the token flow",
            "variables": {{
                "variable_name1": {{
                    "type": "state/local", 
                    "description": "what it does", 
                    "manipulation_difficulty": "easy/medium/hard/impossible",
                    "manipulation_method": "how it could potentially be manipulated",
                    "impact_on_token_flow": "how manipulation would affect token flow"
                }},
                "variable_name2": {{ ... }}
            }},
            "dependencies": {{
                "dependency_code1": {{
                    "type": "function/modifier/contract", 
                    "description": "what it does", 
                    "manipulation_difficulty": "easy/medium/hard/impossible",
                    "manipulation_method": "how it could potentially be manipulated",
                    "impact_on_token_flow": "how manipulation would affect token flow"
                }},
                "dependency_code2": {{ ... }}
            }}
        }}
        
        Include only variables and dependencies that actually impact the token flow amount. Remove any that have no effect.
        For each variable and dependency, provide detailed explanations of how they could be manipulated and their impact.
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
                        "token_flow_description": "Could not parse response. See raw_response for details.",
                        "variables": {},
                        "dependencies": {},
                        "raw_response": content
                    }
            else:
                result = {
                    "token_flow_description": "Could not parse response. See raw_response for details.",
                    "variables": {},
                    "dependencies": {},
                    "raw_response": content
                }
                
        self.analysis_results = result
        
        # Save the preprocessing results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result
    
    def generate_path(self, code: str, path_context: Dict, iteration: int, output_path: str = None) -> Dict:
        """Generate a code path for analysis based on current iteration and previous findings"""
        
        # Get variables and dependencies by difficulty level
        difficulty_levels = ["easy", "medium", "hard", "impossible"]
        
        # Create filtered lists of variables and dependencies based on iteration
        if iteration == 0:
            # First iteration - focus only on easiest to manipulate variables and dependencies
            context = "Analyze only variables and dependencies that are easy to manipulate."
            current_difficulty = difficulty_levels[0]
            
            # Filter variables by current difficulty
            variables_to_consider = {
                var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
                if var_info.get("manipulation_difficulty") == current_difficulty
            }
            
            # Filter dependencies by current difficulty
            deps_to_consider = {
                dep_code: dep_info for dep_code, dep_info in self.analysis_results.get("dependencies", {}).items()
                if dep_info.get("manipulation_difficulty") == current_difficulty
            }
            
        elif iteration == 1:
            # Second iteration - add medium difficulty manipulations
            context = "Analyze variables and dependencies that are medium difficulty to manipulate."
            current_difficulty = difficulty_levels[1]
            
            # Filter variables by current difficulty
            variables_to_consider = {
                var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
                if var_info.get("manipulation_difficulty") == current_difficulty
            }
            
            # Filter dependencies by current difficulty
            deps_to_consider = {
                dep_code: dep_info for dep_code, dep_info in self.analysis_results.get("dependencies", {}).items()
                if dep_info.get("manipulation_difficulty") == current_difficulty
            }
            
        elif iteration == 2:
            # Third iteration - add hard difficulty manipulations
            context = "Analyze variables and dependencies that are hard to manipulate."
            current_difficulty = difficulty_levels[2]
            
            # Filter variables by current difficulty
            variables_to_consider = {
                var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
                if var_info.get("manipulation_difficulty") == current_difficulty
            }
            
            # Filter dependencies by current difficulty
            deps_to_consider = {
                dep_code: dep_info for dep_code, dep_info in self.analysis_results.get("dependencies", {}).items()
                if dep_info.get("manipulation_difficulty") == current_difficulty
            }
            
        else:
            # Later iterations - try combinations of variables and dependencies
            context = "Analyze combinations of variables and dependencies from different difficulty levels."
            
            # Consider all manipulable variables and dependencies (excluding impossible)
            variables_to_consider = {
                var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
                if var_info.get("manipulation_difficulty") != "impossible"
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
                        "code_path": "Could not parse response. See raw_response for details.",
                        "analysis_focus": "Error in parsing",
                        "manipulation_strategy": "Error in parsing",
                        "expected_impact": "Error in parsing",
                        "assumptions": "Error in parsing",
                        "raw_response": content
                    }
            else:
                result = {
                    "code_path": "Could not parse response. See raw_response for details.",
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
            "difficulty_level": current_difficulty if iteration < 3 else "combinations",
            "variables_considered": list(variables_to_consider.keys()),
            "dependencies_considered": list(deps_to_consider.keys())
        }
        
        # Save the path generation results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result