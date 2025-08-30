import inspect
import strands_tools
from strands_tools.swarm import swarm as original_swarm

print("--- TRUY TÌM NGUỒN GỐC MODULE ---")

print("\n[Bước 1: Vị trí của module 'strands_tools']")
try:
    # __file__ trỏ đến file __init__.py của package
    module_path = inspect.getfile(strands_tools)
    print(f"Module 'strands_tools' được import từ file: {module_path}")
except Exception as e:
    print(f"Không thể xác định file của module: {e}")

print("\n[Bước 2: Signature của hàm 'swarm' đang được sử dụng]")
print(f"Function Signature: {inspect.signature(original_swarm)}")

print("\n---------------------------------")