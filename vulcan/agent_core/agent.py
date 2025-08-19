import os
import logging
import warnings
from datetime import datetime
from typing import Optional, List, Tuple

import requests
import ollama
from strands import Agent
from strands.models import BedrockModel
from strands.models.ollama import OllamaModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, editor, load_tool, stop, http_request
from strands_tools.swarm import swarm

# Import hệ thống Configs và Session
from vulcan.config.config import Configs
from vulcan.persistence.models.session_model import Session

# Module nội bộ
from .system_prompts import get_system_prompt
from .agent_handlers import ReasoningHandler
from .utils import Colors
from .memory_tools import mem0_memory, initialize_memory_system
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

def _create_remote_model(
    model_id: str,
    region_name: str,
    temperature: float,
    max_tokens: int = 4096,
) -> BedrockModel:
    """Tạo AWS Bedrock model instance"""
    return BedrockModel(
        model_id=model_id,
        region_name=region_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )

def _create_local_model(
    model_id: str,
    host: str,
    temperature: float,
    max_tokens: int = 4096,
) -> OllamaModel:
    """Tạo Ollama model instance"""
    return OllamaModel(
        host=host, model_id=model_id, temperature=temperature, max_tokens=max_tokens
    )

def _validate_server_requirements() -> None:
    """Kiểm tra yêu cầu server dựa trên cấu hình."""
    server_type = Configs.llm_config.server

    if server_type == "local":
        ollama_host = Configs.llm_config.ollama_host
        try:
            response = requests.get(f"{ollama_host}/api/version", timeout=5)
            if response.status_code != 200:
                raise ConnectionError("Ollama server not responding")
        except Exception:
            raise ConnectionError(
                f"Ollama server not accessible at {ollama_host}. Please ensure Ollama is running."
            )
        try:
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [m.get("model", m.get("name", "")) for m in models_response.get("models", [])]
            required_model = Configs.llm_config.ollama_model_id
            if not any(required_model in model for model in available_models):
                raise ValueError(
                    f"Required model not found: {required_model}. "
                    f"Pull it with: ollama pull {required_model}"
                )
        except Exception as e:
            if "Required model not found" in str(e):
                raise e
            raise ConnectionError(f"Could not verify Ollama models: {e}")

    elif server_type == "remote":
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_profile = os.getenv("AWS_PROFILE")
        
        # Kiểm tra sự tồn tại của file credentials mặc định
        aws_credentials_file = Path.home() / ".aws" / "credentials"
        
        credentials_found = False
        if aws_access_key:
            credentials_found = True
        elif aws_profile:
            credentials_found = True
        elif aws_credentials_file.is_file():
            credentials_found = True
            
        if not credentials_found:
            raise EnvironmentError(
                "AWS credentials not configured for remote mode. "
                "Please set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY environment variables, "
                "or run 'aws configure' to set up a credentials file."
            )

def _handle_model_creation_error(error: Exception) -> None:
    """Cung cấp thông báo lỗi hữu ích."""
    server_type = Configs.llm_config.server
    if server_type == "local":
        print(f"{Colors.RED}[!] Local model creation failed: {error}{Colors.RESET}")
        print("    Troubleshooting: Ensure Ollama is running and the required model is pulled.")
    else:
        print(f"{Colors.RED}[!] Remote model creation failed: {error}{Colors.RESET}")
        print("    Troubleshooting: Check AWS credentials and Bedrock model access in region: {Configs.llm_config.aws_region}")

def create_agent(
    session: Session,
    max_steps: int,
    available_tools: List[str],
    has_persisted_plan: bool = False,
) -> Tuple[Agent, ReasoningHandler]:
    """
    Creates an autonomous agent based on a Session object and global configurations.
    """
    logger = logging.getLogger("VulCanAgent")
    logger.debug(f"Creating agent for session ID: {session.id}")
    
    llm_config = Configs.llm_config
    server_type = llm_config.server

    _validate_server_requirements()

    # Build Memory System Configuration and Initialize
    memory_config = {}

    if llm_config.server == "local":
        os.environ["OLLAMA_HOST"] = llm_config.ollama_host
        print(f"[+] Setting OLLAMA_HOST for Mem0: {llm_config.ollama_host}")

    # Build embedder config
    if llm_config.server == "local":
        memory_config["embedder"] = {
            "provider": "ollama",
            "config": {
                "model": llm_config.ollama_embedding_model_id,
            }
        }
    else:  # remote
        memory_config["embedder"] = {
            "provider": "aws_bedrock", 
            "config": {
                "model": "amazon.titan-embed-text-v2:0",
                "aws_region": llm_config.aws_region 
            }
        }

    # Build internal LLM config for Mem0
    if llm_config.server == "local":
        memory_config["llm"] = {
            "provider": "ollama",
            "config": {
                "model": llm_config.ollama_model_id,
                "temperature": 0.1,
            }
        }
    else:  # remote
        memory_config["llm"] = {
            "provider": "aws_bedrock",
            "config": {
                "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "temperature": 0.1,
                "aws_region": llm_config.aws_region
            }
        }

    # Build vector store config
    faiss_path = f"./mem0_faiss_{session.id or 'default'}"
    memory_config["vector_store"] = {
        "provider": "faiss",
        "config": {
            "embedding_model_dims": 1024,
            "path": faiss_path
        }
    }
    # Initialize the memory system with the built config
    initialize_memory_system(config=memory_config, operation_id=session.id)
    logger.info(f"Memory system initialized for operation: {session.id}")

    system_prompt = get_system_prompt(
        session=session,
        max_steps=max_steps,
        tools_context=", ".join(available_tools),
        has_persisted_plan=has_persisted_plan
    )

    callback_handler = ReasoningHandler(max_steps=max_steps, operation_id=session.id)

    try:
        if server_type == "local":
            logger.debug("Configuring OllamaModel")
            model = _create_local_model(
                model_id=llm_config.ollama_model_id,
                host=llm_config.ollama_host,
                temperature=llm_config.temperature,
            )
            print(f"{Colors.GREEN}[+] Local model initialized: {llm_config.ollama_model_id}{Colors.RESET}")
        else:
            logger.debug("Configuring BedrockModel")
            model = _create_remote_model(
                model_id=llm_config.bedrock_model_id,
                region_name=llm_config.aws_region,
                temperature=llm_config.temperature,
            )
            print(f"{Colors.GREEN}[+] Remote model initialized: {llm_config.bedrock_model_id}{Colors.RESET}")
    except Exception as e:
        _handle_model_creation_error(e)
        raise

    agent = Agent(
        model=model,
        tools=[
            swarm, 
            shell,
            editor,
            load_tool,
            mem0_memory,
            stop,
            http_request,
        ],
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=120),
        load_tools_from_directory=True
    )

    logger.debug("Agent initialized successfully")
    return agent, callback_handler
    