"""
LLM Service - Handles both Claude and OpenAI implementations.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Union, Optional
from openai import OpenAI
from anthropic import Anthropic
import json

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> str:
        """Generate chat completion."""
        pass

    @abstractmethod
    def vision_completion(
        self,
        messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> str:
        """Generate completion for vision tasks."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI implementation."""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.vision_model = "gpt-4-vision-preview"
        self.chat_model = "gpt-4-1106-preview"
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content

    def vision_completion(
        self,
        messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content


class ClaudeProvider(LLMProvider):
    """Claude implementation."""
    
    def __init__(self):
        self.client = Anthropic(
            api_key=os.getenv("CLAUDE_API_KEY"),
            http_client=None,  # Let Anthropic create its default client
        )
        # Use a current, generally available Claude model
        self.model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    
    def _oai_to_claude_blocks(self, content) -> List[Dict[str, Union[str, Dict[str, str]]]]:
        """Convert OpenAI-style message content (text + image_url blocks) to Anthropic blocks."""
        blocks = []
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    blocks.append({"type": "text", "text": item.get("text", "")})
                elif item.get("type") == "image_url":
                    # Expect data URL like: data:image/png;base64,<base64>
                    url = item.get("image_url", {}).get("url", "")
                    if url.startswith("data:application/pdf"):
                        # Handle PDF data URL if ever passed
                        b64_data = url.split(",", 1)[1]
                        blocks.append({
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": b64_data,
                            },
                        })
                    elif url.startswith("data:image/"):
                        # Handle image data URL
                        media_type = url.split(":", 1)[1].split(";", 1)[0]
                        b64_data = url.split(",", 1)[1]
                        # Heuristic fix: ensure media_type matches data by checking common base64 signatures
                        head = b64_data[:10]
                        if head.startswith("iVBORw0KG"):
                            media_type = "image/png"
                        elif head.startswith("/9j/"):
                            media_type = "image/jpeg"
                        blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        })
        else:
            # Plain text
            blocks.append({"type": "text", "text": str(content)})
        return blocks

    def _convert_to_claude_messages(
        self,
        messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]]
    ) -> (Optional[str], List[Dict[str, Union[str, List[Dict[str, str]]]]]):
        """Split out system prompt and convert remaining messages into Claude format with blocks."""
        system_message = next((msg["content"] for msg in messages if msg.get("role") == "system"), None)
        claude_messages = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue
            content = msg.get("content", "")
            blocks = self._oai_to_claude_blocks(content)
            claude_messages.append({"role": role, "content": blocks})
        return system_message, claude_messages

    def chat_completion(
        self,
        messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]],
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> str:
        system_message, claude_messages = self._convert_to_claude_messages(messages)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=claude_messages,
        )
        # Concatenate text blocks from the first response message
        parts = []
        for part in getattr(response, "content", []) or []:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif hasattr(part, "text"):
                parts.append(getattr(part, "text"))
        return "".join(parts) if parts else (getattr(response, "content", "") or "")

    def vision_completion(
        self,
        messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> str:
        system_message, claude_messages = self._convert_to_claude_messages(messages)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=claude_messages,
        )
        parts = []
        for part in getattr(response, "content", []) or []:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif hasattr(part, "text"):
                parts.append(getattr(part, "text"))
        return "".join(parts) if parts else (getattr(response, "content", "") or "")


class LLMService:
    """Factory class to create and manage LLM providers."""
    
    def __init__(self):
        self.provider = self._initialize_provider()
    
    def _initialize_provider(self) -> LLMProvider:
        """Initialize the appropriate LLM provider based on environment settings."""
        provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
        
        if provider_name == "claude":
            if not os.getenv("CLAUDE_API_KEY"):
                raise ValueError("CLAUDE_API_KEY environment variable not set")
            return ClaudeProvider()
        else:  # default to OpenAI
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY environment variable not set")
            return OpenAIProvider()
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> str:
        """Generate chat completion using the configured provider."""
        return self.provider.chat_completion(messages, max_tokens, temperature)
    
    def vision_completion(
        self,
        messages: List[Dict[str, Union[str, List[Dict[str, Union[str, Dict[str, str]]]]]]],
        max_tokens: int = 4000,
        temperature: float = 0.3
    ) -> str:
        """Generate completion for vision tasks using the configured provider."""
        return self.provider.vision_completion(messages, max_tokens, temperature)