import json
import os
from typing import Dict, List, Set

class LogicExtractor:
    def __init__(self, openai_client, memory_manager, model="gpt-4"):
        self.client = openai_client
        self.model = model
        self.memory_manager = memory_manager
        self.analysis_results = {}
    
    def preprocess_code(self, code: str, target_description: str, output_path: str = None) -> Dict:
        """Initial preprocessing of code to identify variables and dependencies that affect token flow"""
        
        # Get assumptions from global memory
        assumptions = self.memory_manager.get_global_assumptions("logic_extractor")
        
        prompt = f"""
        You are analyzing a smart contract to identify variables and dependencies that affect token flow.
        
        Please analyze the following code, focusing on the described target functionality:
        
        TARGET: {target_description}
        
        CODE:
        ```solidity
        {code}
        ```
        
        ANALYSIS ASSUMPTIONS:
        {json.dumps(assumptions, indent=2)}
        
        Provide the following analysis:
        
        1. Identify all variables (both state and local) that affect token flow amounts, and categorize them based on manipulation difficulty:
           - easy: Variables directly controllable by users
           - medium: Variables indirectly controllable with some prerequisites
           - hard: Variables that require complex prerequisites or exploits to manipulate
           - impossible: Variables controlled by privileged accounts or set in constructor
        
        2. Identify all dependencies (functions, modifiers, imported contracts) that the token flow relies on, and categorize them based on risk of error or manipulation using the same scale.
        
        Format your response as a JSON object with:
        {{
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
        
        Include only variables and dependencies that directly impact token flow amounts.
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
            content = response.choices[0].message.content
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    result = {"variables": {}, "dependencies": {}}
            else:
                result = {"variables": {}, "dependencies": {}}
                
        self.analysis_results = result
        
        # Save to case memory
        self.memory_manager.update_code_context({
            "variables_count": len(result.get("variables", {})),
            "dependencies_count": len(result.get("dependencies", {}))
        })
        
        # Save the preprocessing results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result
    
    def generate_path(self, code: str, iteration: int, output_path: str = None) -> Dict:
        """
        Generate structured code representation for a specific analysis path.
        Each iteration adds one variable/dependency to the analysis, starting from easiest to hardest.
        """
        # Get difficulty levels
        difficulty_levels = ["easy", "medium", "hard", "impossible"]
        
        # Get excluded and included variables from case memory
        excluded_variables = self.memory_manager.get_excluded_variables()
        included_variables = self.memory_manager.get_included_variables()
        previous_findings = self.memory_manager.get_previous_findings()
        
        # Determine what to analyze in this iteration
        current_variables = set()
        current_dependencies = set()
        
        # Add variables from previous iterations to current set
        if iteration > 0 and previous_findings:
            for finding in previous_findings:
                if "variables_analyzed" in finding:
                    current_variables.update(finding["variables_analyzed"])
                if "dependencies_analyzed" in finding:
                    current_dependencies.update(finding["dependencies_analyzed"])
        
        # Add one new variable and one new dependency for this iteration, prioritizing by difficulty
        # Start with explicitly included variables
        new_variable_added = False
        for var_name in included_variables:
            if var_name in self.analysis_results.get("variables", {}) and var_name not in current_variables and var_name not in excluded_variables:
                current_variables.add(var_name)
                new_variable_added = True
                break
                
        # If no included variable was added, add by difficulty level
        if not new_variable_added:
            for difficulty in difficulty_levels:
                if difficulty == "impossible":
                    continue  # Skip impossible variables
                
                for var_name, var_info in self.analysis_results.get("variables", {}).items():
                    if (var_info.get("manipulation_difficulty") == difficulty and 
                        var_name not in current_variables and 
                        var_name not in excluded_variables):
                        current_variables.add(var_name)
                        new_variable_added = True
                        break
                
                if new_variable_added:
                    break
        
        # Add one new dependency, prioritizing by difficulty level
        new_dependency_added = False
        for difficulty in difficulty_levels:
            if difficulty == "impossible":
                continue  # Skip impossible dependencies
                
            for dep_name, dep_info in self.analysis_results.get("dependencies", {}).items():
                if (dep_info.get("manipulation_difficulty") == difficulty and 
                    dep_name not in current_dependencies):
                    current_dependencies.add(dep_name)
                    new_dependency_added = True
                    break
            
            if new_dependency_added:
                break
        
        # Create dictionaries of variables and dependencies to consider
        variables_to_consider = {
            var_name: var_info for var_name, var_info in self.analysis_results.get("variables", {}).items()
            if var_name in current_variables
        }
        
        deps_to_consider = {
            dep_name: dep_info for dep_name, dep_info in self.analysis_results.get("dependencies", {}).items()
            if dep_name in current_dependencies
        }
        
        # Generate the code representation for this path
        prompt = f"""
        You are generating a structured code representation for smart contract analysis.
        
        CODE:
        ```solidity
        {code}
        ```
        
        Variables to analyze in this iteration:
        {json.dumps(variables_to_consider, indent=2)}
        
        Dependencies to analyze in this iteration:
        {json.dumps(deps_to_consider, indent=2)}
        
        Excluded variables (do not consider these):
        {json.dumps(excluded_variables)}
        
        Your task is to generate a pseudo-code representation that shows how the specified variables and dependencies interact in the token flow. The code should focus on:
        
        1. The normal execution path of the contract involving these variables and dependencies.
        """
        
        # Call the API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract the code from the response
        content = response.choices[0].message.content
        
        # Try to extract code block if present
        code_block = ""
        if "```" in content:
            start = content.find("```") + 3
            end = content.rfind("```")
            
            # Skip language identifier if present
            if start < len(content) and content[start] != '\n':
                line_end = content.find('\n', start)
                if line_end > start:
                    start = line_end + 1
            
            if end > start:
                code_block = content[start:end].strip()
        else:
            code_block = content.strip()
        
        # Prepare the result
        result = {
            "analysis_focus": f"Iteration {iteration+1}: Analysis of {len(current_variables)} variables and {len(current_dependencies)} dependencies",
            "code_representation": code_block,
            "variables_analyzed": list(current_variables),
            "dependencies_analyzed": list(current_dependencies),
            "iteration_info": {
                "iteration": iteration,
                "new_variable_added": new_variable_added,
                "new_dependency_added": new_dependency_added,
                "variables_count": len(current_variables),
                "dependencies_count": len(current_dependencies)
            }
        }
        
        # Save the path generation results to a file if output_path is provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
        return result