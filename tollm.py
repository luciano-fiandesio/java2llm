import jpype
import jpype.imports  # Enables automatic class importing
import argparse
from pathlib import Path
import sys
import graphviz

DEBUG = False

def dprint(*args, **kwargs):
    """Debug print function that only prints if DEBUG is True"""
    if DEBUG:
        print(*args, **kwargs)

# Find JavaParser JAR in script's directory
script_dir = Path(__file__).parent
jar_files = list(script_dir.glob("*.jar"))
if not jar_files:
    print("Error: No JAR file found in script directory", file=sys.stderr)
    sys.exit(1)
if len(jar_files) > 1:
    print("Error: Multiple JAR files found in script directory. Please keep only one JAR file.", file=sys.stderr)
    sys.exit(1)
javaparser_path = str(jar_files[0])

# Start the JVM with the JavaParser JAR in the classpath
jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", f"-Djava.class.path={javaparser_path}")
from com.github.javaparser import StaticJavaParser

def parse_java_file(file_path):
    """Parse a Java file and return its compilation unit."""
    path = Path(file_path)
    
    if not path.exists():
        print(f"Error: File {file_path} does not exist", file=sys.stderr)
        return None
    
    if not path.suffix == '.java':
        print(f"Error: File {file_path} is not a Java file", file=sys.stderr)
        return None
        
    try:
        # Read file content first and parse from string to handle encoding issues
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Configure parser for Java 16 to support Record Declarations and Text Block Literals
        parser_configuration = StaticJavaParser.getConfiguration()
        parser_configuration.setLanguageLevel(jpype.JClass("com.github.javaparser.ParserConfiguration$LanguageLevel").JAVA_16)
        compilation_unit = StaticJavaParser.parse(content)
        return compilation_unit
    except Exception as e:
        print(f"Error parsing {file_path}: {str(e)}", file=sys.stderr)
        return None

def find_linked_classes(target_file, depth, root_dir, base_package):
    visited_files = set()  # Track files we've already processed
    visited_classes = set()  # Track all classes we've found
    files_to_inspect = [target_file]
    dprint(f"Starting analysis with file: {target_file}")
    dprint(f"Requested depth: {depth}")

    for level in range(depth):
        dprint(f"\n{'='*20} LEVEL {level + 1} {'='*20}")
        dprint(f"Files to inspect at this level: {len(files_to_inspect)}")
        for f in files_to_inspect:
            dprint(f"  - {f}")
            
        next_level_files = []
        for file in files_to_inspect:
            if file in visited_files:
                dprint(f"  Skipping already visited file: {file}")
                continue
            visited_files.add(file)
            
            dprint(f"\n  Processing: {file}")
            cu = parse_java_file(file)
            if cu is None:
                dprint("    Failed to parse file")
                continue
                
            linked_classes = extract_linked_classes(cu, base_package)
            dprint(f"    Found classes: {linked_classes}")
            dprint(f"    Already visited classes: {visited_classes}")
            
            # Only process classes we haven't seen before
            new_classes = linked_classes - visited_classes
            dprint(f"    New classes to process: {new_classes}")
            visited_classes.update(new_classes)
            
            if new_classes:
                found_paths = find_class_paths(new_classes, root_dir)
                dprint(f"    Found file paths: {found_paths}")
                next_level_files.extend(found_paths)
                
        files_to_inspect = list(set(next_level_files))  # Remove duplicates
        dprint(f"\nLevel {level + 1} summary:")
        dprint(f"  Processed files: {len(visited_files)}")
        dprint(f"  Total classes found: {len(visited_classes)}")
        dprint(f"  Files for next level: {len(files_to_inspect)}")
        
        if not files_to_inspect:
            dprint("\nNo more files to process - stopping early")
            break

    dprint("\nFinal summary:")
    dprint(f"Total files processed: {len(visited_files)}")
    dprint(f"Total classes found: {len(visited_classes)}")
    return visited_classes

