import json
import os
import openai
import sys
from typing import Dict
from dotenv import load_dotenv
from logic_extractor import LogicExtractor
from action_generator import ActionGenerator
from reflection import Reflection

class TokenFlowAnalyzer:
    def __init__(self, openai_api_key, model="gpt-4o"):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.model = model
        self.logic_extractor = LogicExtractor(self.client, model)
        self.action_generator = ActionGenerator(self.client, model)
        self.reflection = Reflection(self.client, model)
        self.max_iterations = 5
        self.results_history = []
    
    def analyze(self, code: str, target_description: str, goal: str, contract_name: str) -> Dict:
        """Main analysis flow"""
        print(f"Starting analysis of token flow: {target_description}")
        print(f"Goal: {goal}")
        print(f"Using model: {self.model}")
        
        # Create directory structure for outputs
        base_output_dir = os.path.join("analysis_output", contract_name)
        preprocessing_dir = os.path.join(base_output_dir, "preprocessing")
        iterations_dir = os.path.join(base_output_dir, "iterations")
        final_dir = os.path.join(base_output_dir, "final")
        
        # Create directories if they don't exist
        for dir_path in [base_output_dir, preprocessing_dir, iterations_dir, final_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Step 1: Preprocess the code
        preprocessed = self.logic_extractor.preprocess_code(code, target_description, 
                                                           output_path=os.path.join(preprocessing_dir, "preprocessing_results.json"))
        print("Preprocessing completed.")
        print(f"Token Flow Description: {preprocessed.get('token_flow_description', 'Not available')}")
        print(f"Identified {len(preprocessed.get('variables', {}))} variables and {len(preprocessed.get('dependencies', {}))} dependencies")
        
        # Initialize context for the iterations
        path_context = {
            "previous_findings": [],
            "current_iteration": 0,
            "excluded_variables": [],    # Track variables to exclude from analysis
            "excluded_dependencies": []  # Track dependencies to exclude from analysis
        }
        
        # Track which variables and dependencies have been analyzed
        all_variables = set(preprocessed.get("variables", {}).keys())
        all_dependencies = set(preprocessed.get("dependencies", {}).keys())
        analyzed_variables = set()
        analyzed_dependencies = set()
        
        # Main iteration loop
        for i in range(self.max_iterations):
            print(f"\n--- Iteration {i+1} ---")
            path_context["current_iteration"] = i
            
            # Create iteration directory
            iteration_dir = os.path.join(iterations_dir, f"iteration_{i+1}")
            os.makedirs(iteration_dir, exist_ok=True)
            
            # Step 2: Extract logic path for this iteration
            output = self.logic_extractor.generate_path(code, path_context, i, 
                                                       output_path=os.path.join(iteration_dir, "path_analysis.json"))
            print(f"Path generated for iteration {i+1}")
            print(f"Analysis focus: {output.get('analysis_focus', 'Not available')}")
            print(f"Manipulation strategy: {output.get('manipulation_strategy', 'Not available')}")
            
            # Track which variables and dependencies are being analyzed in this iteration
            if "iteration_info" in output and "variables_considered" in output["iteration_info"]:
                analyzed_variables.update(output["iteration_info"]["variables_considered"])
            if "iteration_info" in output and "dependencies_considered" in output["iteration_info"]:
                analyzed_dependencies.update(output["iteration_info"]["dependencies_considered"])
            
            # Step 3: Generate action
            action_result = self.action_generator.generate_action(code, output, goal, i, 
                                                                output_path=os.path.join(iteration_dir, "action_result.json"))
            print(f"Action generated for iteration {i+1}")
            print(f"Vulnerability found: {action_result.get('vulnerability_found', False)}")
            if action_result.get('vulnerability_found', False):
                print(f"Vulnerability type: {action_result.get('vulnerability_type', 'Not specified')}")
                print(f"Confidence: {action_result.get('confidence', 'Not specified')}")
            
            # Step 4: Reflect on the result
            reflection_result = self.reflection.evaluate_result(code, action_result, goal, i, 
                                                              output_path=os.path.join(iteration_dir, "reflection_result.json"))
            print(f"Reflection completed for iteration {i+1}")
            print(f"Goal met: {reflection_result.get('goal_met', False)}")
            print(f"Finding quality: {reflection_result.get('finding_quality', 'Not specified')}")
            
            # Update excluded variables and dependencies
            if "variables_to_exclude" in reflection_result and reflection_result["variables_to_exclude"]:
                if isinstance(reflection_result["variables_to_exclude"], list):
                    path_context["excluded_variables"].extend(reflection_result["variables_to_exclude"])
                else:
                    print(f"Warning: variables_to_exclude is not a list: {reflection_result['variables_to_exclude']}")
            
            # Store results
            result = {
                "iteration": i+1,
                "path": output,
                "action": action_result,
                "reflection": reflection_result,
                "path_context": path_context,
                "analysis_progress": {
                    "total_variables": len(all_variables),
                    "analyzed_variables": len(analyzed_variables),
                    "total_dependencies": len(all_dependencies),
                    "analyzed_dependencies": len(analyzed_dependencies),
                    "variables_remaining": len(all_variables - analyzed_variables),
                    "dependencies_remaining": len(all_dependencies - analyzed_dependencies)
                }
            }
            self.results_history.append(result)
            
            # Save the iteration results
            with open(os.path.join(iteration_dir, "combined_results.json"), "w") as f:
                json.dump(result, f, indent=2)
            
            # Check if goal is met
            if reflection_result.get("goal_met", False):
                print("Goal met! Analysis complete.")
                final_report = self._generate_final_report()
                self._save_final_report(final_report, final_dir)
                return final_report
            
            # Update context for next iteration
            path_context["previous_findings"].append({
                "focus": output.get("analysis_focus", "Not available"),
                "result": action_result.get("vulnerability_found", False),
                "new_focus": reflection_result.get("new_focus_areas", "Not available"),
                "critical_flaws": reflection_result.get("critical_flaws", "Not available"),
                "additional_conditions": reflection_result.get("additional_conditions", "Not available")
            })
            
            # Print suggestions for next iteration
            if i < self.max_iterations - 1:
                print("\nSuggestions for next iteration:")
                print(reflection_result.get("suggestions", "None provided"))
                print(f"New focus areas: {reflection_result.get('new_focus_areas', 'None provided')}")
                if path_context["excluded_variables"]:
                    print(f"Excluded variables: {path_context['excluded_variables']}")
            
            # Check if all variables and dependencies have been analyzed
            remaining_variables = all_variables - analyzed_variables
            remaining_dependencies = all_dependencies - analyzed_dependencies
            
            # Filter out excluded variables
            remaining_variables = remaining_variables - set(path_context["excluded_variables"])
            remaining_dependencies = remaining_dependencies - set(path_context["excluded_dependencies"])
            
            print(f"\nAnalysis progress:")
            print(f"Variables: {len(analyzed_variables)}/{len(all_variables)} analyzed ({len(remaining_variables)} remaining)")
            print(f"Dependencies: {len(analyzed_dependencies)}/{len(all_dependencies)} analyzed ({len(remaining_dependencies)} remaining)")
            
            # Stop if all variables and dependencies have been analyzed
            if not remaining_variables and not remaining_dependencies:
                print("\nAll variables and dependencies have been analyzed. Analysis complete.")
                final_report = self._generate_final_report()
                self._save_final_report(final_report, final_dir)
                return final_report
    
        print("Maximum iterations reached without meeting goal.")
        final_report = self._generate_final_report()
        self._save_final_report(final_report, final_dir)
        return final_report
    
    def _generate_final_report(self) -> Dict:
        """Generate a final comprehensive report from all iterations"""
        
        # Get the best result if any vulnerability was found
        vulnerability_results = [r for r in self.results_history 
                              if r["action"].get("vulnerability_found", False) and 
                                 r["reflection"].get("goal_met", False)]
        
        if vulnerability_results:
            confidence_scores = {"high": 3, "medium": 2, "low": 1}
            best_result = max(vulnerability_results, 
                             key=lambda x: confidence_scores.get(x["action"].get("confidence", "low"), 0))
            
            final_status = "vulnerability_found"
            final_details = best_result
        else:
            final_status = "no_vulnerability_found"
            final_details = None
        
        # Calculate the overall analysis statistics
        total_variables = set()
        total_dependencies = set()
        analyzed_variables = set()
        analyzed_dependencies = set()
        
        for result in self.results_history:
            if "analysis_progress" in result:
                progress = result["analysis_progress"]
                if "analyzed_variables" in progress and isinstance(progress["analyzed_variables"], int):
                    analyzed_variables_count = progress["analyzed_variables"]
                if "total_variables" in progress and isinstance(progress["total_variables"], int):
                    total_variables_count = progress["total_variables"]
                if "analyzed_dependencies" in progress and isinstance(progress["analyzed_dependencies"], int):
                    analyzed_dependencies_count = progress["analyzed_dependencies"]
                if "total_dependencies" in progress and isinstance(progress["total_dependencies"], int):
                    total_dependencies_count = progress["total_dependencies"]
            
            if "path" in result and "iteration_info" in result["path"]:
                info = result["path"]["iteration_info"]
                if "variables_considered" in info and isinstance(info["variables_considered"], list):
                    analyzed_variables.update(info["variables_considered"])
                if "dependencies_considered" in info and isinstance(info["dependencies_considered"], list):
                    analyzed_dependencies.update(info["dependencies_considered"])
        
        # Construct the final report
        report = {
            "status": final_status,
            "iterations_performed": len(self.results_history),
            "best_finding": final_details,
            "all_findings": self.results_history,
            "analysis_summary": {
                "total_variables": total_variables_count if 'total_variables_count' in locals() else len(total_variables),
                "analyzed_variables": analyzed_variables_count if 'analyzed_variables_count' in locals() else len(analyzed_variables),
                "total_dependencies": total_dependencies_count if 'total_dependencies_count' in locals() else len(total_dependencies),
                "analyzed_dependencies": analyzed_dependencies_count if 'analyzed_dependencies_count' in locals() else len(analyzed_dependencies),
                "analysis_completion": "All variables and dependencies analyzed" if 
                    (len(analyzed_variables) == len(total_variables) and len(analyzed_dependencies) == len(total_dependencies))
                    else "Some variables or dependencies not analyzed"
            }
        }
        
        return report
    
    def _save_final_report(self, report: Dict, output_dir: str):
        """Save the final report to a file"""
        with open(os.path.join(output_dir, "final_report.json"), "w") as f:
            json.dump(report, f, indent=2)
        
        # Also create a human-readable summary
        with open(os.path.join(output_dir, "final_report_summary.txt"), "w") as f:
            f.write("SMART CONTRACT TOKEN FLOW ANALYSIS SUMMARY\n")
            f.write("="*50 + "\n\n")
            
            # Add analysis completion statistics
            f.write("ANALYSIS STATISTICS\n")
            f.write(f"Iterations performed: {report['iterations_performed']}\n")
            summary = report.get("analysis_summary", {})
            f.write(f"Variables analyzed: {summary.get('analyzed_variables', 'N/A')}/{summary.get('total_variables', 'N/A')}\n")
            f.write(f"Dependencies analyzed: {summary.get('analyzed_dependencies', 'N/A')}/{summary.get('total_dependencies', 'N/A')}\n")
            f.write(f"Analysis completion: {summary.get('analysis_completion', 'N/A')}\n\n")
            
            if report["status"] == "vulnerability_found":
                best = report["best_finding"]
                f.write("VULNERABILITY FOUND\n")
                f.write(f"Type: {best['action'].get('vulnerability_type', 'Not specified')}\n")
                f.write(f"Confidence: {best['action'].get('confidence', 'Not specified')}\n\n")
                
                f.write("ATTACK SCENARIO:\n")
                f.write(f"{best['action'].get('attack_scenario', 'Not specified')}\n\n")
                
                f.write("PROFIT MECHANISM:\n")
                f.write(f"{best['action'].get('profit_mechanism', 'Not specified')}\n\n")
                
                f.write("EXPLOIT CODE/SEQUENCE:\n")
                f.write(f"{best['action'].get('exploit_code', 'Not specified')}\n\n")
                
                f.write("REASONING:\n")
                f.write(f"{best['action'].get('reasoning', 'Not specified')}\n\n")
                
                f.write("EVALUATION:\n")
                f.write(f"{best['reflection'].get('evaluation', 'Not specified')}\n\n")
            else:
                f.write("NO VULNERABILITY FOUND\n\n")
                f.write("The analysis did not identify any vulnerabilities that meet the goal criteria.\n\n")
                f.write("Summary of attempted approaches:\n")
                
                for i, finding in enumerate(report["all_findings"]):
                    f.write(f"\nIteration {i+1}:\n")
                    f.write(f"Focus: {finding['path'].get('analysis_focus', 'Not specified')}\n")
                    f.write(f"Result: {'Potential vulnerability found but not confirmed' if finding['action'].get('vulnerability_found', False) else 'No vulnerability found'}\n")
                    if finding['action'].get('vulnerability_found', False):
                        f.write(f"Type: {finding['action'].get('vulnerability_type', 'Not specified')}\n")
                        f.write(f"Why it didn't meet the goal: {finding['reflection'].get('critical_flaws', 'Not specified')}\n")
            
            f.write("\n" + "="*50 + "\n")
            f.write("End of Report\n")


def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get OpenAI API key and model from environment variables
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in .env file")
        print("Please create a .env file with your OpenAI API key like this: OPENAI_API_KEY=your-api-key")
        return
    
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")
    print(f"Using model: {openai_model}")
    
    # Get analysis goal from environment variables or use default
    analysis_goal = os.environ.get(
        "ANALYSIS_GOAL", 
        "Identify if there exists a vulnerability in the code logic where an attacker can manipulate the token flow to profit"
    )
    
    # Get target information from environment variables
    target_contract_name = os.environ.get("TARGET_CONTRACT_NAME")
    target_function = os.environ.get("TARGET_FUNCTION")
    target_token_transfer = os.environ.get("TARGET_TOKEN_TRANSFER")
    
    # Check if code file is specified as command line argument
    if len(sys.argv) > 1:
        code_file = sys.argv[1]
    else:
        print("Error: Please specify the path to the contract code file as a command line argument")
        return
    
    # Load contract code
    try:
        with open(code_file, "r") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find file '{code_file}'")
        return
    
    # If target function or token transfer isn't specified, use defaults
    if not target_function:
        target_function = "withdrawTokensV3"
    if not target_token_transfer:
        target_token_transfer = "IERC20(token).safeTransfer(_userAddress, availableAmountForClaim(_userAddress))"
    
    # Construct target description
    target_description = (
        f"Please analyze {target_contract_name}.sol {target_function} function "
        f"with focus on {target_token_transfer};"
    )
    
    # Initialize the analyzer
    analyzer = TokenFlowAnalyzer(openai_api_key=openai_api_key, model=openai_model)
    
    # Run the analysis
    results = analyzer.analyze(code, target_description, analysis_goal, target_contract_name)
    
    # Print summary
    print("\n" + "="*50)
    print("ANALYSIS COMPLETE")
    print("="*50)
    
    output_dir = os.path.join("analysis_output", target_contract_name, "final")
    
    if results["status"] == "vulnerability_found":
        print("\n=== VULNERABILITY FOUND ===")
        best = results["best_finding"]
        print(f"Type: {best['action'].get('vulnerability_type', 'Not specified')}")
        print(f"Confidence: {best['action'].get('confidence', 'Not specified')}")
        print("\nAttack Scenario:")
        print(f"{best['action'].get('attack_scenario', 'Not specified')}")
        print("\nProfit Mechanism:")
        print(f"{best['action'].get('profit_mechanism', 'Not specified')}")
        print(f"\nSee the detailed report in the '{output_dir}' directory.")
    else:
        print("\n=== NO VULNERABILITY FOUND ===")
        print("The analysis did not identify any vulnerabilities that meet the goal criteria.")
        print(f"See the detailed report in the '{output_dir}' directory.")


if __name__ == "__main__":
    main()