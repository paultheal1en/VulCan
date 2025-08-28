#!/usr/bin/env python3
"""
Script để phân tích và refactor dependencies trong pyproject.toml
Tìm ra những dependencies nào được sử dụng và không được sử dụng
"""

import ast
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DependencyAnalyzer:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.python_files = []
        self.imports_found = set()
        self.dependency_mapping = {}

    def scan_python_files(self) -> List[Path]:
        """Quét tất cả file Python trong project"""
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Bỏ qua các thư mục không cần thiết
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ["__pycache__", "node_modules", "venv", "env"]
            ]

            for file in files:
                if file.endswith(".py"):
                    python_files.append(Path(root) / file)

        self.python_files = python_files
        return python_files

    def extract_imports_from_file(self, file_path: Path) -> Set[str]:
        """Trích xuất tất cả imports từ một file Python"""
        imports = set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split(".")[0])

            # Tìm dynamic imports
            dynamic_imports = re.findall(r'__import__\([\'"]([^\'\"]+)[\'"]', content)
            for imp in dynamic_imports:
                imports.add(imp.split(".")[0])

            # Tìm importlib imports
            importlib_imports = re.findall(
                r'importlib\.import_module\([\'"]([^\'\"]+)[\'"]', content
            )
            for imp in importlib_imports:
                imports.add(imp.split(".")[0])

        except Exception as e:
            print(f"Lỗi khi phân tích {file_path}: {e}")

        return imports

    def extract_all_imports(self) -> Set[str]:
        """Trích xuất tất cả imports từ toàn bộ project"""
        all_imports = set()

        for file_path in self.python_files:
            file_imports = self.extract_imports_from_file(file_path)
            all_imports.update(file_imports)

        self.imports_found = all_imports
        return all_imports

    def create_dependency_mapping(self) -> Dict[str, List[str]]:
        """Tạo mapping giữa package name và import name"""
        mapping = {
            # Core frameworks
            "strands-agents": ["strands_agents", "strands"],
            "strands-agents-tools": ["strands_agents_tools"],
            # Document & PDF
            "PyPDF2": ["PyPDF2"],
            "pdfplumber": ["pdfplumber"],
            "tqdm": ["tqdm"],
            "chardet": ["chardet"],
            # Memory Systems
            "litellm": ["litellm"],
            "mistralai": ["mistralai", "mistral"],
            "mem0ai": ["mem0", "mem0ai"],
            "faiss-cpu": ["faiss"],
            "pymilvus": ["pymilvus"],
            "langchain": ["langchain"],
            "langchain-community": ["langchain_community"],
            "langchain-core": ["langchain_core"],
            "langchain-huggingface": ["langchain_huggingface"],
            "langchain-milvus": ["langchain_milvus"],
            "langchain-openai": ["langchain_openai"],
            "langchain-text-splitters": ["langchain_text_splitters"],
            "sentence-transformers": ["sentence_transformers"],
            "langchain_mistralai": ["langchain_mistralai"],
            # Database
            "SQLAlchemy": ["sqlalchemy"],
            "PyMySQL": ["pymysql"],
            # API & Web
            "fastapi": ["fastapi"],
            "uvicorn": ["uvicorn"],
            "streamlit": ["streamlit"],
            "streamlit-antd-components": ["streamlit_antd_components"],
            "streamlit-aggrid": ["st_aggrid"],
            # Utilities
            "pydantic": ["pydantic"],
            "pydantic-settings": ["pydantic_settings"],
            "boto3": ["boto3"],
            "botocore": ["botocore"],
            "ollama": ["ollama"],
            "requests": ["requests"],
            "httpx": ["httpx"],
            "click": ["click"],
            "rich": ["rich"],
            "paramiko": ["paramiko"],
            "ruamel.yaml": ["ruamel"],
            "loguru": ["loguru"],
            "tenacity": ["tenacity"],
            "python-docx": ["docx"],
            "python-pptx": ["pptx"],
            "PyMuPDF": ["fitz"],
            "opencv-python": ["cv2"],
            "unstructured": ["unstructured"],
            "rapidocr-onnxruntime": ["rapidocr_onnxruntime"],
            "strenum": ["strenum"],
            "memoization": ["memoization"],
            "opensearch-py": ["opensearchpy", "opensearch"],
        }

        self.dependency_mapping = mapping
        return mapping

    def analyze_usage(self) -> Tuple[List[str], List[str]]:
        """Phân tích dependencies nào được sử dụng và không được sử dụng"""
        used_packages = []
        unused_packages = []

        for package, import_names in self.dependency_mapping.items():
            is_used = False
            for import_name in import_names:
                if import_name in self.imports_found:
                    is_used = True
                    break

            if is_used:
                used_packages.append(package)
            else:
                unused_packages.append(package)

        return used_packages, unused_packages

    def generate_requirements_txt(self, used_packages: List[str]) -> str:
        """Tạo requirements.txt chỉ với packages được sử dụng"""
        requirements = []
        for package in used_packages:
            # Giữ nguyên version constraints nếu có
            if package == "strands-agents":
                requirements.append("strands-agents[ollama,mistral]>=1.0.0")
            elif package == "strands-agents-tools":
                requirements.append("strands-agents-tools==0.2.0")
            elif package == "mem0ai":
                requirements.append("mem0ai==0.1.110")
            elif package == "uvicorn":
                requirements.append("uvicorn[standard]")
            elif package == "ollama":
                requirements.append("ollama>=0.1.0")
            else:
                requirements.append(package)

        return "\n".join(sorted(requirements))

    def run_analysis(self) -> Dict:
        """Chạy toàn bộ quá trình phân tích"""
        print("🔍 Đang quét các file Python...")
        python_files = self.scan_python_files()
        print(f"   Tìm thấy {len(python_files)} file Python")

        print("\n📦 Đang trích xuất imports...")
        imports = self.extract_all_imports()
        print(f"   Tìm thấy {len(imports)} import khác nhau")

        print("\n🗺️  Đang tạo dependency mapping...")
        self.create_dependency_mapping()

        print("\n📊 Đang phân tích usage...")
        used_packages, unused_packages = self.analyze_usage()

        # Tìm imports không có trong dependency mapping
        all_mapped_imports = set()
        for import_names in self.dependency_mapping.values():
            all_mapped_imports.update(import_names)

        unmapped_imports = (
            imports - all_mapped_imports - {"vulcan"}
        )  # Bỏ qua local package

        return {
            "python_files": python_files,
            "all_imports": imports,
            "used_packages": used_packages,
            "unused_packages": unused_packages,
            "unmapped_imports": unmapped_imports,
            "requirements_txt": self.generate_requirements_txt(used_packages),
        }


