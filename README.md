# TokenFlow Analyzer

A modular AI agent system for analyzing token flow vulnerabilities in smart contracts. The agent progressively adds complexity to its analysis, gradually incorporating variables and dependencies to find potential vulnerabilities.

## Architecture

The TokenFlow Analyzer consists of three main modules:

1. **Logic Extractor**: Analyzes the code to understand token flow paths, influential variables, and dependencies. It starts with a simple analysis and progressively adds complexity.

2. **Action Generator**: Generates potential attack scenarios based on the extracted logic paths.

3. **Reflection**: Evaluates the findings, determining if a vulnerability has been found, and provides feedback for the next iteration.

These modules work together in an iterative process, starting with simple token flow analysis and gradually incorporating more context until a vulnerability is found or all possibilities are exhausted.

## Directory Structure
tokenflow-agent/
│
├── analyzer.py                 # Main controller and entry point
├── action_generator.py         # Action generator module
├── logic_extractor.py          # Logic extractor module
├── reflection.py               # Reflection module
├── setup.py                    # Directory structure setup script
│
├── test/                       # Directory for test Solidity contracts
│   └── StakeDeodV3.sol         # Example contract
│
└── analysis_output/            # Analysis outputs organized by contract
└── [ContractName]/         # Subdirectory for each analyzed contract
├── preprocessing/      # Preprocessing results
├── iterations/         # Results from each iteration
└── final/              # Final reports

## Getting Started

### Prerequisites

- Python 3.7 or higher
- An OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tokenflow-agent.git
cd tokenflow-agent
```
2. Install the required packages:
```bash
bashCopypip install openai python-dotenv
```


3. Create a .env file with your OpenAI API key:
```bash
echo "OPENAI_API_KEY=your-openai-api-key" > .env
echo "OPENAI_MODEL=gpt-4" >> .env
echo "MAX_ITERATIONS=5" >> .env
```

### Usage

1. Place your Solidity contract in the test directory.
2. Run the analysis:
```bash
python analyzer.py test/YourContract.sol
```
3. Check the results in the `analysis_output/YourContract/` directory.

Configuration
You can configure the agent through the .env file:

OPENAI_API_KEY: Your OpenAI API key
OPENAI_MODEL: The model to use (default: "o3-mini")
MAX_ITERATIONS: Maximum number of iterations (default: 5)

## How It Works

1. The Logic Extractor module first preprocesses the contract to identify:
    - The overall token flow
    - Variables that affect token amounts
    - Dependencies that the token flow relies on
2. The analysis proceeds through multiple iterations:
    - Iteration 0: Analyzes only the direct token transfer flow
    - Iteration 1: Adds high-risk variables and dependencies
    - Iteration 2: Adds medium-risk variables and dependencies
    - Later iterations: Considers all variables and dependencies
3. For each iteration, the Action Generator proposes possible vulnerabilities, which the Reflection module evaluates.
4. The process continues until either:
    - A legitimate vulnerability is found
    - The maximum number of iterations is reached

## Example Output

The analysis generates comprehensive output files:

- `preprocessing_results.json`: Initial analysis of the contract
- `iterations/iteration_X/`: Results for each iteration
- `final/final_report.json`: Comprehensive final report
- `final/final_report_summary.txt`: Human-readable summary

## Extending the System

The modular architecture makes it easy to extend the system:

- To change the analysis logic, modify the `logic_extractor.py` file
- To change how attack scenarios are generated, modify `action_generator.py`
- To change the evaluation criteria, modify `reflection.py`