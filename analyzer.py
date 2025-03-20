import json
import os
import openai
import sys
from typing import Dict, Set
from dotenv import load_dotenv
from logic_extractor import LogicExtractor
from action_generator import ActionGenerator
from reflection import Reflection
from memory_manager import MemoryManager

class TokenFlowAnalyzer:
    def __init__(self, openai_api_key, model="gpt-4o", global_memory_file="global_memory.json"):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.model = model
        self.global_memory_file = global_memory_file
        self.max_iterations = int(os.environ.get("MAX_ITERATIONS", "5"))
        self.results_history = []
        self.memory_manager = None
        self.logic_extractor = None
        self.action_generator = None
        self.reflection = None
    
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
        
        # Initialize memory manager and components with case-specific output directory
        self.memory_manager = MemoryManager(global_memory_file_path=self.global_memory_file, case_output_dir=base_output_dir)
        self.logic_extractor = LogicExtractor(self.client, self.memory_manager, self.model)
        self.action_generator = ActionGenerator(self.client, self.memory_manager, self.model)
        self.reflection = Reflection(self.client, self.memory_manager, self.model)
        
        # Step 1: Preprocess the code to identify variables and dependencies
        preprocessed = self.logic_extractor.preprocess_code(code, target_description, 
                                                           output_path=os.path.join(preprocessing_dir, "preprocessing_results.json"))
        print("Preprocessing completed.")
        print(f"Identified {len(preprocessed.get('variables', {}))} variables and {len(preprocessed.get('dependencies', {}))} dependencies")
        
        # Track which variables and dependencies have been analyzed
        all_variables = set(preprocessed.get("variables", {}).keys())
        all_dependencies = set(preprocessed.get("dependencies", {}).keys())
        analyzed_variables = set()
        analyzed_dependencies = set()
        
        # Main iteration loop
        for i in range(self.max_iterations):
            print(f"\n--- Iteration {i+1} ---")
            
            # Create iteration directory
            iteration_dir = os.path.join(iterations_dir, f"iteration_{i+1}")
            os.makedirs(iteration_dir, exist_ok=True)
            
            # Take a snapshot of case memory before the iteration
            with open(os.path.join(iteration_dir, "case_memory_before.json"), "w") as f:
                json.dump(self.memory_manager.get_case_memory_snapshot(), f, indent=2)
            
            # Step 2: Generate code representation for this iteration
            path_output = self.logic_extractor.generate_path(code, i, 
                                                       output_path=os.path.join(iteration_dir, "path_analysis.json"))
            print(f"Path generated for iteration {i+1}")
            print(f"Analysis focus: {path_output.get('analysis_focus', 'Not available')}")
            
            # Update analyzed variables and dependencies tracking
            if "variables_analyzed" in path_output:
                analyzed_variables.update(path_output["variables_analyzed"])
            if "dependencies_analyzed" in path_output:
                analyzed_dependencies.update(path_output["dependencies_analyzed"])
            
            # Step 3: Generate action based on the code representation
            action_result = self.action_generator.generate_action(code, path_output, goal, i, 
                                                                output_path=os.path.join(iteration_dir, "action_result.json"))
            print(f"Action generated for iteration {i+1}")
            print(f"Vulnerability found: {action_result.get('vulnerability_found', False)}")
            if action_result.get('vulnerability_found', False):
                print(f"Vulnerability type: {action_result.get('vulnerability_type', 'Not specified')}")
                print(f"Confidence: {action_result.get('confidence', 'Not specified')}")
            
            # Step 4: Reflect on the result and update case-specific memory
            reflection_result = self.reflection.evaluate_result(code, path_output, action_result, goal, i, 
                                                              output_path=os.path.join(iteration_dir, "reflection_result.json"))
            print(f"Reflection completed for iteration {i+1}")
            print(f"Goal met: {reflection_result.get('goal_met', False)}")
            print(f"Finding quality: {reflection_result.get('finding_quality', 'Not specified')}")
            
            # Take a snapshot of case memory after the iteration
            with open(os.path.join(iteration_dir, "case_memory_after.json"), "w") as f:
                json.dump(self.memory_manager.get_case_memory_snapshot(), f, indent=2)
            
            # Store results
            result = {
                "iteration": i+1,
                "path": path_output,
                "action": action_result,
                "reflection": reflection_result,
                "analysis_progress": {
                    "total_variables": len(all_variables),
                    "analyzed_variables": len(analyzed_variables),
                    "total_dependencies": len(all_dependencies),
                    "analyzed_dependencies": len(analyzed_dependencies),
                    "variables_remaining": len(all_variables - analyzed_variables - set(self.memory_manager.get_excluded_variables())),
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
                final_report = self._generate_final_report(contract_name, goal, "vulnerability_found")
                self._save_final_report(final_report, final_dir)
                # return final_report
            
            # Print suggestions for next iteration
            if i < self.max_iterations - 1:
                print("\nSuggestions for next iteration:")
                print(reflection_result.get("suggestions", "None provided"))
                print(f"New focus areas: {reflection_result.get('new_focus_areas', 'None provided')}")
                
                excluded_vars = self.memory_manager.get_excluded_variables()
                if excluded_vars:
                    print(f"Excluded variables: {excluded_vars}")
                
                included_vars = self.memory_manager.get_included_variables()
                if included_vars:
                    print(f"Explicitly included variables: {included_vars}")
            
            # Get excluded variables from case memory
            excluded_vars = self.memory_manager.get_excluded_variables()
            
            # Check if all variables and dependencies have been analyzed or excluded
            remaining_variables = all_variables - analyzed_variables - set(excluded_vars)
            remaining_dependencies = all_dependencies - analyzed_dependencies
            
            print(f"\nAnalysis progress:")
            print(f"Variables: {len(analyzed_variables)}/{len(all_variables)} analyzed, {len(excluded_vars)} excluded, {len(remaining_variables)} remaining")
            print(f"Dependencies: {len(analyzed_dependencies)}/{len(all_dependencies)} analyzed, {len(remaining_dependencies)} remaining")
            
            # Stop if all variables and dependencies have been analyzed
            if not remaining_variables and not remaining_dependencies:
                print("\nAll variables and dependencies have been analyzed or excluded. Analysis complete.")
                final_report = self._generate_final_report(contract_name, goal, "analysis_complete_no_vulnerability_found")
                self._save_final_report(final_report, final_dir)
                return final_report
    
        print("Maximum iterations reached without meeting goal.")
        final_report = self._generate_final_report(contract_name, goal, "max_iterations_reached_no_vulnerability_found")
        self._save_final_report(final_report, final_dir)
        return final_report
    
    def _generate_final_report(self, contract_name: str, goal: str, status: str) -> Dict:
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
            final_status = status
            final_details = None
        
        # Calculate the overall analysis statistics
        analyzed_variables = set()
        analyzed_dependencies = set()
        
        for result in self.results_history:
            if "path" in result:
                if "variables_analyzed" in result["path"]:
                    analyzed_variables.update(result["path"]["variables_analyzed"])
                if "dependencies_analyzed" in result["path"]:
                    analyzed_dependencies.update(result["path"]["dependencies_analyzed"])
        
        # Get current case memory state
        case_memory_state = self.memory_manager.get_case_memory_snapshot()
        excluded_variables = set(case_memory_state.get("excluded_variables", []))
        
        # Get all variables and dependencies from preprocessing results
        all_variables = set(self.logic_extractor.analysis_results.get("variables", {}).keys())
        all_dependencies = set(self.logic_extractor.analysis_results.get("dependencies", {}).keys())
        
        # Construct the final report
        report = {
            "contract_name": contract_name,
            "goal": goal,
            "status": final_status,
            "iterations_performed": len(self.results_history),
            "best_finding": final_details,
            "all_findings": self.results_history,
            "analysis_summary": {
                "total_variables": len(all_variables),
                "analyzed_variables": len(analyzed_variables),
                "excluded_variables": len(excluded_variables),
                "total_dependencies": len(all_dependencies),
                "analyzed_dependencies": len(analyzed_dependencies),
                "analysis_completion": "All variables and dependencies analyzed" if 
                    (len(analyzed_variables) + len(excluded_variables) >= len(all_variables) and 
                     len(analyzed_dependencies) >= len(all_dependencies))
                    else "Some variables or dependencies not analyzed"
            },
            "case_memory_state": case_memory_state
        }
        
        return report
    
    def _save_final_report(self, report: Dict, output_dir: str):
        """Save the final report to a file"""
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "final_report.json"), "w") as f:
            json.dump(report, f, indent=2)
        
        # Also create a human-readable summary
        with open(os.path.join(output_dir, "final_report_summary.txt"), "w") as f:
            f.write("SMART CONTRACT TOKEN FLOW ANALYSIS SUMMARY\n")
            f.write("="*50 + "\n\n")
            
            # Add analysis completion statistics
            f.write("ANALYSIS STATISTICS\n")
            f.write(f"Contract: {report['contract_name']}\n")
            f.write(f"Goal: {report['goal']}\n")
            f.write(f"Iterations performed: {report['iterations_performed']}\n")
            summary = report.get("analysis_summary", {})
            f.write(f"Variables analyzed: {summary.get('analyzed_variables', 'N/A')}/{summary.get('total_variables', 'N/A')}\n")
            f.write(f"Variables excluded: {summary.get('excluded_variables', 'N/A')}\n")
            f.write(f"Dependencies analyzed: {summary.get('analyzed_dependencies', 'N/A')}/{summary.get('total_dependencies', 'N/A')}\n")
            f.write(f"Analysis completion: {summary.get('analysis_completion', 'N/A')}\n\n")
            
            # Add case memory summary
            f.write("CASE MEMORY SUMMARY\n")
            case_memory = report.get("case_memory_state", {})
            f.write(f"Excluded variables: {case_memory.get('excluded_variables', [])}\n")
            f.write(f"Included variables: {case_memory.get('included_variables', [])}\n")
            f.write(f"Analysis tricks count: {len(case_memory.get('analysis_tricks', {}))}\n")
            f.write(f"Previous findings count: {len(case_memory.get('previous_findings', []))}\n\n")
            
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
                    if "variables_analyzed" in finding["path"]:
                        f.write(f"Variables analyzed: {finding['path'].get('variables_analyzed', [])}\n")
                    if "dependencies_analyzed" in finding["path"]:
                        f.write(f"Dependencies analyzed: {finding['path'].get('dependencies_analyzed', [])}\n")
                    f.write(f"Result: {'Potential vulnerability found but not confirmed' if finding['action'].get('vulnerability_found', False) else 'No vulnerability found'}\n")
                    if finding['action'].get('vulnerability_found', False):
                        f.write(f"Type: {finding['action'].get('vulnerability_type', 'Not specified')}\n")
                        f.write(f"Why it didn't meet the goal: {finding['reflection'].get('critical_flaws', 'Not specified')}\n")
            
            f.write("\n" + "="*50 + "\n")
            f.write("End of Report\n")

def main():
    """Main entry point for the smart contract token flow analyzer"""
    
    # Load environment variables from .env file
    from dotenv import load_dotenv
    import sys
    
    load_dotenv()
    
    # Get OpenAI API key and model from environment variables
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in .env file")
        print("Please create a .env file with your OpenAI API key like this: OPENAI_API_KEY=your-api-key")
        return
    
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")
    print(f"Using model: {openai_model}")
    
    # Get global memory file path from environment variables or use default
    global_memory_file = os.environ.get("GLOBAL_MEMORY_FILE", "global_memory.json")
    print(f"Using global memory file: {global_memory_file}")
    
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
    
    # If target contract name isn't specified, derive it from the filename
    if not target_contract_name:
        target_contract_name = os.path.splitext(os.path.basename(code_file))[0]
    
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
    analyzer = TokenFlowAnalyzer(
        openai_api_key=openai_api_key, 
        model=openai_model,
        global_memory_file=global_memory_file
    )
    
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