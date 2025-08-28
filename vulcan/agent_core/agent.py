import logging
import os
import warnings
from datetime import datetime
from typing import List, Optional, Tuple

import ollama
import requests
from dotenv import load_dotenv
from langchain_mistralai import MistralAIEmbeddings
from mistralai import Mistral, SDKError
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel
from strands.models.litellm import LiteLLMModel
from strands.models.mistral import MistralModel
from strands.models.ollama import OllamaModel
from strands.models.openai import OpenAIModel
from strands_tools import editor, http_request, load_tool, shell, stop, swarm
from strands_tools.swarm import swarm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

from pathlib import Path

# Import hệ thống Configs và Session
from vulcan.config.config import Configs
from vulcan.persistence.models.session_model import Session
from vulcan.utils.agent_utils import Colors

from .agent_handlers import ReasoningHandler
from .memory_tools import initialize_memory_system, mem0_memory

# Module nội bộ
from .system_prompts import get_system_prompt
from .tools.knowledge_tools import query_knowledge_base

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _create_remote_model(
    model_id: str,
    region_name: str,
    temperature: float,
    max_tokens: int = 4096,
) -> BedrockModel:
    """Create an AWS Bedrock model instance."""
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
    """Create an Ollama model instance."""
    return OllamaModel(
        host=host, model_id=model_id, temperature=temperature, max_tokens=max_tokens
    )


def _validate_server_requirements() -> None:
    """Validate server requirements based on configuration."""
    server_type = Configs.llm_config.server

    if server_type == "ollama":
        ollama_host = Configs.llm_config.ollama_host
        try:
            response = requests.get(f"{ollama_host}/api/version", timeout=5)
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(
                f"Ollama server not accessible at {ollama_host}. Please ensure Ollama is running."
            ) from e
        try:
            client = ollama.Client(host=ollama_host)
            models_response = client.list()
            available_models = [
                m.get("model", m.get("name", ""))
                for m in models_response.get("models", [])
            ]
            required_model = Configs.llm_config.ollama_model_id
            if not any(required_model in model for model in available_models):
                raise ValueError(
                    f"Required model not found: {required_model}. "
                    f"Pull it with: ollama pull {required_model}"
                )
        except ValueError:
            raise
        except Exception as e:
            raise ConnectionError(f"Could not verify Ollama models: {e}") from e

    elif server_type == "bedrock":
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_profile = os.getenv("AWS_PROFILE")
        aws_credentials_file = Path.home() / ".aws" / "credentials"
        credentials_found = bool(
            aws_access_key or aws_profile or aws_credentials_file.is_file()
        )
        if not credentials_found:
            raise EnvironmentError(
                "AWS credentials not configured for remote mode. "
                "Please set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY environment variables, "
                "or run 'aws configure' to set up a credentials file."
            )

    elif server_type == "mistral":
        api_key = Configs.llm_config.mistral_api_key or os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "Mistral API key not configured. Please set it in llm_config.yaml or as MISTRAL_API_KEY environment variable."
            )

        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type(Exception),
        )
        def check_mistral_api():
            try:
                client = Mistral(api_key=api_key)
                client.models.list()
            except SDKError as e:
                raise ConnectionError(
                    f"Mistral API key is invalid or has insufficient permissions: {e}"
                ) from e
            except Exception as e:
                raise ConnectionError(
                    f"Could not connect to Mistral API. Check your network connection. Error: {e}"
                ) from e

        check_mistral_api()
    elif server_type == "openai":
        if not (Configs.llm_config.openai_api_key or os.getenv("OPENAI_API_KEY")):
            raise EnvironmentError("OpenAI API key not configured...")
    elif server_type == "gemini":
        if not (Configs.llm_config.gemini_api_key or os.getenv("GEMINI_API_KEY")):
            raise EnvironmentError("Gemini API key not configured...")


