# src/config.py

from dataclasses import dataclass

@dataclass(frozen=True)
class ReasoningConfig:
    confidence_threshold: float = 0.7       # ниже → второй think()
    max_think_tokens: int = 4096
    adversarial_validation: bool = True     # False = быстрый режим для демо

@dataclass(frozen=True)  
class ModelConfig:
    model: str = "gemma4:e4b"
    host: str = "http://localhost:11434"
    timeout: int = 120
    num_ctx: int = 8192
    retry_attempts: int = 3

# Глобальные инстансы — импортируй их везде
REASONING_CONFIG = ReasoningConfig()
MODEL_CONFIG = ModelConfig()