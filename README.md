# TokenFlow Agent

A smart contract security analysis tool specializing in token flow vulnerabilities. The TokenFlow Agent automatically identifies and analyzes potential vulnerabilities in smart contract code that could allow attackers to manipulate token flow for profit.

## Overview

This tool uses advanced AI models to progressively analyze smart contract code, focusing on token transfer functions to identify potential security vulnerabilities. It performs an iterative analysis, examining variables and dependencies that impact token flows, generating attack scenarios, and validating whether vulnerabilities exist.

## Features

- Automated analysis of smart contract token flow vulnerabilities
- Progressive, iterative exploration of variables and dependencies
- Detection of manipulation points in token-related functions
- Detailed attack scenario generation with profit mechanisms
- Comprehensive reporting with evaluation of vulnerability severity
- Memory management for case-specific and global analysis knowledge

## Requirements

- Python 3.8+
- OpenAI API key
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tokenflow-agent.git
cd tokenflow-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root directory with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o  # or another appropriate model
```

## Usage

Run the analyzer on a smart contract file:

```bash
python analyzer.py path/to/your/contract.sol
```

Optional environment variables that can be set in the `.env` file:
- `TARGET_FUNCTION`: The specific function to analyze (default: "withdrawTokensV3")
- `TARGET_TOKEN_TRANSFER`: The token transfer code to focus on 
- `MAX_ITERATIONS`: Maximum number of analysis iterations (default: 5)
- `GLOBAL_MEMORY_FILE`: Path to the global memory file (default: "global_memory.json")

## Output

The tool generates a detailed analysis in the `analysis_output` directory, organized as follows:

- `analysis_output/[contract_name]/preprocessing`: Initial variable and dependency analysis
- `analysis_output/[contract_name]/iterations`: Results from each analysis iteration
- `analysis_output/[contract_name]/final`: Final report with vulnerability details

The final report includes:
- Vulnerability details (if found)
- Attack scenarios
- Profit mechanisms
- Exploit sequences
- Comprehensive explanation of the vulnerability

## Core Components

### 1. TokenFlowAnalyzer (`analyzer.py`)
Orchestrates the entire analysis process, managing the iterative exploration of smart contract code.

### 2. LogicExtractor (`logic_extractor.py`)
Analyzes the smart contract code to identify variables and dependencies that affect token flow, categorizing them by manipulation difficulty.

### 3. ActionGenerator (`action_generator.py`)
Generates potential attack scenarios based on code representations, determining if vulnerabilities exist and how they could be exploited.

### 4. Reflection (`reflection.py`)
Evaluates the findings from the ActionGenerator, determining if they truly represent vulnerabilities and providing feedback for future iterations.

### 5. MemoryManager (`memory_manager.py`)
Manages both global and case-specific memory, maintaining knowledge across analysis sessions and tracking discoveries.

## Example

Analyzing a contract with potential reentrancy vulnerability:

```bash
python analyzer.py contracts/VulnerableStaking.sol
```

This will analyze the contract, focusing on token flow manipulation in the withdrawal functions, and generate a detailed report of any found vulnerabilities.

## License

[Your License Info Here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.