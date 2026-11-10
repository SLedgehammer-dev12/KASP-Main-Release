#!/usr/bin/env python3
"""
Graphify - Deterministic Codebase Knowledge Graph & Impact Analyzer for KASP.
Extracts AST symbols, import dependencies, function call graphs, database schemas,
and test-to-source mappings locally without external APIs or vector databases.
"""

import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
CACHE_DIR = WORKSPACE_ROOT / ".graphify"
GRAPH_FILE = CACHE_DIR / "graph.json"

class CodebaseGraphBuilder:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.nodes = {}  # id -> {type, path, name, doc, line}
        self.edges = []  # [{source, target, relation}]
        self.file_to_symbols = defaultdict(list)
        self.symbol_to_file = {}
        self.call_graph = defaultdict(set)
        self.import_graph = defaultdict(set)
        self.table_usages = defaultdict(set)  # table -> files/symbols
        self.test_mappings = defaultdict(set) # source_module -> test_files

    def should_skip(self, path: Path) -> bool:
        parts = path.parts
        skip_dirs = {
            ".git", ".opencode", ".pytest_cache", "__pycache__", "build", "dist",
            ".jdk", "releases", "scratch", ".graphify"
        }
        return any(d in parts for d in skip_dirs)

    def scan_files(self):
        for ext in ("*.py",):
            for file_path in self.root_dir.rglob(ext):
                if not self.should_skip(file_path):
                    self.parse_python_file(file_path)

        self._map_tests_to_sources()
        self._detect_sql_tables()

    def parse_python_file(self, file_path: Path):
        rel_path = str(file_path.relative_to(self.root_dir))
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=rel_path)
        except Exception:
            return

        file_node_id = f"file:{rel_path}"
        self.nodes[file_node_id] = {
            "type": "file",
            "name": rel_path,
            "path": rel_path
        }

        # AST Walker
        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.edges.append({
                        "source": file_node_id,
                        "target": f"module:{alias.name}",
                        "relation": "imports"
                    })
                    self.import_graph[rel_path].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.edges.append({
                    "source": file_node_id,
                    "target": f"module:{module}",
                    "relation": "imports_from"
                })
                self.import_graph[rel_path].add(module)

            # Class definitions
            elif isinstance(node, ast.ClassDef):
                class_id = f"class:{rel_path}:{node.name}"
                self.nodes[class_id] = {
                    "type": "class",
                    "name": node.name,
                    "path": rel_path,
                    "line": node.lineno
                }
                self.edges.append({
                    "source": file_node_id,
                    "target": class_id,
                    "relation": "defines_class"
                })
                self.file_to_symbols[rel_path].append(node.name)
                self.symbol_to_file[node.name] = rel_path

            # Function definitions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_id = f"function:{rel_path}:{node.name}"
                self.nodes[fn_id] = {
                    "type": "function",
                    "name": node.name,
                    "path": rel_path,
                    "line": node.lineno
                }
                self.edges.append({
                    "source": file_node_id,
                    "target": fn_id,
                    "relation": "defines_function"
                })
                self.file_to_symbols[rel_path].append(node.name)
                self.symbol_to_file[node.name] = rel_path

                # Call resolution inside function
                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.Call):
                        target_name = None
                        if isinstance(sub_node.func, ast.Name):
                            target_name = sub_node.func.id
                        elif isinstance(sub_node.func, ast.Attribute):
                            target_name = sub_node.func.attr

                        if target_name:
                            self.call_graph[target_name].add(f"{rel_path}:{node.name}")
                            self.edges.append({
                                "source": fn_id,
                                "target": f"call:{target_name}",
                                "relation": "calls"
                            })

    def _detect_sql_tables(self):
        # Look for SQL queries or CREATE TABLE statements
        db_file = self.root_dir / "kasp" / "data" / "database.py"
        if not db_file.exists():
            return

        try:
            content = db_file.read_text(encoding="utf-8", errors="replace")
            # Find CREATE TABLE
            tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)", content, re.IGNORECASE)
            for table in set(tables):
                table_id = f"table:{table}"
                self.nodes[table_id] = {
                    "type": "db_table",
                    "name": table,
                    "path": "kasp/data/database.py"
                }

            # Map table references across files
            for rel_path, symbols in self.file_to_symbols.items():
                if rel_path.startswith("kasp/"):
                    full_p = self.root_dir / rel_path
                    if full_p.exists():
                        txt = full_p.read_text(encoding="utf-8", errors="replace")
                        for table in tables:
                            if re.search(r"\b" + re.escape(table) + r"\b", txt, re.IGNORECASE):
                                self.table_usages[table].add(rel_path)
                                self.edges.append({
                                    "source": f"file:{rel_path}",
                                    "target": f"table:{table}",
                                    "relation": "queries_table"
                                })
        except Exception:
            pass

    def _map_tests_to_sources(self):
        # Map test_*.py files to modules in kasp/
        test_files = [f for f in self.file_to_symbols.keys() if Path(f).name.startswith("test_")]
        for tf in test_files:
            content = (self.root_dir / tf).read_text(encoding="utf-8", errors="replace")
            for rel_path in self.file_to_symbols.keys():
                if rel_path.startswith("kasp/"):
                    mod_name = Path(rel_path).stem
                    mod_import = rel_path.replace("/", ".").replace(".py", "")
                    if mod_name in content or mod_import in content:
                        self.test_mappings[rel_path].add(tf)
                        self.edges.append({
                            "source": f"file:{tf}",
                            "target": f"file:{rel_path}",
                            "relation": "tests"
                        })

    def export_graph(self) -> dict:
        return {
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_files": len([n for n in self.nodes.values() if n["type"] == "file"]),
                "total_symbols": len([n for n in self.nodes.values() if n["type"] in ("class", "function")]),
                "total_tables": len([n for n in self.nodes.values() if n["type"] == "db_table"])
            },
            "nodes": self.nodes,
            "edges": self.edges,
            "call_graph": {k: sorted(list(v)) for k, v in self.call_graph.items()},
            "table_usages": {k: sorted(list(v)) for k, v in self.table_usages.items()},
            "test_mappings": {k: sorted(list(v)) for k, v in self.test_mappings.items()}
        }

    def save(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = self.export_graph()
        with open(GRAPH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Graphify] Knowledge graph saved: {GRAPH_FILE} ({data['summary']['total_nodes']} nodes, {data['summary']['total_edges']} edges)")

def load_graph() -> dict:
    if not GRAPH_FILE.exists():
        builder = CodebaseGraphBuilder(WORKSPACE_ROOT)
        builder.scan_files()
        builder.save()
    with open(GRAPH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def cmd_build():
    builder = CodebaseGraphBuilder(WORKSPACE_ROOT)
    builder.scan_files()
    builder.save()

def cmd_impact(target: str):
    graph = load_graph()
    target_clean = target.strip()
    print(f"\n🔍 [Graphify Impact Analysis] for: '{target_clean}'")
    print("=" * 60)

    # If it's a file path
    matched_file = None
    for file_id, node in graph["nodes"].items():
        if node["type"] == "file" and (target_clean in node["path"] or target_clean == node["name"]):
            matched_file = node["path"]
            break

    if matched_file:
        print(f"📁 Target File: {matched_file}")
        # Tests that verify this file
        tests = graph["test_mappings"].get(matched_file, [])
        print(f"\n🧪 Linked Test Suites ({len(tests)} found):")
        if tests:
            for t in tests:
                print(f"  • {t}")
        else:
            print("  ⚠️  No direct test file linked! (Recommend writing a new test)")

        # Downstream importers
        importers = []
        for edge in graph["edges"]:
            if edge["relation"] in ("imports", "imports_from"):
                tgt = edge["target"].replace("module:", "").replace(".", "/")
                if tgt and (tgt in matched_file or matched_file.startswith(tgt)):
                    importers.append(edge["source"].replace("file:", ""))

        importers = sorted(list(set(importers)))
        print(f"\n🔗 Downstream Consumers / Importers ({len(importers)} files):")
        for imp in importers[:15]:
            print(f"  • {imp}")
        if len(importers) > 15:
            print(f"  ... and {len(importers) - 15} more.")
        return

    # Check symbol callers
    callers = graph["call_graph"].get(target_clean, [])
    if callers:
        print(f"⚡ Function/Symbol Callers ({len(callers)} call sites):")
        for c in callers:
            print(f"  • {c}")
    else:
        print(f"ℹ️ No direct callers found for symbol '{target_clean}' in call graph.")

    # Table usages
    if target_clean in graph["table_usages"]:
        print(f"\n🗄️ Database Table Usages for '{target_clean}':")
        for u in graph["table_usages"][target_clean]:
            print(f"  • {u}")

def cmd_callers(symbol: str):
    graph = load_graph()
    callers = graph["call_graph"].get(symbol.strip(), [])
    print(f"\n📞 [Graphify Callers] for symbol: '{symbol}'")
    print("=" * 60)
    if callers:
        for c in callers:
            print(f"  • {c}")
    else:
        print(f"No callers found for '{symbol}'.")

def cmd_stats():
    graph = load_graph()
    summary = graph["summary"]
    print("\n📊 [Graphify Codebase Knowledge Graph Statistics]")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  • {k.replace('_', ' ').capitalize()}: {v}")
    print(f"\nIndexed database tables: {len(graph['table_usages'])}")
    for tbl in sorted(graph["table_usages"].keys()):
        print(f"  - {tbl} (used in {len(graph['table_usages'][tbl])} modules)")

def cmd_test_map(mod_name: str):
    graph = load_graph()
    matches = {k: v for k, v in graph["test_mappings"].items() if mod_name in k}
    print(f"\n🧪 [Graphify Test Mapping] for '{mod_name}':")
    print("=" * 60)
    if not matches:
        print(f"No test mapping found for '{mod_name}'.")
    for mod, tests in matches.items():
        print(f"\nSource: {mod}")
        for t in tests:
            print(f"  • {t}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 graphify.py build")
        print("  python3 graphify.py impact <symbol_or_filepath>")
        print("  python3 graphify.py callers <symbol>")
        print("  python3 graphify.py stats")
        print("  python3 graphify.py test-map <module_name>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "build":
        cmd_build()
    elif cmd == "impact" and len(sys.argv) > 2:
        cmd_impact(sys.argv[2])
    elif cmd == "callers" and len(sys.argv) > 2:
        cmd_callers(sys.argv[2])
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "test-map" and len(sys.argv) > 2:
        cmd_test_map(sys.argv[2])
    else:
        print(f"Unknown or incomplete command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
