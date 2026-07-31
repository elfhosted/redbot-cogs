import ast
import re
import unittest
from pathlib import Path
from typing import Any


METHODS = {
    "_normalize_username",
    "_strip_code_fences",
    "_table_lines_from_output",
    "_compact_k8s_workload_name",
    "_code_block",
    "_code_blocks",
    "_tenant_node_from_pods",
    "_compact_pods_table",
    "_compact_pod_usage_table",
    "_split_discord",
}


def load_subject_class():
    source_path = Path(__file__).resolve().parent / "elrondradar" / "elrondradar.py"
    tree = ast.parse(source_path.read_text())
    module_body = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            names = []
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.append(target.id)
            elif isinstance(node.target, ast.Name):
                names.append(node.target.id)
            if any(name in {"USERNAME_RE", "USERNAME_STOPWORDS"} for name in names):
                module_body.append(node)
        if isinstance(node, ast.ClassDef) and node.name == "ElrondRadar":
            methods = [item for item in node.body if isinstance(item, ast.FunctionDef) and item.name in METHODS]
            module_body.append(ast.ClassDef(name="Subject", bases=[], keywords=[], body=methods, decorator_list=[]))
            break
    test_module = ast.Module(body=module_body, type_ignores=[])
    ast.fix_missing_locations(test_module)
    ns = {"re": re, "Any": Any, "Optional": Any, "Tuple": tuple}
    exec(compile(test_module, str(source_path), "exec"), ns)
    return ns["Subject"]


class ElrondRadarFormattingTests(unittest.TestCase):
    def setUp(self):
        self.subject = load_subject_class()()

    def test_compacts_usage_from_decorated_or_fenced_output(self):
        raw = """📊 **Pod Usage**
_Tenant-supplied diagnostic data._
```text
POD                                      CONTAINER  CPU(cores)   MEMORY(bytes)
demo-radarr-7g8h9j0klm-ab12c            radarr       12m          512Mi
demo-radarr-exporter-7g8h9j0klm-cd34e   exporter      1m           32Mi
```"""
        formatted = self.subject._compact_pod_usage_table(raw, "demo")

        self.assertIn("APP", formatted)
        self.assertIn("CONTAINER", formatted)
        self.assertIn("radarr", formatted)
        self.assertIn("radarr-exporter", formatted)
        self.assertNotIn("7g8h9j0klm", formatted)
        self.assertNotIn("demo-", formatted)

    def test_preserves_legitimate_long_workload_suffixes(self):
        self.assertEqual(
            self.subject._compact_k8s_workload_name("media-configurator-abcdefgh-abcde", ""),
            "media-configurator-abcdefgh-abcde",
        )

    def test_compacts_pod_table_and_still_extracts_node_with_intro_text(self):
        raw = """📋 **Pods**
```text
APP     POD                                READY  STATUS   RESTARTS  AGE  NODE       IMAGE
radarr  radarr-7g8h9j0klm-ab12c            1/1    Running  0         2h   node-one   v5.27.5
plex    plex-very-long-name-8k9l0m1n2p-zz99q  1/1    Running  2         3d   node-two   v1
```"""
        formatted = self.subject._compact_pods_table(raw)
        node = self.subject._tenant_node_from_pods(raw)

        self.assertIn("APP", formatted)
        self.assertIn("POD", formatted)
        self.assertIn("radarr", formatted)
        self.assertIn("plex-very-long-name", formatted)
        self.assertNotIn("7g8h9j0klm", formatted)
        self.assertEqual(node, "node-one, node-two")

    def test_code_sections_fit_splitter_without_breaking_fences_or_dropping_rows(self):
        usage_rows = "\n".join(f"app-{index}  container  {index}m  {index}Mi" for index in range(80))
        pods_rows = "\n".join(f"app-{index}  pod-{index}  1/1  Running  0  1h" for index in range(80))
        usage_section = "\n".join(["📊 **Pod Usage**", *self.subject._code_blocks(usage_rows, 1050)])
        pods_section = "\n".join(["📋 **Pods**", *self.subject._code_blocks(pods_rows, 1050)])
        chunks = self.subject._split_discord("intro\n\n" + usage_section + "\n\n" + pods_section)
        joined = "\n".join(chunks)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertIn("app-0  container", joined)
        self.assertIn("app-79  container", joined)
        self.assertIn("app-0  pod-0", joined)
        self.assertIn("app-79  pod-79", joined)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1800)
            self.assertEqual(chunk.count("```") % 2, 0, chunk)


if __name__ == "__main__":
    unittest.main()
