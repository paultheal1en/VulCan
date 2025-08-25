from strands import Agent
from vulcan.config.config import Configs

_llm_agent_cache = None

def _get_llm_agent():
    """
    Tạo hoặc lấy lại một agent đơn giản chỉ để nói chuyện với LLM.
    """
    global _llm_agent_cache
    if _llm_agent_cache is None:
        llm_config = Configs.llm_config
        if llm_config.server == 'local':
            from strands.models.ollama import OllamaModel
            model = OllamaModel(
                host=llm_config.ollama_host,
                model_id=llm_config.ollama_model_id,
            )
        else: # remote
            from strands.models import BedrockModel
            model = BedrockModel(
                model_id=llm_config.bedrock_model_id,
                region_name=llm_config.aws_region
            )
        
        _llm_agent_cache = Agent(model=model, tools=[], system_prompt="You are a helpful assistant.")
    return _llm_agent_cache

def _chat(query: str, **kwargs) -> tuple[str, None]:
    """
    Gửi một truy vấn đến LLM và trả về kết quả.
    Tương thích với cách gọi của APG.
    """
    agent = _get_llm_agent()
    response = agent(query)
    return str(response), None # Trả về tuple để giống với hàm _chat gốc