def main():
    """Main function"""
    analyzer = DependencyAnalyzer()
    results = analyzer.run_analysis()

    print("\n" + "=" * 60)
    print("📋 KẾT QUẢ PHÂN TÍCH DEPENDENCIES")
    print("=" * 60)

    print(f"\n✅ PACKAGES ĐƯỢC SỬ DỤNG ({len(results['used_packages'])}):")
    for package in sorted(results["used_packages"]):
        print(f"   • {package}")

    print(f"\n❌ PACKAGES KHÔNG ĐƯỢC SỬ DỤNG ({len(results['unused_packages'])}):")
    for package in sorted(results["unused_packages"]):
        print(f"   • {package}")

    if results["unmapped_imports"]:
        print(f"\n⚠️  IMPORTS KHÔNG XÁC ĐỊNH ({len(results['unmapped_imports'])}):")
        for imp in sorted(results["unmapped_imports"]):
            print(f"   • {imp}")

    print(f"\n💾 REQUIREMENTS.TXT ĐỀ XUẤT:")
    print("-" * 40)
    print(results["requirements_txt"])

    # Tính toán tiết kiệm
    total_deps = len(results["used_packages"]) + len(results["unused_packages"])
    saved_percentage = (
        (len(results["unused_packages"]) / total_deps) * 100 if total_deps > 0 else 0
    )

    print(f"\n📈 THỐNG KÊ:")
    print(f"   • Tổng packages: {total_deps}")
    print(f"   • Được sử dụng: {len(results['used_packages'])}")
    print(f"   • Không sử dụng: {len(results['unused_packages'])}")
    print(f"   • Tiết kiệm: {saved_percentage:.1f}%")


if __name__ == "__main__":
    main()