def _handle_model_creation_error(error: Exception) -> None:
    """Provide helpful error messages for model creation failures."""
    server_type = Configs.llm_config.server
    if server_type == "ollama":
        print(f"{Colors.RED}[!] Ollama model creation failed: {error}{Colors.RESET}")
        print(
            "    Troubleshooting: Ensure Ollama is running and the required model is pulled."
        )
    else:
        print(f"{Colors.RED}[!] Remote model creation failed: {error}{Colors.RESET}")
        print(
            f"    Troubleshooting: Check your API keys/credentials and model access in region: {Configs.llm_config.aws_region}"
        )


def setup_hf_token():
    """Setup HuggingFace token để tránh warning."""
    hf_token = os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN")

    if not hf_token:
        os.environ["HF_TOKEN"] = "hf_dummy_token_to_suppress_warning"
        print("[+] Set dummy HF_TOKEN to reduce warnings")
    else:
        os.environ["HF_TOKEN"] = hf_token


def _build_memory_config(session_id: str) -> dict:
    """Build memory system configuration based on LLM server type."""
    llm_config = Configs.llm_config
    memory_config = {}

    # Embedder config
    if llm_config.server == "ollama":
        memory_config["embedder"] = {
            "provider": "ollama",
            "config": {"model": llm_config.ollama_embedding_model_id},
        }

    elif llm_config.server == "mistral":
        setup_hf_token()
        mistral_embeddings = MistralAIEmbeddings(
            model="mistral-embed",
            mistral_api_key=llm_config.mistral_api_key,
            max_concurrent_requests=1,
            max_retries=3,
        )

        memory_config["embedder"] = {
            "provider": "langchain",
            "config": {"model": mistral_embeddings},
        }
    elif llm_config.server == "bedrock":
        memory_config["embedder"] = {
            "provider": "aws_bedrock",
            "config": {
                "model": "amazon.titan-embed-text-v2:0",
                "aws_region": llm_config.aws_region,
            },
        }
    elif llm_config.server == "openai":
        memory_config["embedder"] = {
            "provider": "litellm",
            "config": {
                "model": "text-embedding-ada-002",
            },
        }

    elif llm_config.server == "gemini":
        memory_config["embedder"] = {
            "provider": "litellm",
            "config": {
                "model": "gemini/embedding-001",
            },
        }
    # Internal LLM config for Mem0
    if llm_config.server == "ollama":
        memory_config["llm"] = {
            "provider": "ollama",
            "config": {
                "model": llm_config.ollama_model_id,
                "temperature": 0.1,
            },
        }
    elif llm_config.server == "mistral":
        memory_config["llm"] = {
            "provider": "litellm",
            "config": {
                "model": f"mistral/{llm_config.mistral_model_id}",
                "temperature": 0.1,
            },
        }
    elif llm_config.server == "bedrock":
        memory_config["llm"] = {
            "provider": "aws_bedrock",
            "config": {
                "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "temperature": 0.1,
                "aws_region": llm_config.aws_region,
            },
        }
    elif llm_config.server == "openai":
        memory_config["llm"] = {
            "provider": "openai",
            "config": {
                "model": "gpt-4o",
                "temperature": 0.1,
            },
        }

    elif llm_config.server == "gemini":
        memory_config["llm"] = {
            "provider": "gemini",
            "config": {
                "model": "gemini-2.0-flash-001",
                "temperature": 0.1,
            },
        }

    # Vector store config with correct dimensions
    faiss_path = f"./memory/mem0_faiss_{session_id or 'default'}"
    memory_config["vector_store"] = {
        "provider": "faiss",
        "config": {
            "embedding_model_dims": 1024,
            "path": faiss_path,
        },
    }

    return memory_config


