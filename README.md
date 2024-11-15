# Java Dependencies Analyzer for LLM

This tool is designed to analyzes Java source files and dump the contents of the selected file and its dependencies into a single file, making it easier to use in Retrieval-Augmented Generation (RAG) systems or as part of prompts for Large Language Models (LLMs). By consolidating your codebase into one file, you can more easily pass context to an LLM or integrate it into a RAG pipeline.

## Features

- Analyzes Java source files to find class dependencies
- Follows imports up to a specified depth
- Filters dependencies by base package
- Caches file paths for better performance
- Removes license headers and comments before package declarations
- Supports static imports
- Debug mode for verbose output

## Prerequisites

- Python 3.x
- JPype1
- JavaParser 3.26.2 JAR file

## Installation

1. Install Python dependencies using the requirements.txt file:

```bash
pip install -r requirements.txt
```

This will install all required dependencies including:
- JPype1 for Java integration
- Graphviz for dependency visualization

Note that if you are on MacOS, you need to install Graphviz as well.

```bash
brew install graphviz
```

2. Download JavaParser JAR file and place it in the same directory as the script:
```bash
wget https://repo1.maven.org/maven2/com/github/javaparser/javaparser-core/3.26.2/javaparser-core-3.26.2.jar -O $(dirname $(which tollm.py))/javaparser-core-3.26.2.jar
```

The script will automatically find and use the JavaParser JAR file in its directory. Only one JAR file should be present in the script's directory.

## Usage

```bash
python tollm.py --file <java_file> --root <project_root> --base_package <base.package> [--depth <depth>] [--debug]
```

### Parameters

- `--file`: Path to the target Java source file to analyze
- `--root`: Path to the root directory of the Java project
- `--base_package`: Base package name to filter dependencies (e.g., com.example)
- `--depth`: (Optional) How many levels deep to follow dependencies (default: 1)
- `--format`: (Optional) Output format: txt, md, or json (default: txt)
- `--debug`: (Optional) Enable verbose debug output
- `--graph`: (Optional) Generate a visual dependency graph (requires Graphviz)

### Example

Basic usage:

```bash
python tollm.py --file src/main/java/com/example/MyClass.java --root /path/to/project --base_package com.example --depth 2

Generate with dependency graph:
```bash
python tollm.py --file src/main/java/com/example/MyClass.java --root /path/to/project --base_package com.example --graph
```


## Output

The script generates a file named `linked_classes.txt` (or with appropriate extension based on format) containing the target Java file and all its dependencies. The output format can be specified using the `--format` parameter:

### Output Formats

- **txt** (default):
  - Plain text format
  - Each file starts with `// File: filepath`
  - Files are separated by `=` character lines
  - Content starts from package declaration

- **md** (Markdown):
  - Each file under a level-2 heading with its path
  - Code blocks wrapped in ```java syntax highlighting
  - Files separated by horizontal rules
  - Content starts from package declaration

- **json**:
  - File paths as keys
  - File contents as values
  - Pretty-printed with 2-space indentation
  - Content starts from package declaration

## Caching

The script maintains a cache file `.java2llm` in the root directory to speed up subsequent runs. The cache maps fully qualified class names to their file paths.

## Error Handling

- Invalid file paths are reported
- Missing dependencies are logged (in debug mode)
- Invalid cache entries are automatically removed
- Encoding issues are handled gracefully

## License

Apache License 2.0
