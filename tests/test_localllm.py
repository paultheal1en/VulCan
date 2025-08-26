import requests

url = "https://4b8cd3e82dfa.ngrok-free.app" + "/chat"
payload = {"message": "Viết hàm tính số nguyên tố bằng C++"}
r = requests.post(url, json=payload)
print(r.json())