def extract_linked_classes(compilation_unit, base_package):
    linked_classes = set()
    
    # Get package name for resolving same-package references
    package_name = str(compilation_unit.getPackageDeclaration().get().getName()) if compilation_unit.getPackageDeclaration().isPresent() else ""
    
    # Process imports
    for import_decl in compilation_unit.getImports():
        # Convert Java String to Python string before checking
        if import_decl.isStatic():
            # For static imports, get the class name by removing the last part
            full_name = str(import_decl.getName().asString())
            class_name_str = '.'.join(full_name.split('.')[:-1])
        else:
            class_name_str = str(import_decl.getName().asString())
            
        if not class_name_str.startswith('java.') and class_name_str.startswith(base_package):
            linked_classes.add(class_name_str)
    
    # Process class declarations to find extends and implements
    for type_decl in compilation_unit.getTypes():
        # Handle extended class
        if type_decl.getExtendedTypes().isNonEmpty():
            for extended_type in type_decl.getExtendedTypes():
                class_name = str(extended_type.asString())
                # If it's a simple class name (no package), assume it's in the same package
                if '.' not in class_name:
                    full_class_name = f"{package_name}.{class_name}"
                    if full_class_name.startswith(base_package):
                        linked_classes.add(full_class_name)
                elif class_name.startswith(base_package):
                    linked_classes.add(class_name)
        
        # Handle implemented interfaces
        if type_decl.getImplementedTypes().isNonEmpty():
            for implemented_type in type_decl.getImplementedTypes():
                class_name = str(implemented_type.asString())
                # If it's a simple class name (no package), assume it's in the same package
                if '.' not in class_name:
                    full_class_name = f"{package_name}.{class_name}"
                    if full_class_name.startswith(base_package):
                        linked_classes.add(full_class_name)
                elif class_name.startswith(base_package):
                    linked_classes.add(class_name)
    
    return linked_classes

def load_cache(root_dir):
    """Load the class path cache from .java2llm file."""
    cache_file = Path(root_dir) / '.java2llm'
    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                for line in f:
                    if '=' in line:
                        class_name, path = line.strip().split('=', 1)
                        if Path(path).exists():  # Only cache valid paths
                            cache[class_name] = path
        except Exception as e:
            dprint(f"Warning: Error reading cache file: {e}", file=sys.stderr)
    return cache

def save_cache(cache, root_dir):
    """Save the class path cache to .java2llm file."""
    cache_file = Path(root_dir) / '.java2llm'
    try:
        with open(cache_file, 'w') as f:
            for class_name, path in sorted(cache.items()):
                f.write(f"{class_name}={path}\n")
    except Exception as e:
        dprint(f"Warning: Error writing cache file: {e}", file=sys.stderr)

def find_class_paths(class_names, root_dir):
    """Convert fully qualified class names to potential file paths using cache."""
    paths = []
    root_dir = Path(root_dir)
    cache = load_cache(root_dir)
    updated = False
    
    for class_name in class_names:
        # Check cache first
        if class_name in cache:
            cached_path = cache[class_name]
            if Path(cached_path).exists():
                paths.append(cached_path)
                dprint(f"  Found {class_name} in cache: {cached_path}")
                continue
            else:
                # Remove invalid cache entry
                del cache[class_name]
                updated = True
        
        # Convert Java String to Python string and handle path conversion
        file_path = str(class_name).replace('.', '/') + '.java'
        
        # Walk through the root directory to find all possible Java source directories
        java_dirs = []
        for path in root_dir.rglob('**/src/main/java'):
            if path.is_dir():
                java_dirs.append(path)
        
        # Also add src directories and root itself
        java_dirs.extend([p for p in root_dir.rglob('**/src') if p.is_dir()])
        java_dirs.append(root_dir)
        
        dprint(f"  Checking paths for {class_name}:")
        found = False
        for base_dir in java_dirs:
            potential_path = base_dir / file_path
            dprint(f"    - {potential_path} {'(exists)' if potential_path.exists() else '(not found)'}")
            if potential_path.exists():
                path_str = str(potential_path)
                paths.append(path_str)
                # Update cache
                cache[class_name] = path_str
                updated = True
                found = True
                break
                
        if not found:
            dprint(f"    Warning: Could not find {class_name} in any source directory")
    
    if updated:
        save_cache(cache, root_dir)
            
    return paths

