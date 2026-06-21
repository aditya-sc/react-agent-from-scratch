import requests
from pprint import pprint
# from abc import ABC, abstractmethod 

# curl http://localhost:11434/api/generate -d '{
#   "model": "gemma4",
#   "prompt": "Why is the sky blue?"
# }'



class LLMModel:
    def __init__(self, base_url:str, model:str):
        self.base_url=base_url
        self.model=model
        self.message_map={}

    def chat(self, messages):
        """Sends a direct http POST to Ollama instance"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stop": ["Observation:"]
        }
        response = requests.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]

def get_model(provider:str="", model_name:str="qwen3:8b") -> LLMModel:
    """
    Factory function initializing model instance
    NOTE: Supports only local ollama instance
    """
    return LLMModel(base_url="http://localhost:11434/v1", model=model_name)

