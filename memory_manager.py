import json
import os
from typing import Dict, List, Any
import logging
from datetime import datetime

class MemoryManager:
    """
    Memory manager that handles both global persistent memory and case-specific temporary memory.
    
    Global memory: Persistent knowledge about assumptions and attack patterns.
    Case memory: Temporary context specific to the current analysis case.
    """
    
    def __init__(self, global_memory_file_path: str = "global_memory.json", case_output_dir: str = None):
        """
        Initialize the memory manager with paths to both global and case-specific memory.
        
        Args:
            global_memory_file_path: Path to the persistent global memory JSON file
            case_output_dir: Directory for the current case analysis where case memory will be stored
        """
        self.global_memory_file_path = global_memory_file_path
        self.case_output_dir = case_output_dir
        
        # Initialize both memory types
        self.global_memory = self._load_global_memory()
        self.case_memory = self._initialize_case_memory()
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for the memory manager"""
        self.logger = logging.getLogger("MemoryManager")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _load_global_memory(self) -> Dict:
        """Load global memory from file or return empty structure if file doesn't exist"""
        if os.path.exists(self.global_memory_file_path):
            try:
                with open(self.global_memory_file_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning(f"Error loading global memory file {self.global_memory_file_path}. Using empty structure.")
                return self._get_empty_global_memory()
        else:
            self.logger.info(f"Global memory file {self.global_memory_file_path} not found. Using empty structure.")
            return self._get_empty_global_memory()
    
    def _get_empty_global_memory(self) -> Dict:
        """Return an empty global memory structure"""
        return {
            "logic_extractor": {
                "assumptions": {},
                "attack_patterns": {}
            },
            "action_generator": {
                "assumptions": {},
                "attack_patterns": {}
            },
            "reflection": {
                "assumptions": {},
                "false_positive_rules": {}
            },
            "meta": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
    
    def _initialize_case_memory(self) -> Dict:
        """Initialize case-specific memory"""
        case_memory = {
            "excluded_variables": [],
            "included_variables": [],
            "analysis_tricks": {},
            "code_context": {},
            "previous_findings": [],
            "meta": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        }
        
        # Save initial case memory if case output directory is specified
        if self.case_output_dir:
            self._save_case_memory(case_memory)
        
        return case_memory
    
    def _save_case_memory(self, memory: Dict = None) -> None:
        """Save case memory to file in the case output directory"""
        if not self.case_output_dir:
            self.logger.warning("Case output directory not specified. Cannot save case memory.")
            return
            
        memory_to_save = memory if memory is not None else self.case_memory
        memory_to_save["meta"]["last_updated"] = datetime.now().isoformat()
        
        memory_file_path = os.path.join(self.case_output_dir, "case_memory.json")
        os.makedirs(os.path.dirname(memory_file_path), exist_ok=True)
        
        with open(memory_file_path, "w") as f:
            json.dump(memory_to_save, f, indent=2)
        
        self.logger.info(f"Case memory saved to {memory_file_path}")
    
    def _save_global_memory(self) -> None:
        """Save global memory to file - used only when explicitly updating global knowledge"""
        self.global_memory["meta"]["last_updated"] = datetime.now().isoformat()
        
        os.makedirs(os.path.dirname(self.global_memory_file_path), exist_ok=True)
        with open(self.global_memory_file_path, "w") as f:
            json.dump(self.global_memory, f, indent=2)
        
        self.logger.info(f"Global memory saved to {self.global_memory_file_path}")
    
    def load_case_memory(self, case_output_dir: str) -> Dict:
        """
        Load case memory from a specific case directory.
        Updates the current case output directory and case memory.
        """
        self.case_output_dir = case_output_dir
        case_memory_path = os.path.join(case_output_dir, "case_memory.json")
        
        if os.path.exists(case_memory_path):
            try:
                with open(case_memory_path, "r") as f:
                    self.case_memory = json.load(f)
                self.logger.info(f"Loaded case memory from {case_memory_path}")
                return self.case_memory
            except json.JSONDecodeError:
                self.logger.warning(f"Error loading case memory from {case_memory_path}. Initializing new case memory.")
                self.case_memory = self._initialize_case_memory()
                return self.case_memory
        else:
            self.logger.info(f"No existing case memory found at {case_memory_path}. Initializing new case memory.")
            self.case_memory = self._initialize_case_memory()
            return self.case_memory
    
    def get_global_assumptions(self, module_name: str) -> Dict:
        """Get global assumptions for a specific module"""
        if module_name in self.global_memory and "assumptions" in self.global_memory[module_name]:
            return self.global_memory[module_name]["assumptions"]
        else:
            self.logger.warning(f"No global assumptions found for module {module_name}")
            return {}
    
    def get_attack_patterns(self, module_name: str) -> Dict:
        """Get attack patterns for a specific module from global memory"""
        if module_name in self.global_memory and "attack_patterns" in self.global_memory[module_name]:
            return self.global_memory[module_name]["attack_patterns"]
        elif module_name in self.global_memory and "false_positive_rules" in self.global_memory[module_name]:
            return self.global_memory[module_name]["false_positive_rules"]
        else:
            self.logger.warning(f"No attack patterns or false positive rules found for module {module_name}")
            return {}
    
    def get_excluded_variables(self) -> List[str]:
        """Get the list of excluded variables from case memory"""
        return self.case_memory.get("excluded_variables", [])
    
    def get_included_variables(self) -> List[str]:
        """Get the list of explicitly included variables from case memory"""
        return self.case_memory.get("included_variables", [])
    
    def get_analysis_tricks(self) -> Dict:
        """Get analysis tricks from case memory"""
        return self.case_memory.get("analysis_tricks", {})
    
    def get_previous_findings(self) -> List[Dict]:
        """Get previous findings from case memory"""
        return self.case_memory.get("previous_findings", [])
    
    def add_excluded_variable(self, variable_name: str) -> None:
        """Add a variable to the excluded list in case memory"""
        if "excluded_variables" not in self.case_memory:
            self.case_memory["excluded_variables"] = []
        
        if variable_name not in self.case_memory["excluded_variables"]:
            self.case_memory["excluded_variables"].append(variable_name)
            self._save_case_memory()
            self.logger.info(f"Added variable to excluded list: {variable_name}")
    
    def add_included_variable(self, variable_name: str) -> None:
        """Add a variable to the explicitly included list in case memory"""
        if "included_variables" not in self.case_memory:
            self.case_memory["included_variables"] = []
        
        if variable_name not in self.case_memory["included_variables"]:
            self.case_memory["included_variables"].append(variable_name)
            self._save_case_memory()
            self.logger.info(f"Added variable to included list: {variable_name}")
    
    def add_analysis_trick(self, trick_name: str, trick_data: Any) -> None:
        """Add an analysis trick to case memory"""
        if "analysis_tricks" not in self.case_memory:
            self.case_memory["analysis_tricks"] = {}
        
        self.case_memory["analysis_tricks"][trick_name] = trick_data
        self._save_case_memory()
        self.logger.info(f"Added analysis trick: {trick_name}")
    
    def add_previous_finding(self, finding: Dict) -> None:
        """Add a finding to the previous findings list in case memory"""
        if "previous_findings" not in self.case_memory:
            self.case_memory["previous_findings"] = []
        
        self.case_memory["previous_findings"].append(finding)
        self._save_case_memory()
        self.logger.info(f"Added finding to previous findings list")
    
    def update_code_context(self, context_data: Dict) -> None:
        """Update the code context in case memory"""
        self.case_memory["code_context"] = context_data
        self._save_case_memory()
        self.logger.info(f"Updated code context in case memory")
    
    def get_code_context(self) -> Dict:
        """Get the code context from case memory"""
        return self.case_memory.get("code_context", {})
    
    def update_global_assumption(self, module_name: str, assumption_name: str, assumption_value: str) -> None:
        """Update a global assumption (only used by authorized processes)"""
        if module_name in self.global_memory:
            if "assumptions" not in self.global_memory[module_name]:
                self.global_memory[module_name]["assumptions"] = {}
            
            self.global_memory[module_name]["assumptions"][assumption_name] = assumption_value
            self._save_global_memory()
            self.logger.info(f"Updated global assumption for {module_name}: {assumption_name}")
        else:
            self.logger.warning(f"Module {module_name} not found in global memory")
    
    def add_attack_pattern(self, module_name: str, pattern_name: str, pattern_data: Any) -> None:
        """Add an attack pattern to global memory (only used by authorized processes)"""
        if module_name in self.global_memory:
            if "attack_patterns" not in self.global_memory[module_name]:
                self.global_memory[module_name]["attack_patterns"] = {}
            
            self.global_memory[module_name]["attack_patterns"][pattern_name] = pattern_data
            self._save_global_memory()
            self.logger.info(f"Added attack pattern for {module_name}: {pattern_name}")
        else:
            self.logger.warning(f"Module {module_name} not found in global memory")
    
    def add_false_positive_rule(self, rule_name: str, rule_data: Any) -> None:
        """Add a false positive rule to global memory (only used by authorized processes)"""
        if "reflection" in self.global_memory:
            if "false_positive_rules" not in self.global_memory["reflection"]:
                self.global_memory["reflection"]["false_positive_rules"] = {}
            
            self.global_memory["reflection"]["false_positive_rules"][rule_name] = rule_data
            self._save_global_memory()
            self.logger.info(f"Added false positive rule: {rule_name}")
        else:
            self.logger.warning("Reflection module not found in global memory")
    
    def get_case_memory_snapshot(self) -> Dict:
        """Get a complete snapshot of the current case memory"""
        return self.case_memory