def create_agent(
    session: Session,
    max_steps: int,
    available_tools: List[str],
    is_parallel_disabled: bool = False,
) -> Tuple[Agent, ReasoningHandler]:
    """
    Create an autonomous agent based on a Session object and global configurations.
    """
    logger = logging.getLogger("VulCanAgent")
    logger.debug(f"Creating agent for session ID: {session.id}")

    llm_config = Configs.llm_config
    server_type = llm_config.server

    _validate_server_requirements()

    if server_type == "ollama":
        os.environ["OLLAMA_HOST"] = llm_config.ollama_host
        print(f"[+] Setting OLLAMA_HOST for Mem0: {llm_config.ollama_host}")
    elif server_type == "mistral":
        api_key = Configs.llm_config.mistral_api_key or os.getenv("MISTRAL_API_KEY")
        if api_key:
            os.environ["MISTRAL_API_KEY"] = api_key

    memory_config = _build_memory_config(session.id)
    initialize_memory_system(config=memory_config, operation_id=session.id)
    logger.info(f"Memory system initialized for operation: {session.id}")

    system_prompt = get_system_prompt(
        session=session,
        max_steps=max_steps,
        tools_context=", ".join(available_tools),
        is_parallel_disabled=is_parallel_disabled,
    )

    callback_handler = ReasoningHandler(max_steps=max_steps, operation_id=session.id)

    try:
        if server_type == "ollama":
            logger.debug("Configuring OllamaModel")
            model = _create_local_model(
                model_id=llm_config.ollama_model_id,
                host=llm_config.ollama_host,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
            print(
                f"{Colors.GREEN}[+] Local model initialized: {llm_config.ollama_model_id}{Colors.RESET}"
            )
        elif server_type == "mistral":
            logger.debug("Configuring MistralModel")
            model = MistralModel(
                api_key=Configs.llm_config.mistral_api_key,
                model_id=llm_config.mistral_model_id,
                max_tokens=llm_config.max_tokens,
                temperature=llm_config.temperature,
            )
            print(
                f"{Colors.GREEN}[+] Mistral AI model initialized: {llm_config.mistral_model_id}{Colors.RESET}"
            )
        elif server_type == "openai":
            logger.debug("Configuring OpenAIModel")
            client_args = {"api_key": Configs.llm_config.openai_api_key}
            if Configs.llm_config.openai_base_url:
                client_args["base_url"] = Configs.llm_config.openai_base_url

            model = OpenAIModel(
                client_args=client_args,
                model_id=Configs.llm_config.openai_model_id,
                params={
                    "max_tokens": Configs.llm_config.max_tokens,
                    "temperature": Configs.llm_config.temperature,
                },
            )
            print(
                f"{Colors.GREEN}[+] OpenAI model initialized: {Configs.llm_config.openai_model_id}{Colors.RESET}"
            )

        elif server_type == "gemini":
            logger.debug("Configuring LiteLLMModel for Gemini")
            model = LiteLLMModel(
                client_args={"api_key": Configs.llm_config.gemini_api_key},
                model_id=Configs.llm_config.gemini_model_id,
                params={
                    "max_tokens": Configs.llm_config.max_tokens,
                    "temperature": Configs.llm_config.temperature,
                },
            )
            print(
                f"{Colors.GREEN}[+] Gemini (via LiteLLM) initialized: {Configs.llm_config.gemini_model_id}{Colors.RESET}"
            )
        else:
            logger.debug("Configuring BedrockModel")
            model = _create_remote_model(
                model_id=llm_config.bedrock_model_id,
                region_name=llm_config.aws_region,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
            print(
                f"{Colors.GREEN}[+] Remote model initialized: {llm_config.bedrock_model_id}{Colors.RESET}"
            )
    except Exception as e:
        _handle_model_creation_error(e)
        raise
    core_tools = {
        "shell": shell,
        "editor": editor,
        "load_tool": load_tool,
        "stop": stop,
        "mem0_memory": mem0_memory,
        "query_knowledge_base": query_knowledge_base,
        "swarm": swarm,
        "http_request": http_request,
    }
    agent = Agent(
        model=model,
        tools=[*core_tools.values()],
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=120),
        load_tools_from_directory=True,
    )

    logger.debug("Agent initialized successfully")
    return agent, callback_handler