def generate_dependency_graph(target_file, root_dir, base_package, depth, output_file):
    """Generate a graphviz visualization of class dependencies with proper depth levels.
    
    Args:
        target_file: The main file being analyzed
        root_dir: Project root directory
        base_package: Base package to filter dependencies
        depth: Maximum depth to analyze
    """
    dot = graphviz.Digraph(comment='Class Dependencies')
    dot.attr(rankdir='LR')  # Left to right layout
    
    # Track dependencies at each level
    dependencies = {}  # {level: {source: [targets]}}
    visited = set()
    
    def analyze_file(file_path, current_depth=0):
        if current_depth >= depth or file_path in visited:
            return
        
        visited.add(file_path)
        cu = parse_java_file(file_path)
        if cu is None:
            return
            
        source_class = Path(file_path).stem
        if current_depth == 0:
            dot.node(source_class, source_class, shape='box', style='filled', fillcolor='lightblue')
        else:
            dot.node(source_class, source_class)
            
        linked_classes = extract_linked_classes(cu, base_package)
        class_paths = find_class_paths(linked_classes, root_dir)
        
        if current_depth not in dependencies:
            dependencies[current_depth] = {}
        dependencies[current_depth][source_class] = []
        
        for dep_path in class_paths:
            dep_class = Path(dep_path).stem
            dependencies[current_depth][source_class].append(dep_class)
            dot.node(dep_class, dep_class)
            # Add edge from current file to its direct dependency
            dot.edge(source_class, dep_class)
            # Recursively analyze the dependency
            analyze_file(dep_path, current_depth + 1)
    
    # Start analysis from target file
    analyze_file(target_file)
    
    # Save the graph
    dot.render(output_file, format='png', cleanup=True)

def write_linked_files(linked_files, output_file, format='txt'):
    """Write the content of linked Java files to a file in the specified format.
    
    Args:
        linked_files: List of file paths to process
        output_file: Output file path
        format: Output format ('txt', 'md', or 'json')
    """
    if format == 'json':
        import json
        result = {}
        for file_path in linked_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    package_index = content.find("package ")
                    if package_index != -1:
                        content = content[package_index:]
                    result[file_path] = content
            except Exception as e:
                print(f"Error reading file {file_path}: {str(e)}", file=sys.stderr)
        
        with open(output_file, 'w') as out:
            json.dump(result, out, indent=2)
            
    elif format == 'md':
        with open(output_file, 'w') as out:
            for file_path in linked_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        package_index = content.find("package ")
                        if package_index != -1:
                            content = content[package_index:]
                        
                        out.write(f"## {file_path}\n\n")
                        out.write("```java\n")
                        out.write(content)
                        out.write("\n```\n\n")
                        out.write("---\n\n")
                except Exception as e:
                    print(f"Error reading file {file_path}: {str(e)}", file=sys.stderr)
    else:  # Default txt format
        with open(output_file, 'w') as out:
            for file_path in linked_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        # Find the package declaration
                        package_index = content.find("package ")
                        if package_index != -1:
                            # Keep only the content from package declaration onwards
                            content = content[package_index:]
                        
                        out.write(f"// File: {file_path}\n")
                        out.write("=" * 80 + "\n")
                        out.write(content)
                        out.write("\n" + "=" * 80 + "\n\n")
                except Exception as e:
                    print(f"Error reading file {file_path}: {str(e)}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Analyze a Java class and dump linked classes.")
    parser.add_argument('--file', required=True, help='Path to the target Java class file.')
    parser.add_argument('--root', required=True, help='Path to the root project folder.')
    parser.add_argument('--base_package', required=True, help='Base package to filter classes (e.g., com.aider)')
    parser.add_argument('--depth', type=int, default=1, help='Depth of classes to fetch.')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--format', choices=['txt', 'md', 'json'], default='txt',
                      help='Output format (txt, md, or json)')
    parser.add_argument('--graph', action='store_true',
                      help='Generate a dependency graph visualization')
    
    args = parser.parse_args()
    global DEBUG
    DEBUG = args.debug
    target_java_class = args.file
    depth = args.depth
    
    try:
        linked_classes = find_linked_classes(target_java_class, depth, args.root, args.base_package)
        # Set output filename based on format
        output_file = f"linked_classes.{args.format}"
        # Convert class names to actual file paths and write their content
        linked_files = set(find_class_paths(linked_classes, args.root))
        # Add the target class as the first file
        linked_files = [target_java_class] + list(linked_files)
        write_linked_files(linked_files, output_file, args.format)
        
        if args.graph:
            graph_output = "class_dependencies"
            generate_dependency_graph(target_java_class, args.root, args.base_package, depth, graph_output)
            print(f"Generated dependency graph: {graph_output}.png")
        
        print(f"Successfully analyzed {target_java_class} and wrote linked classes to {output_file}")
    finally:
        # Shutdown the JVM
        jpype.shutdownJVM()

if __name__ == '__main__':
    main()
