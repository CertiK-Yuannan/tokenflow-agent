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
        """Main analysis flow with simplified output and better iteration handling"""
        print(f"Starting analysis of {contract_name} with target: {target_description}")
        
        # Create directory structure for outputs
        base_output_dir = os.path.join("analysis_output", contract_name)
        preprocessing_dir = os.path.join(base_output_dir, "preprocessing")
        iterations_dir = os.path.join(base_output_dir, "iterations")
        final_dir = os.path.join(base_output_dir, "final")
        
        for dir_path in [base_output_dir, preprocessing_dir, iterations_dir, final_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Step 1: Preprocess the code
        preprocessed = self.logic_extractor.preprocess_code(
            code, 
            target_description, 
            output_path=os.path.join(preprocessing_dir, "preprocessing_results.json")
        )
        
        print("\n=== Preprocessing Completed ===")
        print(f"Token Flow: {preprocessed.get('token_flow_description', 'Not available')[:100]}...")
        print(f"Variables: {len(preprocessed.get('variables', {}))} | Dependencies: {len(preprocessed.get('dependencies', {}))}")
        
        # Initialize analysis context
        path_context = {
            "previous_findings": [],
            "current_iteration": 0,
            "excluded_variables": [],
            "excluded_dependencies": []
        }
        
        # Track analysis progress
        all_variables = set(preprocessed.get("variables", {}).keys())
        all_dependencies = set(preprocessed.get("dependencies", {}).keys())
        analyzed_variables = set()
        analyzed_dependencies = set()
        
        # Main iteration loop
        for iteration in range(self.max_iterations):
            print(f"\n=== Iteration {iteration+1}/{self.max_iterations} ===")
            path_context["current_iteration"] = iteration
            
            # Create iteration directory
            iteration_dir = os.path.join(iterations_dir, f"iteration_{iteration+1}")
            os.makedirs(iteration_dir, exist_ok=True)
            
            # Step 2: Extract logic path
            output = self.logic_extractor.generate_path(
                code, 
                path_context, 
                iteration, 
                output_path=os.path.join(iteration_dir, "path_analysis.json")
            )
            
            print(f"\nPath Analysis:")
            print(f"Focus: {output.get('analysis_focus', 'Not available')[:100]}...")
            print(f"Strategy: {output.get('manipulation_strategy', 'Not available')[:100]}...")
            
            # Update analyzed variables/dependencies
            if "iteration_info" in output:
                if "variables_considered" in output["iteration_info"]:
                    analyzed_variables.update(output["iteration_info"]["variables_considered"])
                if "dependencies_considered" in output["iteration_info"]:
                    analyzed_dependencies.update(output["iteration_info"]["dependencies_considered"])
            
            # Step 3: Generate action
            action_result = self.action_generator.generate_action(
                code, 
                output, 
                goal, 
                iteration, 
                output_path=os.path.join(iteration_dir, "action_result.json")
            )
            
            print(f"\nAction Analysis:")
            vulnerability_found = action_result.get('vulnerability_found', False)
            print(f"Vulnerability found: {'Yes' if vulnerability_found else 'No'}")
            if vulnerability_found:
                print(f"Type: {action_result.get('vulnerability_type', 'Not specified')}")
                print(f"Confidence: {action_result.get('confidence', 'Not specified')}")
            
            # Step 4: Reflect on the result
            reflection_result = self.reflection.evaluate_result(
                code, 
                action_result, 
                goal, 
                iteration, 
                output_path=os.path.join(iteration_dir, "reflection_result.json")
            )
            
            print(f"\nReflection:")
            print(f"Goal met: {'Yes' if reflection_result.get('goal_met', False) else 'No'}")
            print(f"Finding quality: {reflection_result.get('finding_quality', 'Not specified')}")
            
            # Add excluded variables to context
            if "variables_to_exclude" in reflection_result:
                excluded_vars = reflection_result["variables_to_exclude"]
                if isinstance(excluded_vars, list):
                    path_context["excluded_variables"].extend(excluded_vars)
                    print(f"Variables excluded: {excluded_vars}")
            
            # Store iteration results
            result = {
                "iteration": iteration+1,
                "path": output,
                "action": action_result,
                "reflection": reflection_result,
                "path_context": path_context,
                "analysis_progress": {
                    "total_variables": len(all_variables),
                    "analyzed_variables": len(analyzed_variables),
                    "total_dependencies": len(all_dependencies),
                    "analyzed_dependencies": len(analyzed_dependencies),
                    "variables_remaining": len(all_variables - analyzed_variables - set(path_context["excluded_variables"])),
                    "dependencies_remaining": len(all_dependencies - analyzed_dependencies - set(path_context["excluded_dependencies"]))
                }
            }
            self.results_history.append(result)
            
            # Save iteration results
            with open(os.path.join(iteration_dir, "combined_results.json"), "w") as f:
                json.dump(result, f, indent=2)
            
            # Update context for next iteration
            path_context["previous_findings"].append({
                "focus": output.get("analysis_focus", "Not available"),
                "result": action_result.get("vulnerability_found", False),
                "new_focus": reflection_result.get("new_focus_areas", "Not available"),
                "critical_flaws": reflection_result.get("critical_flaws", "Not available"),
                "additional_conditions": reflection_result.get("additional_conditions", "Not available")
            })
            
            # Print suggestions for next iteration
            if iteration < self.max_iterations - 1:
                print(f"\nNext iteration will focus on: {reflection_result.get('new_focus_areas', 'Not specified')[:100]}...")
            
            # Check if all variables and dependencies have been analyzed or excluded
            remaining_variables = all_variables - analyzed_variables - set(path_context["excluded_variables"])
            remaining_dependencies = all_dependencies - analyzed_dependencies - set(path_context["excluded_dependencies"])
            
            print(f"\nProgress: Variables {len(analyzed_variables)}/{len(all_variables)} | Dependencies {len(analyzed_dependencies)}/{len(all_dependencies)}")
            
            # Stop if all variables and dependencies have been analyzed
            if not remaining_variables and not remaining_dependencies:
                print("\n=== All variables and dependencies analyzed. Analysis complete. ===")
                final_report = self._generate_final_report()
                self._save_final_report(final_report, final_dir)
                return final_report
    
        print("\n=== Maximum iterations reached. Analysis complete. ===")
        final_report = self._generate_final_report()
        self._save_final_report(final_report, final_dir)
        return final_report
    
    def _generate_final_report(self) -> Dict:
        """Generate a final comprehensive report from all iterations"""
        
        # Find the best vulnerability result if any
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
        
        # Calculate overall analysis statistics
        analyzed_variables = set()
        analyzed_dependencies = set()
        
        for result in self.results_history:
            if "path" in result and "iteration_info" in result["path"]:
                info = result["path"]["iteration_info"]
                if "variables_considered" in info and isinstance(info["variables_considered"], list):
                    analyzed_variables.update(info["variables_considered"])
                if "dependencies_considered" in info and isinstance(info["dependencies_considered"], list):
                    analyzed_dependencies.update(info["dependencies_considered"])
        
        # Get total variables and dependencies from the first iteration's analysis_progress
        if self.results_history:
            progress = self.results_history[0].get("analysis_progress", {})
            total_variables = progress.get("total_variables", 0)
            total_dependencies = progress.get("total_dependencies", 0)
        else:
            total_variables = 0
            total_dependencies = 0
        
        # Construct the final report
        report = {
            "status": final_status,
            "iterations_performed": len(self.results_history),
            "best_finding": final_details,
            "all_findings": self.results_history,
            "analysis_summary": {
                "total_variables": total_variables,
                "analyzed_variables": len(analyzed_variables),
                "total_dependencies": total_dependencies,
                "analyzed_dependencies": len(analyzed_dependencies),
                "analysis_completion": "Complete" if (len(analyzed_variables) == total_variables and 
                                                    len(analyzed_dependencies) == total_dependencies) 
                                      else "Incomplete"
            }
        }
        
        return report
    
    def _save_final_report(self, report: Dict, output_dir: str):
        """Save the final report to a file with improved formatting"""
        # Save JSON report
        with open(os.path.join(output_dir, "final_report.json"), "w") as f:
            json.dump(report, f, indent=2)
        
        # Create a human-readable summary
        with open(os.path.join(output_dir, "final_report_summary.txt"), "w") as f:
            f.write("SMART CONTRACT TOKEN FLOW ANALYSIS SUMMARY\n")
            f.write("="*50 + "\n\n")
            
            # Analysis statistics
            summary = report.get("analysis_summary", {})
            f.write("ANALYSIS STATISTICS\n")
            f.write(f"Iterations performed: {report['iterations_performed']}\n")
            f.write(f"Variables analyzed: {summary.get('analyzed_variables', 'N/A')}/{summary.get('total_variables', 'N/A')}\n")
            f.write(f"Dependencies analyzed: {summary.get('analyzed_dependencies', 'N/A')}/{summary.get('total_dependencies', 'N/A')}\n")
            f.write(f"Analysis completion: {summary.get('analysis_completion', 'N/A')}\n\n")
            
            # Vulnerability details if found
            if report["status"] == "vulnerability_found" and report["best_finding"]:
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
                
                f.write("EVALUATION:\n")
                f.write(f"{best['reflection'].get('evaluation', 'Not specified')}\n\n")
            else:
                f.write("NO VULNERABILITY FOUND\n\n")
                f.write("The analysis did not identify any exploitable vulnerabilities.\n\n")
                f.write("SUMMARY OF ATTEMPTED APPROACHES:\n")
                
                for i, finding in enumerate(report["all_findings"]):
                    f.write(f"\nIteration {i+1}:\n")
                    f.write(f"Focus: {finding['path'].get('analysis_focus', 'Not specified')[:150]}...\n")
                    f.write(f"Result: {'Potential vulnerability' if finding['action'].get('vulnerability_found', False) else 'No vulnerability found'}\n")
                    if finding['action'].get('vulnerability_found', False):
                        f.write(f"Type: {finding['action'].get('vulnerability_type', 'Not specified')}\n")
                        f.write(f"Not viable because: {finding['reflection'].get('critical_flaws', 'Not specified')[:150]}...\n")
            
            f.write("\n" + "="*50 + "\n")
            f.write("End of Report\n")


def main():
    # Load environment variables
    load_dotenv()
    
    # Get OpenAI API key
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in .env file")
        sys.exit(1)
    
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4")
    
    # Get analysis parameters
    analysis_goal = os.environ.get(
        "ANALYSIS_GOAL", 
        "Identify if there exists a vulnerability in the code logic where an attacker can manipulate the token flow to profit"
    )
    
    target_contract_name = os.environ.get("TARGET_CONTRACT_NAME", "Contract")
    target_function = os.environ.get("TARGET_FUNCTION", "withdrawTokensV3")
    target_token_transfer = os.environ.get("TARGET_TOKEN_TRANSFER", 
        "IERC20(token).safeTransfer(_userAddress, availableAmountForClaim(_userAddress))"
    )
    
    # Check for code file argument
    if len(sys.argv) > 1:
        code_file = sys.argv[1]
    else:
        print("Error: Please specify the path to the contract code file as a command line argument")
        sys.exit(1)
    
    # Load contract code
    try:
        with open(code_file, "r") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find file '{code_file}'")
        sys.exit(1)
    
    # Construct target description
    target_description = (
        f"Analyze {target_contract_name}.sol {target_function} function "
        f"with focus on {target_token_transfer}"
    )
    
    # Run the analysis
    analyzer = TokenFlowAnalyzer(openai_api_key=openai_api_key, model=openai_model)
    results = analyzer.analyze(code, target_description, analysis_goal, target_contract_name)
    
    # Print summary
    print("\n" + "="*50)
    print("ANALYSIS COMPLETE")
    print("="*50)
    
    output_dir = os.path.join("analysis_output", target_contract_name, "final")
    
    if results["status"] == "vulnerability_found" and results["best_finding"]:
        best = results["best_finding"]
        print("\n=== VULNERABILITY FOUND ===")
        print(f"Type: {best['action'].get('vulnerability_type', 'Not specified')}")
        print(f"Confidence: {best['action'].get('confidence', 'Not specified')}")
        print(f"Attack: {best['action'].get('attack_scenario', 'Not specified')[:150]}...")
        print(f"\nSee detailed report in '{output_dir}'")
    else:
        print("\n=== NO VULNERABILITY FOUND ===")
        print("No exploitable vulnerabilities were identified.")
        print(f"See detailed report in '{output_dir}'")


if __name__ == "__main__":
    main()