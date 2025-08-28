import json
import os

import boto3

print("\n" + "=" * 60)
print("RUNNING DIAGNOSTIC SCRIPT: test_bedrock.py")
print("=" * 60)

try:
    # 1. Khởi tạo session và lấy thông tin cơ bản
    session = boto3.Session()
    boto_region = session.region_name
    env_region = os.environ.get("AWS_REGION")

    print("\n--- ENVIRONMENT & REGION ---")
    print(f"Boto3 effective region (session.region_name): {boto_region}")
    print(f"AWS_REGION environment variable: {env_region}")

    # 2. Lấy danh tính người gọi (credentials)
    sts_client = boto3.client("sts")
    identity = sts_client.get_caller_identity()

    print("\n--- CREDENTIALS (CALLER IDENTITY) ---")
    print(f"UserID: {identity.get('UserId')}")
    print(f"Account: {identity.get('Account')}")
    print(f"ARN: {identity.get('Arn')}")

    # 3. Thực hiện lệnh gọi API
    region_to_use = boto_region or "us-east-1"
    model_id = "amazon.titan-embed-text-v2:0"

    print(f"\n--- API CALL ---")
    print(f"Attempting to invoke model '{model_id}' in region '{region_to_use}'...")

    bedrock_runtime = boto3.client(
        service_name="bedrock-runtime", region_name=region_to_use
    )

    body = json.dumps({"inputText": "Test"})

    response = bedrock_runtime.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())

    print("\n--- RESULT ---")
    print("SUCCESS! API call was successful.")
    print("This proves that the credentials and region above are CORRECT.")
    print("=" * 60 + "\n")


except Exception as e:
    print(f"\n--- RESULT ---")
    print(f"ERROR: An exception occurred: {e}")
    print("This indicates a problem with the credentials or region above.")
    import traceback

    traceback.print_exc()
    print("=" * 60 + "\n")
