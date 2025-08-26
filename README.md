


## Kiến trúc

VulCan hoạt động với một `Orchestrator` quản lý vòng đời của `Session`, và một `Agent` tự trị duy nhất thực hiện toàn bộ logic nghiệp vụ.

```mermaid
graph TD
    subgraph "Application Layer"
        A[User via CLI] --> B[Orchestrator];
        B -- Manages Session --> C[MySQL Database];
    end

    subgraph "Agent Cognitive Core"
        D[Autonomous Agent Instance];
        E[Metacognitive System Prompt];
        
        D -- Guided by --> E;
        D -- Interacts with --> F[Unified Memory (Mem0/FAISS)];
        D -- Uses --> G[Toolbelt];
    end
    
    B -- Initializes & Runs --> D;

    subgraph "Agent Resources"
        F -- Stores --> F1[Strategic Plans (JSON)];
        F -- Stores --> F2[Technical Findings (Text)];
        
        G -- Includes --> G1[Execution Tools (shell, swarm)];
        G -- Includes --> G2[Knowledge Tools (query_knowledge_base)];
    end
    
    H[Knowledge Base (Zilliz Cloud)]
    G2 --> H
```

---

## Hướng dẫn Cài đặt và Thiết lập

### 1. Yêu cầu Hệ thống

*   **Hệ điều hành:** Linux (khuyến nghị Kali Linux hoặc các bản phân phối Debian-based).
*   **Python:** 3.11+
*   **Conda (khuyến nghị):** Để quản lý môi trường.
*   **Docker:** Để chạy các máy lab thử nghiệm.
*   **MySQL Server:** Một server MySQL đang chạy (có thể là cục bộ hoặc trên Docker).
*   **Zilliz Cloud Account:** Một tài khoản Zilliz Cloud (có gói miễn phí) để host Knowledge Base.

### 2. Cài đặt Môi trường

1.  **Sao chép Repository:**
    ```bash
    git clone <URL_CUA_REPOSITORY_VULCAN> VulCan-main
    cd VulCan-main
    ```

2.  **Tạo và Kích hoạt Môi trường Conda:**
    ```bash
    conda create --name vulcanenv python=3.11 -y
    conda activate vulcanenv
    ```

3.  **Cài đặt các Phụ thuộc Python:**
    Lệnh này sẽ đọc `pyproject.toml` và cài đặt tất cả các thư viện cần thiết.
    ```bash
    pip install -e .[dev]
    ```

### 3. Thiết lập Cấu hình

Bạn cần chỉnh sửa các tệp `.yaml` trong thư mục gốc của dự án.

1.  **Database (`db_config.yaml`):**
    Cung cấp thông tin kết nối đến MySQL server của bạn.
    ```yaml
    mysql:
      host: 127.0.0.1
      port: 3306
      user: your_user
      password: your_password
      database: vulcan_db
    ```
Chạy lệnh để khởi tạo service DB
```bash
docker compose up -d
```


2.  **Mô hình Ngôn ngữ (`llm_config.yaml`):**
    Chọn chế độ `local` (Ollama) hoặc `remote` (AWS Bedrock).
    ```yaml
    # Ví dụ cho chế độ local
    server: local
    ollama_host: http://localhost:11434
    ollama_model_id: llama3 # Hoặc model khác bạn đã pull
    
    # Ví dụ cho chế độ remote
    # server: remote
    # aws_region: us-east-1
    # bedrock_model_id: anthropic.claude-3-sonnet-20240229-v1:0
    ```
    *   Nếu dùng Ollama, đảm bảo bạn đã chạy `ollama pull <tên_model>`.
    *   Nếu dùng Bedrock, đảm bảo bạn đã cấu hình AWS credentials (`aws configure`).
    *  Nên ưu tiên sử dụng chế độ remote

3.  **Knowledge Base (`kb_config.yaml`):**
    Điền thông tin từ Zilliz Cloud của bạn.
    ```yaml
    kb_name: vulcan_rag # Tên collection bạn đã tạo
    milvus:
      uri: "https://your-zilliz-cloud-uri.com"
      password: "your-zilliz-cloud-api-key"
    embedding_model: "all-MiniLM-L6-v2" # Model dùng để nạp và truy vấn
    # ... các cấu hình khác
    ```

### 4. Khởi tạo Dự án

Sau khi đã cấu hình xong, chạy lệnh `init` một lần duy nhất. Lệnh này sẽ tạo các thư mục cần thiết và các bảng trong database.

```bash
python -m vulcan.cli init
```
hoặc 
```bash
vulcan init 
```
---

## Cách chạy VulCan

### Chế độ Tương tác (Khuyến nghị)

Chạy agent mà không cần tham số. Chương trình sẽ hỏi bạn muốn tiếp tục session cũ hay tạo mới.

```bash
python -m vulcan.cli start
```
hoặc 
```bash
vulcan start
```

### Chế độ Không tương tác (Dùng cho Kịch bản)

Cung cấp nhiệm vụ trực tiếp qua cờ `-m` hoặc `--mission`.

```bash
python -m vulcan.cli start --mission "Target: <IP>, Objective: <Mô tả nhiệm vụ>"
```

### Các Tùy chọn Hữu ích

*   `--iterations <số>`: Ghi đè số bước tối đa được định nghĩa trong `config.yaml`.
*   `--no-parallel`: Buộc agent không thực thi các lệnh `shell` song song (hữu ích cho việc gỡ lỗi).

**Ví dụ một phiên chạy hoàn chỉnh:**

```bash
# Bắt đầu một cuộc pentest trên máy lab DVWA
python -m vulcan.cli start --mission "Target: http://127.0.0.1:8080, Objective: Find and exploit SQL Injection and Command Injection vulnerabilities in DVWA at low security level."
```