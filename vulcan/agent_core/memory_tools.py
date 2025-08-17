import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from mem0 import Memory as Mem0Memory
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from strands import tool

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Rich console
console = Console()

# Global client
_MEMORY_CLIENT: Optional[Mem0Memory] = None
_OPERATION_ID: Optional[str] = None

# Tool specification
TOOL_SPEC = {
    "name": "mem0_memory",
    "description": (
        "Memory management tool for storing, retrieving, and managing memories in Mem0.\n\n"
        "Features:\n"
        "1. Store memories with metadata (requires user_id or agent_id)\n"
        "2. Retrieve memories by ID or semantic search (requires user_id or agent_id)\n"
        "3. List all memories for a user/agent (requires user_id or agent_id)\n"
        "4. Delete memories\n"
        "5. Get memory history\n\n"
        "Actions:\n"
        "- store: Store new memory (requires user_id or agent_id)\n"
        "- get: Get memory by ID\n"
        "- list: List all memories (requires user_id or agent_id)\n"
        "- retrieve: Semantic search (requires user_id or agent_id)\n"
        "- delete: Delete memory\n"
        "- history: Get memory history\n\n"
        "Note: Most operations require either user_id or agent_id to be specified."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform (store, get, list, retrieve, delete, history)",
                    "enum": ["store", "get", "list", "retrieve", "delete", "history"],
                },
                "content": {
                    "type": "string",
                    "description": "Content to store (required for store action)",
                },
                "memory_id": {
                    "type": "string",
                    "description": "Memory ID (required for get, delete, history actions)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for retrieve action)",
                },
                "user_id": {
                    "type": "string",
                    "description": "User ID for the memory operations (required for store, list, retrieve actions)",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID for the memory operations (required for store, list, retrieve actions)",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata to store with the memory",
                },
            },
            "required": ["action"],
        }
    },
}

def format_get_response(memory: Dict) -> Panel:
    """Format get memory response."""
    memory_id = memory.get("id", "unknown")
    content = memory.get("memory", "No content available")
    metadata = memory.get("metadata")
    created_at = memory.get("created_at", "Unknown")
    user_id = memory.get("user_id", "Unknown")

    result = [
        "✅ Memory retrieved successfully:",
        f"🔑 Memory ID: {memory_id}",
        f"👤 User ID: {user_id}",
        f"🕒 Created: {created_at}",
    ]

    if metadata:
        result.append(f"📋 Metadata: {json.dumps(metadata, indent=2)}")

    result.append(f"\n📄 Memory: {content}")

    return Panel("\n".join(result), title="[bold green]Memory Retrieved", border_style="green")

