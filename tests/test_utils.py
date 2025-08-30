from vulcan.utils.agent_utils import create_session_dir_name
import uuid

# Kịch bản 1: Tên bình thường
name1 = "My First Session!"
id1 = uuid.uuid4().hex
print(f"'{name1}' + '{id1[:8]}' ---> '{create_session_dir_name(name1, id1)}'")

# Kịch bản 2: Tên trống
name2 = ""
id2 = uuid.uuid4().hex
print(f"'{name2}' + '{id2[:8]}' ---> '{create_session_dir_name(name2, id2)}'")

# Kịch bản 3: Tên chỉ có ký tự đặc biệt
name3 = "!@#$%"
id3 = uuid.uuid4().hex
print(f"'{name3}' + '{id3[:8]}' ---> '{create_session_dir_name(name3, id3)}'")