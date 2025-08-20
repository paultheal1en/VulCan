
# VulCan - Autonomous Penetration Testing Agent

![Project Status](https://img.shields.io/badge/status-alpha-orange.svg)
![GitHub License](https://img.shields.io/github/license/mashape/apistatus.svg)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)

**VulCan là một agent kiểm thử xâm nhập tự trị, được trang bị khả năng lập luận siêu nhận thức (metacognitive reasoning) và quản lý trạng thái bền bỉ, được thiết kế để tự động hóa các quy trình tấn công an ninh mạng phức tạp.**

</div>

---

### ⚠️ TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM QUAN TRỌNG ⚠️

**PHẦN MỀM NÀY CHỈ DÀNH CHO MỤC ĐÍCH GIÁO DỤC VÀ KIỂM THỬ BẢO MẬT ĐƯỢC ỦY QUYỀN.**

-   **KHÔNG BAO GIỜ** sử dụng công cụ này trên các hệ thống mà bạn không có sự cho phép rõ ràng bằng văn bản.
-   Luôn triển khai trong một môi trường an toàn, được cô lập (sandboxed).
-   Người dùng hoàn toàn chịu trách nhiệm về việc sử dụng công cụ một cách hợp pháp và có đạo đức. Việc lạm dụng có thể dẫn đến hậu quả pháp lý nghiêm trọng.

---

### ✨ Tính năng nổi bật

*   🧠 **Lập luận siêu nhận thức:** Agent tự đánh giá độ tin cậy, lựa chọn chiến lược và thích ứng với các tình huống mới.
*   💾 **Trạng thái bền bỉ (Stateful):** Tích hợp sâu với cơ sở dữ liệu (MySQL) để lưu trữ **Sessions**, **Plans**, và **Tasks**. Cho phép tạm dừng và tiếp tục các nhiệm vụ phức tạp kéo dài.
*   🤖 **Lập kế hoạch tự động:** Tự động phân rã các nhiệm vụ cấp cao thành các kế hoạch hành động chi tiết, có thể thực thi được.
*   🛠️ **Kho vũ khí hiện đại:** Tích hợp các công cụ pentest hàng đầu như **Nuclei**, **Subfinder**, **httpx**, **ffuf**, và **sqlmap**.
*   🌐 **Hỗ trợ Dual-LLM:** Dễ dàng chuyển đổi giữa các mô hình **Remote** (Amazon Bedrock) để có sức mạnh tối đa và **Local** (Ollama) để đảm bảo quyền riêng tư và tiết kiệm chi phí.
*   🤝 **Giao diện dòng lệnh (CLI):** Giao diện mạnh mẽ và thân thiện với các lệnh `init` và `start` để quản lý.
*   📊 **Báo cáo tự động:** Tự động tạo báo cáo cuối cùng dựa trên các bằng chứng (`findings`) đã thu thập.
*   ⚙️ **Cấu hình linh hoạt:** Quản lý tất cả các thiết lập thông qua các file `.yaml` dễ đọc.

### 🚀 Demo hoạt động

Đây là một ví dụ về cách VulCan suy nghĩ và hành động trong một nhiệm vụ:

```sh
# Người dùng khởi động nhiệm vụ
$ python -m vulcan.cli start -m "Find web vulnerabilities on example.com"

# Output của VulCan
...
[+] Remote model initialized: anthropic.claude-3-sonnet...
Agent Core initialized successfully.
──────────────────────────────── Agent Execution Log ─────────────────────────────────

🤔 Agent Reasoning...
────────────────────────────────────────────────────────────────────────────────
   The mission is to find web vulnerabilities. The best modern workflow starts with comprehensive reconnaissance.
   I will begin by finding subdomains, then checking for live web servers, and finally running a broad vulnerability scan with Nuclei.
   Confidence in this initial plan is High (95%).
────────────────────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────────────────────
Step 1/100: shell
────────────────────────────────────────────────────────────────────────────────
↳ Running: subfinder -d example.com -silent | httpx -silent | nuclei -t vulnerabilities/

[INF] Found 3 subdomains
[INF] blog.example.com:443 [HTTPS, 200]
[INF] api.example.com:443 [HTTPS, 200]
[INF] [CVE-2021-44228] http-log4j-jndi-injection on https://api.example.com [high]
...

🤔 Agent Reasoning...
────────────────────────────────────────────────────────────────────────────────
   Nuclei has identified a potential Log4j vulnerability on api.example.com. This is a critical finding.
   I must now store this evidence and then attempt to verify and exploit this vulnerability using curl and netcat.
────────────────────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────────────────────
Step 2/100: mem0_memory
────────────────────────────────────────────────────────────────────────────────
↳ Storing [finding]: [CVE-2021-44228] Log4j vulnerability found on https://api.example.com
  Metadata: {'category': 'finding', 'severity': 'critical', 'confidence': '90%'}

...