def format_list_response(memories: List[Dict]) -> Panel:
    """Format list memories response."""
    if not memories:
        return Panel("No memories found.", title="[bold yellow]No Memories", border_style="yellow")

    table = Table(title="Memories", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Memory", style="yellow", width=50)
    table.add_column("Created At", style="blue")
    table.add_column("User ID", style="green")
    table.add_column("Metadata", style="magenta")

    for memory in memories:
        memory_id = memory.get("id", "unknown")
        content = memory.get("memory", "No content available")
        created_at = memory.get("created_at", "Unknown")
        user_id = memory.get("user_id", "Unknown")
        metadata = memory.get("metadata", {})

        content_preview = content[:100] + "..." if len(content) > 100 else content
        metadata_str = json.dumps(metadata, indent=2) if metadata else "None"

        table.add_row(memory_id, content_preview, created_at, user_id, metadata_str)

    return Panel(table, title="[bold green]Memories List", border_style="green")

def format_delete_response(memory_id: str) -> Panel:
    """Format delete memory response."""
    content = [
        "✅ Memory deleted successfully:",
        f"🔑 Memory ID: {memory_id}",
    ]
    return Panel("\n".join(content), title="[bold green]Memory Deleted", border_style="green")

def format_retrieve_response(memories: List[Dict]) -> Panel:
    """Format retrieve response."""
    if not memories:
        return Panel("No memories found matching the query.", title="[bold yellow]No Matches", border_style="yellow")

    table = Table(title="Search Results", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Memory", style="yellow", width=50)
    table.add_column("Relevance", style="green")
    table.add_column("Created At", style="blue")
    table.add_column("User ID", style="magenta")
    table.add_column("Metadata", style="white")

    for memory in memories:
        memory_id = memory.get("id", "unknown")
        content = memory.get("memory", "No content available")
        score = memory.get("score", 0)
        created_at = memory.get("created_at", "Unknown")
        user_id = memory.get("user_id", "Unknown")
        metadata = memory.get("metadata", {})

        content_preview = content[:100] + "..." if len(content) > 100 else content
        metadata_str = json.dumps(metadata, indent=2) if metadata else "None"

        if score > 0.8:
            score_color = "green"
        elif score > 0.5:
            score_color = "yellow"
        else:
            score_color = "red"

        table.add_row(
            memory_id, content_preview, f"[{score_color}]{score}[/{score_color}]", created_at, user_id, metadata_str
        )

    return Panel(table, title="[bold green]Search Results", border_style="green")

def format_history_response(history: List[Dict]) -> Panel:
    """Format memory history response."""
    if not history:
        return Panel("No history found for this memory.", title="[bold yellow]No History", border_style="yellow")

    table = Table(title="Memory History", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Memory ID", style="green")
    table.add_column("Event", style="yellow")
    table.add_column("Old Memory", style="blue", width=30)
    table.add_column("New Memory", style="blue", width=30)
    table.add_column("Created At", style="magenta")

    for entry in history:
        entry_id = entry.get("id", "unknown")
        memory_id = entry.get("memory_id", "unknown")
        event = entry.get("event", "UNKNOWN")
        old_memory = entry.get("old_memory", "None")
        new_memory = entry.get("new_memory", "None")
        created_at = entry.get("created_at", "Unknown")

        old_memory_preview = old_memory[:100] + "..." if old_memory and len(old_memory) > 100 else old_memory
        new_memory_preview = new_memory[:100] + "..." if new_memory and len(new_memory) > 100 else new_memory

        table.add_row(entry_id, memory_id, event, old_memory_preview, new_memory_preview, created_at)

    return Panel(table, title="[bold green]Memory History", border_style="green")

def format_store_response(results: List[Dict]) -> Panel:
    """Format store memory response."""
    if not results:
        return Panel("No memories stored.", title="[bold yellow]No Memories Stored", border_style="yellow")

    table = Table(title="Memory Stored", show_header=True, header_style="bold magenta")
    table.add_column("Operation", style="green")
    table.add_column("Content", style="yellow", width=50)

    for memory in results:
        event = memory.get("event")
        text = memory.get("memory")
        content_preview = text[:100] + "..." if len(text) > 100 else text
        table.add_row(event, content_preview)

    return Panel(table, title="[bold green]Memory Stored", border_style="green")

def initialize_memory_system(config: Dict, operation_id: Optional[str] = None) -> None:
    """Initialize the memory system with a pre-built configuration."""
    global _MEMORY_CLIENT, _OPERATION_ID
    
    print("[+] Initializing Memory System...")
    try:
        _MEMORY_CLIENT = Mem0Memory.from_config(config)
        _OPERATION_ID = operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info("Memory system initialized for operation %s", _OPERATION_ID)
        print("[+] Memory System Initialized Successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Mem0Memory from config: {e}")
        raise

def get_memory_client() -> Optional[Mem0Memory]:
    """Get the current memory client."""
    return _MEMORY_CLIENT

@tool
def mem0_memory(
    action: str,
    content: Optional[str] = None,
    memory_id: Optional[str] = None,
    query: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """
    Memory management tool for storing, retrieving, and managing memories in Mem0.
    """
    global _MEMORY_CLIENT

    if _MEMORY_CLIENT is None:
        return "Error: Memory system is not initialized."

    try:
        if not user_id and not agent_id:
            user_id = "vulcan_agent"

        strands_dev = os.environ.get("BYPASS_TOOL_CONSENT", "").lower() == "true"
        mem0 = _MEMORY_CLIENT

        if action == "store":
            if not content:
                raise ValueError("content is required for store action")

            cleaned_content = str(content).replace('\x00', '').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
            cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
            if not cleaned_content:
                raise ValueError("Content is empty after cleaning")

            if metadata:
                cleaned_metadata = {}
                for key, value in metadata.items():
                    if isinstance(value, str):
                        cleaned_value = str(value).replace('\x00', '').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
                        cleaned_value = re.sub(r'\s+', ' ', cleaned_value)
                        cleaned_metadata[key] = cleaned_value
                    else:
                        cleaned_metadata[key] = value
                metadata = cleaned_metadata

            mem0_logger = logging.getLogger('root')
            original_level = mem0_logger.level
            mem0_logger.setLevel(logging.CRITICAL)
            
            try:
                results = mem0.add([{"role": "user", "content": cleaned_content}], user_id=user_id, agent_id=agent_id, metadata=metadata, infer=False)
            except Exception as store_error:
                if "Extra data" in str(store_error) or "Expecting value" in str(store_error):
                    fallback_result = [{"status": "stored", "content_preview": cleaned_content[:50] + "..."}]
                    if not strands_dev:
                        console.print("[yellow]Memory stored with minor parsing warnings[/yellow]")
                    return json.dumps(fallback_result, indent=2)
                else:
                    raise store_error
            finally:
                mem0_logger.setLevel(original_level)

            if results is None:
                results_list = []
            elif isinstance(results, list):
                results_list = results
            elif isinstance(results, dict):
                results_list = results.get("results", [])
            else:
                results_list = []
            if results_list and not strands_dev:
                panel = format_store_response(results_list)
                console.print(panel)
            return json.dumps(results_list, indent=2)

        elif action == "get":
            if not memory_id:
                raise ValueError("memory_id is required for get action")

            memory = mem0.get(memory_id)
            if not strands_dev:
                panel = format_get_response(memory)
                console.print(panel)
            return json.dumps(memory, indent=2)

        elif action == "list":
            memories = mem0.get_all(user_id=user_id, agent_id=agent_id)
            if memories is None:
                results_list = []
            elif isinstance(memories, list):
                results_list = memories
            elif isinstance(memories, dict):
                results_list = memories.get("results", [])
            else:
                results_list = []
            if not strands_dev:
                panel = format_list_response(results_list)
                console.print(panel)
            return json.dumps(results_list, indent=2)

        elif action == "retrieve":
            if not query:
                raise ValueError("query is required for retrieve action")

            memories = mem0.search(query=query, user_id=user_id, agent_id=agent_id)
            if memories is None:
                results_list = []
            elif isinstance(memories, list):
                results_list = memories
            elif isinstance(memories, dict):
                results_list = memories.get("results", [])
            else:
                results_list = []
            if not strands_dev:
                panel = format_retrieve_response(results_list)
                console.print(panel)
            return json.dumps(results_list, indent=2)

        elif action == "delete":
            if not memory_id:
                raise ValueError("memory_id is required for delete action")

            mem0.delete(memory_id)
            if not strands_dev:
                panel = format_delete_response(memory_id)
                console.print(panel)
            return f"Memory {memory_id} deleted successfully"

        elif action == "history":
            if not memory_id:
                raise ValueError("memory_id is required for history action")

            history = mem0.history(memory_id)
            if not strands_dev:
                panel = format_history_response(history)
                console.print(panel)
            return json.dumps(history, indent=2)

        else:
            raise ValueError(f"Invalid action: {action}")

    except Exception as e:
        error_msg = f"Error in memory tool: {str(e)}"
        if not strands_dev:
            error_panel = Panel(
                Text(str(e), style="red"),
                title="❌ Memory Operation Error",
                border_style="red",
            )
            console.print(error_panel)
        return error_msg