# PassportAI — Порядок реализации v2

# Архитектурная ревизия: агентная система с Gemma 4 native function calling

# + Anti-hallucination architecture (двухфазный контракт, Evidence enum, cross-consistency)

> **Ключевое отличие от v1:** BaseAgent переносится в Неделю 1.
> Gemma 4 имеет нативный function calling через `tools=[]` в Ollama API.
> Вся агентная система строится на этом контракте с первого шага.

## Правило: Test-as-you-go

После каждого шага — запусти тест. Не переходи к следующему шагу если тест не прошёл.

---

## НЕДЕЛЯ 1: Агентный фундамент (13–19 апреля)

Цель: BaseAgent + GemmaClient с нативным tool calling + первый рабочий агент (текст → JSON-LD)

### Шаг 1.1 — Ollama + модель (День 1)

Задача: убедиться что Gemma 4 запускается локально
Файлы: нет (только shell)

```bash
ollama pull gemma4:e4b
ollama run gemma4:e4b "Hello, respond with JSON: {\"status\": \"ok\"}"
```

Тест пройден: получили JSON в ответе

---

### Шаг 1.2 — GemmaClient с нативным tool calling (День 1-2)

Файл: `src/core/gemma_client.py`

> ⚠️ ИЗМЕНЕНИЕ vs v1: добавить метод `call_tool()` который использует `tools=[]` параметр
> Ollama API. Это нативный механизм Gemma 4 — надёжнее любого prompt-JSON parsing.

> ⚠️ ПРОВЕРКА ПЕРВЫМ ДЕЛОМ (совет от Gemini — верный): до написания BaseAgent
> запусти диагностический скрипт ниже. Если Ollama SDK не возвращает `tool_calls` —
> `call_tool()` автоматически упадёт в `_parse_json_fallback()`. Это нормально.
> BaseAgent пишется одинаково в обоих случаях — fallback прозрачен для агентов.

```bash
# Диагностика tool_calls поддержки — запустить ДО шага 1.3
python -c "
import ollama
client = ollama.Client(host='http://localhost:11434')
resp = client.chat(
    model='gemma4:e4b',
    messages=[{'role': 'user', 'content': 'Extract: cotton bag'}],
    tools=[{'type': 'function', 'function': {
        'name': 'test', 'description': 'test',
        'parameters': {'type': 'object', 'properties': {'material': {'type': 'string'}}, 'required': ['material']}
    }}]
)
has_tool_calls = hasattr(resp, 'message') and hasattr(resp.message, 'tool_calls') and bool(resp.message.tool_calls)
print('Native tool_calls:', 'YES - нативный путь активен' if has_tool_calls else 'NO - будет использован _parse_json_fallback')
"
```

Методы:

- `generate(prompt) → str` — текстовый ответ (уже есть)
- `think(prompt) → str` — режим рассуждения (уже есть)
- `analyze_image(image_path, prompt) → str` — vision (уже есть)
- `call_tool(prompt, tools: list[dict], system_prompt: str | None) → dict` — **НОВЫЙ**

Реализация `call_tool()`:

````python
def call_tool(
    self,
    prompt: str,
    tools: list[dict],
    system_prompt: str | None = None,
) -> dict:
    """Call Gemma 4 with native function calling via Ollama tools= parameter.

    Returns the parsed tool_calls dict from the model response.
    Falls back to _parse_json_response() if model returns text instead of tool call.

    Args:
        prompt: User prompt describing the task.
        tools: List of tool definitions in OpenAI function calling format.
        system_prompt: Optional system context for the agent.

    Returns:
        dict: Parsed arguments from the first tool call.

    Example tools format:
        [{
            "type": "function",
            "function": {
                "name": "extract_product_attributes",
                "description": "Extract product attributes from description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "materials": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["category", "materials"]
                }
            }
        }]
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("prompt must not be empty")

    messages: list[ChatMessage] = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=clean_prompt))

    logger.info("Calling tool with model=%s tools=%s", self.model, [t["function"]["name"] for t in tools])

    for attempt in range(1, self.RETRY_ATTEMPTS + 1):
        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                options={"num_ctx": self.DEFAULT_NUM_CTX, "temperature": 0.1},
            )
            # Gemma 4 native tool call response
            if hasattr(response, "message") and hasattr(response.message, "tool_calls"):
                tool_calls = response.message.tool_calls
                if tool_calls:
                    first_call = tool_calls[0]
                    if hasattr(first_call, "function"):
                        return dict(first_call.function.arguments)
            # Fallback: model returned text — parse as JSON
            text = self._extract_text_from_chat_response(response)
            return self._parse_json_fallback(text)
        except Exception as exc:
            logger.warning("call_tool attempt %d/%d failed: %s", attempt, self.RETRY_ATTEMPTS, exc)
            if attempt == self.RETRY_ATTEMPTS:
                raise GemmaResponseError(f"call_tool failed after {self.RETRY_ATTEMPTS} attempts") from exc
            time.sleep(self.RETRY_DELAY_SECONDS * (self.RETRY_BACKOFF_FACTOR ** (attempt - 1)))

def _parse_json_fallback(self, raw: str) -> dict:
    """Parse JSON from model text response (fallback when tools= not triggered).

    Strips markdown code fences and returns parsed dict.
    Used as fallback in call_tool() when model returns text instead of tool call.
    """
    import json, re
    # Remove markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as exc:
        raise GemmaResponseError(f"Model returned invalid JSON: {raw[:200]}") from exc
````

Тест:

```bash
python -c "
from src.core.gemma_client import GemmaClient
c = GemmaClient()
# Test 1: basic generate
print(c.generate('Say OK'))
# Test 2: call_tool (native function calling)
result = c.call_tool(
    prompt='Product: cotton tote bag, made in Ukraine',
    tools=[{
        'type': 'function',
        'function': {
            'name': 'extract_product',
            'description': 'Extract product info',
            'parameters': {
                'type': 'object',
                'properties': {
                    'category': {'type': 'string'},
                    'materials': {'type': 'array', 'items': {'type': 'string'}}
                },
                'required': ['category', 'materials']
            }
        }
    }]
)
print('Tool result:', result)
assert 'materials' in result
print('call_tool OK')
"
```

Тест пройден: `call_tool OK` и `materials` в результате

---

### Шаг 1.3 — BaseAgent (День 2) ← ПЕРЕНЕСЁН ИЗ 3.1 + ДВУХФАЗНЫЙ КОНТРАКТ

Файл: `agents/base_agent.py`

> ⚠️ КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: BaseAgent теперь в Неделе 1, ДО любых агентов.
> Это контракт для всей агентной системы. Все агенты (VisionAgent, RegulatoryConsultant,
> LegalAgent, LCASpecialist, DataAuditAgent, GS1Specialist) наследуют именно этот класс.
>
> ⚠️ НОВОЕ: метод `run_verified_task()` — двухфазный контракт anti-hallucination.
> Phase 1: think() — модель показывает рассуждение, ищет противоречия.
> Phase 2: call_tool() — структурирует ТОЛЬКО то, о чём уже «подумала».
> Используй для агентов с регуляторными данными (Regulatory, Legal).
> Для Vision и LCA — обычный call_tool() (там данные детерминированы иначе).

```python
from abc import ABC, abstractmethod
import logging
from typing import Any
from src.core.gemma_client import GemmaClient


class BaseAgent(ABC):
    """Base class for all PassportAI agents.

    Provides:
    - Standard __init__ with GemmaClient
    - Abstract run() method — each agent implements its own logic
    - call_tool() shortcut — Gemma 4 native function calling
    - run_verified_task() — двухфазный think→call_tool для регуляторных агентов
    - _parse_json_fallback() — fallback для text responses
    - Logging with agent class name
    """

    def __init__(self, client: GemmaClient) -> None:
        self.client = client
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def run(self, **kwargs) -> dict[str, Any]:
        """Execute the agent's task. Must be implemented by subclasses."""
        ...

    def call_tool(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
    ) -> dict:
        """Single-phase: direct call_tool. Use for Vision, LCA, GS1."""
        return self.client.call_tool(prompt, tools, system_prompt)

    def run_verified_task(
        self,
        prompt: str,
        tools: list[dict],
        system_prompt: str | None = None,
    ) -> dict:
        """Two-phase anti-hallucination contract.

        Phase 1 — think(): model reasons about the input, surfaces
        contradictions, cites regulation knowledge before committing.
        Phase 2 — call_tool(): structures ONLY what was reasoned in Phase 1.

        Use for: RegulatoryConsultant, LegalAgent.
        Do NOT use for: VisionAgent (visual facts), LCASpecialist (lookup table),
        GS1Specialist (deterministic math).

        Why this works: if the model's thinking says one thing and the tool
        call says another — that contradiction is visible in logs.
        Self-correction before output, not after.
        """
        self.logger.info("%s: Phase 1 — thinking", self.__class__.__name__)
        thinking_result = self.client.think(prompt)
        self.logger.debug("%s: thinking output: %s", self.__class__.__name__, thinking_result[:300])

        # Phase 2: inject thinking result into call_tool prompt
        verified_prompt = (
            f"{prompt}\n\n"
            f"[Internal analysis completed. Key reasoning:]\n{thinking_result}\n\n"
            f"Now structure the above analysis into the required format."
        )
        self.logger.info("%s: Phase 2 — structuring via call_tool", self.__class__.__name__)
        return self.client.call_tool(verified_prompt, tools, system_prompt)

    def think(self, prompt: str) -> str:
        """Delegate to GemmaClient.think() — extended reasoning mode."""
        return self.client.think(prompt)

    def _parse_json_fallback(self, raw: str) -> dict:
        """Delegate to GemmaClient._parse_json_fallback()."""
        return self.client._parse_json_fallback(raw)
```

Тест:

```bash
python -c "
from agents.base_agent import BaseAgent
from src.core.gemma_client import GemmaClient

class TestAgent(BaseAgent):
    def run(self, **kwargs): return {'ok': True}

a = TestAgent(None)
# Test 1: _parse_json_fallback

ok = a._format_success({'ok': True})
assert ok['success'] is True
assert ok['agent'] == 'TestAgent'

err = a._format_error('boom')
assert err['success'] is False
assert err['agent'] == 'TestAgent'

print('AgentResult contract OK')
# Test 2: run_verified_task exists and is callable
assert callable(getattr(a, 'run_verified_task', None))
print('run_verified_task OK')
print('BaseAgent v2.1 OK')
"
```

Тест пройден: `BaseAgent v2.1 OK`

---

### Шаг 1.4 — DPP Schema (День 2)

Файл: `schemas/universal_dpp.json`
Задача: базовая JSON схема пустого DPP (все поля, типы, required)
(без изменений vs v1)

Тест:

```bash
python -c "import json; s=json.load(open('schemas/universal_dpp.json')); print('OK', len(s))"
```

---

### Шаг 1.5 — DPPGenerator (текст only) (День 3)

Файл: `src/core/dpp_generator.py` + `prompts/dpp_generation.txt`

> ⚠️ ИЗМЕНЕНИЕ vs v1: DPPGenerator теперь использует `client.call_tool()` вместо
> `client.generate()` + ручного JSON parsing. Schema для DPP передаётся как tool definition.
> Если DPPGenerator вырастет до God Object — переименовать в DPPOrchestrator
> и вынести pipeline-логику в `src/core/pipeline.py` (шаг 3.0 ниже).

Метод: `generate_from_text(description: str) → dict`

Пример с нативным tool calling:

```python
DPP_TOOL = [{
    "type": "function",
    "function": {
        "name": "create_dpp_passport",
        "description": "Create EU Digital Product Passport in VCDM 2.0 JSON-LD format",
        "parameters": {
            "type": "object",
            "properties": {
                "@context": {"type": "array"},
                "type": {"type": "array"},
                "credentialSubject": {
                    "type": "object",
                    "properties": {
                        "productName": {"type": "string"},
                        "materialComposition": {"type": "array"},
                        "countryOfManufacture": {"type": "string"},
                        "gwp_kg_co2e": {"type": "number"}
                    }
                }
            },
            "required": ["@context", "type", "credentialSubject"]
        }
    }
}]

def generate_from_text(self, description: str) -> dict:
    return self.client.call_tool(
        prompt=f"Create a DPP passport for: {description}",
        tools=DPP_TOOL,
        system_prompt="You are an EU DPP expert. Generate ESPR-compliant Digital Product Passports."
    )
```

```
# DPPGenerator — два слоя

# Слой 1: Python владеет структурой (неизменно)
BASE_TEMPLATE = {
    "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://passportai.io/contexts/dpp/v1"
    ],
    "type": ["VerifiableCredential", "DigitalProductPassport"],
    "issuer": "did:web:passportai.io",
    "credentialSubject": {
        "type": "ProductPassport",
        "productIdentifier": None,   # ← GS1Specialist заполнит
        "manufacturer": None,        # ← user_input
        "materialComposition": [],   # ← VisionAgent + user_input
        "countryOfManufacture": None,
        "gwp_kg_co2e": None,         # ← LCASpecialist заполнит
        "sustainabilityScore": None,
        "repairabilityScore": None,
        "endOfLifeInstructions": None,
    }
}

# Слой 2: LLM возвращает ТОЛЬКО значения (филлы)
FILL_TOOL = [{
    "type": "function",
    "function": {
        "name": "fill_product_fields",
        "description": "Extract product field values only. No JSON-LD structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "productName":          {"type": "string"},
                "materialComposition":  {"type": "array", "items": {"type": "string"}},
                "countryOfManufacture": {"type": "string"},
                "description":          {"type": "string"},
            },
            "required": ["productName", "materialComposition"]
        }
    }
}]

# Слой 3: Python собирает финальный паспорт
def build_passport(self, fills: dict) -> dict:
    passport = copy.deepcopy(BASE_TEMPLATE)
    passport["id"] = f"urn:uuid:{uuid4()}"
    passport["issuanceDate"] = datetime.utcnow().isoformat() + "Z"
    # Каждый агент вносит свои поля
    cs = passport["credentialSubject"]
    cs["productName"] = fills.get("productName")
    cs["materialComposition"] = fills.get("materialComposition", [])
    # ... и т.д.
    return passport
```

Тест:

```bash
python -c "
from src.core.gemma_client import GemmaClient
from src.core.dpp_generator import DPPGenerator
client = GemmaClient()
gen = DPPGenerator(client)
passport = gen.generate_from_text('Cotton tote bag, made in Ukraine')
print(passport.get('@context'))
print(passport.get('type'))
"
```

Тест пройден: `@context` и `type` содержит `VerifiableCredential`

---

### Шаг 1.6 — JSON-LD валидация + офлайн кэш (День 3)

(без изменений vs v1 — pyld + local documentLoader)

---

### Шаг 1.7 — Промпт refinement в Colab (День 3-4)

(без изменений vs v1 — T4 GPU, 10 итераций, финальный тест локально)

---

### Шаг 1.8 — StorageProvider интерфейс (День 4-5) ← ПЕРЕНЕСЁН ИЗ 3.8

Файлы: `src/storage/base.py`, `src/storage/local.py`

> ⚠️ ПЕРЕНОС ИЗ 3.8: Storage — чистый интерфейс без зависимости от агентов или UI.
> Pipeline (шаг 3.0) не может генерировать URL для QR-кода без Storage.
> LocalStorage нужен раньше чем QR Generator.
> AWS S3 реализацию пишем позже (неделя 3 или 4), но интерфейс фиксируем сейчас.

```python
class StorageProvider(ABC):
    def save_package(self, passport_id: str, files: dict[str, Path]) -> str: ...
    def get_public_url(self, passport_id: str, filename: str) -> str: ...
```

Тест LOCAL:

```bash
python -c "
from src.storage.local import LocalStorage
from pathlib import Path
s = LocalStorage(output_dir='./output', hosting_url='http://localhost:8000')
url = s.save_package('test-uuid-123', {'passport.json': Path('DPP_SCHEMA.json')})
print('URL:', url)
import os
assert os.path.exists('./output/test-uuid-123/passport.json')
print('Local storage OK')
"
```

### Шаг 1.9 — Базовый скелет app.py (День 5)

(без изменений vs v1 — только проверка импортов)

**ИТОГ НЕДЕЛИ 1:**

- ✅ BaseAgent — контракт агентной системы
- ✅ GemmaClient с нативным call_tool()
- ✅ DPPGenerator использует native function calling
- ✅ StorageProvider интерфейс зафиксирован
- ✅ `python -c "..."` генерирует JSON-LD DPP из текстового описания

---

## НЕДЕЛЯ 2: Multimodal (20–26 апреля)

Цель: фото + текст → JSON-LD + стандартизированное фото

### Шаг 2.1 — analyze_image() в GemmaClient (День 1-2)

(без изменений vs v1 — уже реализован в gemma_client_clean.py)

---

### Шаг 2.2 — VisionAgent (День 2-3) ← ПЕРЕИМЕНОВАН И ПЕРЕМЕЩЁН

Файлы: `agents/vision_agent.py` + `prompts/vision_analysis.txt`

> ⚠️ ИЗМЕНЕНИЕ vs v1: файл ТЕПЕРЬ в `agents/`, НЕ в `src/core/vision.py`.
> VisionAgent наследует BaseAgent (уже готов из шага 1.3).
> Метод run() использует client.call_tool() с нативным tool calling.

```python
from agents.base_agent import BaseAgent

VISION_TOOL = [{
    "type": "function",
    "function": {
        "name": "extract_product_attributes",
        "description": "Extract product attributes from image analysis",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["textiles", "electronics", "furniture", "packaging"]},
                "materials": {"type": "array", "items": {"type": "string"}},
                "colors": {"type": "array", "items": {"type": "string"}},
                "dimensions_estimate": {
                    "type": "object",
                    "properties": {
                        "width_cm": {"type": "number"},
                        "height_cm": {"type": "number"}
                    }
                },
                "certifications_visible": {"type": "array", "items": {"type": "string"}},
                "special_markings": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["category", "materials", "colors"]
        }
    }
}]

class VisionAgent(BaseAgent):
    def run(self, image_path: str, description: str = "") -> dict:
        # Step 1: analyze image (vision capability)
        image_description = self.client.analyze_image(
            image_path,
            "Describe all visible product attributes: materials, colors, markings, dimensions"
        )
        # Step 2: extract structured attributes via native tool call
        combined_prompt = f"Image analysis: {image_description}\nUser description: {description}"
        return self.call_tool(
            prompt=combined_prompt,
            tools=VISION_TOOL,
            system_prompt="You are a product attribute extraction specialist for EU compliance."
        )

    # Keep legacy method name for backward compatibility with DPPGenerator
    def extract_product_attributes(self, image_path: str, description: str) -> dict:
        return self.run(image_path=image_path, description=description)
```

Тест: запустить на фото шопера Brand → `category == "textiles"`

---

### Шаг 2.3 — PhotoProcessor (День 2)

Файл: `src/processing/photo.py`

> Примечание: это НЕ агент — нет LLM, только PIL + rembg.
> Правильное имя: PhotoProcessor, не PhotoAgent.
> (без изменений vs v1)

---

### Шаг 2.4 — Merge функция (День 3)

(без изменений vs v1 — user_input всегда приоритет над vision_output)

---

### Шаг 2.5 — Интегрированный pipeline фото+текст (День 4-5)

(без изменений vs v1 — generate_from_photo_and_text)

**ИТОГ НЕДЕЛИ 2:** одна функция принимает фото + текст → JSON-LD + стандартизированное фото

---

## НЕДЕЛЯ 3: Full DPP Package (27 апр – 3 мая)

Цель: все 5 агентов работают, полный `output/{uuid}/` пакет

> Примечание: BaseAgent уже готов (шаг 1.3). VisionAgent уже готов (шаг 2.2).
> На этой неделе только 4 новых агента + Pipeline + отчёты.

### Шаг 3.0 — PassportPipeline / DPPOrchestrator (День 1) ← НОВЫЙ ШАГ

Файл: `src/core/pipeline.py`

> ⚠️ НОВЫЙ ШАГ которого не было в v1.
> DPPGenerator рискует стать God Object (4+ методов, все разные ответственности).
> PassportPipeline — единственный класс который знает ПОРЯДОК шагов.
> Он не вычисляет — он координирует. Это и есть архитектура агентной системы.

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class PipelineResult:
    """Typed result of passport generation pipeline.

    Replaces untyped dict that was previously passed to Gradio UI.
    Gradio receives this object — fields are explicit, not magic strings.
    """
    passport_id: str
    passport_json: dict[str, Any]
    readiness_score: int
    missing_essential: list[str]
    missing_recommended: list[str]
    legal_flags: list[str]
    gwp_kg_co2e: float | None
    gwp_confidence: float | None
    files: dict[str, Path] = field(default_factory=dict)
    public_url: str | None = None
    errors: list[str] = field(default_factory=list)


class PassportPipeline:
    """Orchestrates the full DPP generation pipeline.

    Knows the order of steps. Does not compute — delegates to agents.
    Single source of truth for: what runs, in what order, with what data.

    Step order (deterministic):
    1. VisionAgent + PhotoProcessor — ПАРАЛЛЕЛЬНО (asyncio.gather)
       VisionAgent: LLM (медленно, ждёт модель)
       PhotoProcessor: rembg CPU (независимо от LLM)
    2. DPPGenerator — generate draft passport
    3. RegulatoryConsultant — ESPR classification (run_verified_task: think→call_tool)
    4. LegalAgent — compliance flags (run_verified_task: think→call_tool)
    5. LCASpecialist — carbon footprint (call_tool + lookup table)
    6. DataAuditAgent — readiness score + cross_agent_consistency_check
    7. GS1Specialist — GS1 Digital Link + DID (детерминированный)
    8. GapReportGenerator — PDF (включает conflicts из DataAuditAgent)
    9. StorageProvider — save package, get public URL
    10. QRGenerator — ПОСЛЕДНИЙ (нужен финальный URL из Storage)
    """

    def __init__(self, agents: dict, storage: StorageProvider):
        self.agents = agents
        self.storage = storage

    async def run(self, image_path: str | None, description: str, user_inputs: dict) -> PipelineResult:
        """Run full pipeline. Async to support parallel Vision+Photo step."""
        import asyncio

        # Step 1: PARALLEL — Vision (LLM) + Photo (CPU rembg), independent
        vision_task = asyncio.create_task(
            asyncio.to_thread(self.agents['vision'].run, image_path, description)
        ) if image_path else None
        photo_task = asyncio.create_task(
            asyncio.to_thread(self.agents['photo'].standardize_photo, image_path)
        ) if image_path else None

        vision_result = await vision_task if vision_task else {}
        photo_path = await photo_task if photo_task else None

        # Steps 2-10: sequential (each depends on previous)
        ...
```

Тест: инстанциировать PassportPipeline с mock агентами → проверить что Vision и Photo вызываются параллельно

---

### Шаг 3.1 — RegulatoryConsultant (День 1-2)

Наследует BaseAgent. Использует **`run_verified_task()`** (двухфазный).

> Почему двухфазный: дедлайны ESPR регуляций (2026, 2027, 2030) — это конкретные факты.
> Если модель «думает» перед ответом, она цитирует свои знания о регуляциях явно.
> Если в thinking написано «2027» а в tool call «2025» — это флаг для проверки.

Выход обязательно содержит `evidence` блок (см. стандарт ниже).

---

### Шаг 3.2 — LegalAgent (День 2)

Наследует BaseAgent. Использует **`run_verified_task()`** (двухфазный).

> Почему двухфазный: REACH SVHC список, RoHS директива, CE требования —
> модель должна «вспомнить» основание перед тем как поставить флаг.
> Ложноположительный флаг REACH хуже чем отсутствие флага — он пугает клиента.

Выход обязательно содержит `evidence` блок (см. стандарт ниже).

---

### Шаг 3.3 — LCASpecialist (День 2-3)

(без изменений vs v1, lookup table gwp_coefficients.csv + call_tool())

---

### Шаг 3.4 — DataAuditAgent (День 3) ← РАСШИРЕН: cross-consistency check

Наследует BaseAgent. Использует **детерминированную логику** (не LLM для сравнения).

> ⚠️ DataAuditAgent теперь последний перед GapReport — он получает результаты
> ВСЕХ предыдущих агентов и проверяет согласованность. Это не LLM задача —
> это Python сравнение dict значений. Надёжно и быстро.

```python
def cross_agent_consistency_check(
    self,
    vision_result: dict,
    dpp_draft: dict,
    regulatory_result: dict,
    strict_mode: bool = False,  # False = флаг в Gap Report, True = блокировка
) -> dict:
    """Deterministic consistency check across agent outputs.

    Compares key attributes between agents — no LLM involved.
    strict_mode=False (default): flags conflicts, does NOT block pipeline.
    strict_mode=True: raises ConsistencyError, blocks QR generation.

    For MVP demo: always use strict_mode=False.
    For production: set strict_mode=True.
    """
    conflicts = []

    # Check 1: category consistency
    vision_cat = vision_result.get("category", "").lower()
    reg_cat = regulatory_result.get("espr_category", "").lower()
    if vision_cat and reg_cat and vision_cat != reg_cat:
        conflicts.append({
            "field": "category",
            "vision": vision_cat,
            "regulatory": reg_cat,
            "message": f"VisionAgent detected '{vision_cat}' but RegulatoryConsultant classified as '{reg_cat}'"
        })

    # Check 2: materials consistency (intersection check)
    vision_mats = set(m.lower() for m in vision_result.get("materials", []))
    dpp_mats_raw = dpp_draft.get("credentialSubject", {}).get("materialComposition", [])
    dpp_mats = set(m.lower() if isinstance(m, str) else str(m).lower() for m in dpp_mats_raw)
    if vision_mats and dpp_mats and vision_mats.isdisjoint(dpp_mats):
        conflicts.append({
            "field": "materials",
            "vision": list(vision_mats),
            "dpp_draft": list(dpp_mats),
            "message": "No material overlap between VisionAgent and DPPGenerator outputs"
        })

    if conflicts and strict_mode:
        raise ConsistencyError(f"Pipeline blocked: {len(conflicts)} data conflicts detected", conflicts)

    return {
        "conflict_detected": len(conflicts) > 0,
        "conflicts": conflicts,
        "strict_mode": strict_mode,
    }
```

Выход DataAuditAgent (расширенный):

```json
{
  "readiness_score": 54,
  "missing_essential": ["manufacturer", "materialComposition"],
  "missing_recommended": ["recycledContent", "waterConsumption"],
  "inconsistencies": [],
  "warnings": ["countryOfManufacture not matching facilityId.address"],
  "conflict_detected": false,
  "conflicts": []
}
```

Тест:

```bash
python -c "
from agents.data_audit_agent import DataAuditAgent
agent = DataAuditAgent(None)
# Test: vision says textiles, regulatory says electronics → conflict
result = agent.cross_agent_consistency_check(
    vision_result={'category': 'textiles', 'materials': ['cotton']},
    dpp_draft={'credentialSubject': {'materialComposition': ['polyester']}},
    regulatory_result={'espr_category': 'electronics'},
    strict_mode=False
)
assert result['conflict_detected'] == True
assert len(result['conflicts']) == 2  # category + materials
print('cross_agent_consistency_check OK — conflicts flagged, pipeline not blocked')
"
```

---

### Шаг 3.5 — GS1Specialist (День 3-4)

(без изменений vs v1, GTIN validation + DID + digital link)

---

### Шаг 3.6 — GapReportGenerator (День 4)

(без изменений vs v1, jinja2 + weasyprint → PDF)

---

### Шаг 3.7 — AWS S3 Storage (День 4-5) ← ТОЛЬКО S3, интерфейс уже есть

Файл: `src/storage/aws_s3.py`

> LocalStorage уже написан в шаге 1.8. Здесь только S3 реализация.

---

### Шаг 3.8 — QR Generator (День 5) ← ВСЕГДА ПОСЛЕДНИЙ

Файл: `src/processing/qr.py`
(без изменений vs v1 — QR генерируется только после Storage.get_public_url())

**ИТОГ НЕДЕЛИ 3:** end-to-end тест: фото Brand → полный `output/{uuid}/` со всеми 5 файлами

---

## НЕДЕЛЯ 4: UI + Demo (4–10 мая)

(без изменений vs v1 — FastAPI + Gradio + Brand тест + видео)

### Шаг 4.1 — FastAPI Passport Server

### Шаг 4.2 — Gradio UI

### Шаг 4.3 — app.py финальный (gr.mount_gradio_app pattern)

### Шаг 4.4 — Тест с Brand ← КРИТИЧЕСКИЙ

### Шаг 4.5 — Демо-видео (OBS Studio, 3 минуты)

---

## НЕДЕЛЯ 5: Submit (11–18 мая)

(без изменений vs v1)

### Шаг 5.1 — GitHub README

### Шаг 5.2 — Kaggle Writeup (1500 слов)

### Шаг 5.3 — Live Demo (HF Spaces)

### Шаг 5.4 — Media Gallery (cover 1280x720)

### Шаг 5.5 — Kaggle Submit (17 мая, safety margin)

---

## Сводная таблица изменений v1 → v2.1

| Шаг                  | v1             | v2              | v2.1 (финал)                               | Причина                                             |
| -------------------- | -------------- | --------------- | ------------------------------------------ | --------------------------------------------------- |
| BaseAgent            | Шаг 3.1        | Шаг 1.3         | **+ `run_verified_task()`**                | Двухфазный think→call_tool для регуляторных агентов |
| GemmaClient          | generate()     | + call_tool()   | **+ диагностика SDK перед 1.3**            | Проверить tool_calls до написания BaseAgent         |
| VisionAgent          | `src/core/`    | `agents/`       | **+ параллельный запуск с PhotoProcessor** | asyncio.gather экономит 1-2 мин                     |
| StorageProvider      | Шаг 3.8        | Шаг 1.8         | без изменений                              | Нет зависимостей                                    |
| PassportPipeline     | —              | Шаг 3.0         | **async run() с parallel step 1**          | Vision+Photo параллельно                            |
| PipelineResult       | `dict`         | dataclass       | без изменений                              | Типизированный выход                                |
| DPP generation       | prompt+parsing | native tools=   | без изменений                              | Надёжнее                                            |
| RegulatoryConsultant | промпт         | call_tool()     | **run_verified_task()**                    | Факты регуляций через thinking                      |
| LegalAgent           | промпт         | call_tool()     | **run_verified_task()**                    | REACH флаги через thinking                          |
| DataAuditAgent       | поля missing   | readiness_score | **+ cross_agent_consistency_check()**      | Детерминированное сравнение агентов                 |
| All tool schemas     | нет confidence | —               | **+ `evidence.source_type` enum**          | Машиночитаемый источник данных                      |

---

## Архитектурная диаграмма (текстовая)

```
Неделя 1:
  GemmaClient ──→ call_tool() [native] + _parse_json_fallback() [fallback]
       │         ↑ диагностика SDK ПЕРВЫМ ДЕЛОМ (шаг 1.2)
  BaseAgent ──→ run() [abstract] + run_verified_task() [think→call_tool]
       │
  DPPGenerator ──→ call_tool() с DPP JSON Schema как tool definition
       │
  StorageProvider (interface) + LocalStorage

Неделя 2:
  VisionAgent(BaseAgent) ──→ analyze_image() → call_tool(VISION_TOOL)
  PhotoProcessor ──→ rembg + PIL (не LLM, не агент)

Неделя 3:
  PassportPipeline.run() [async] координирует:
    ┌─────────────────────────────────────────────┐
    │ ПАРАЛЛЕЛЬНО (asyncio.gather):               │
    │  VisionAgent [LLM]  +  PhotoProcessor [CPU] │
    └─────────────────────────────────────────────┘
         ↓
    DPPGenerator [call_tool]
         ↓
    RegulatoryConsultant [run_verified_task: think→call_tool]
         ↓
    LegalAgent [run_verified_task: think→call_tool]
         ↓
    LCASpecialist [call_tool + lookup_table CSV]
         ↓
    DataAuditAgent [детерминированный + cross_agent_consistency_check]
         ↓
    GS1Specialist [детерминированный]
         ↓
    GapReportGenerator [PDF + conflicts из DataAuditAgent]
         ↓
    Storage.save_package() → public_url
         ↓
    QRGenerator [ПОСЛЕДНИЙ — нужен URL]

  Каждый агентный выход содержит evidence.source_type + evidence.confidence
  PipelineResult (dataclass) ──→ типизированный выход в Gradio

Неделя 4:
  FastAPI + Gradio ──→ принимает PipelineResult, отдаёт UI

Неделя 5:
  Submit: writeup + video + github + demo + cover
```

---

## Критические заметки по Gemma 4 E4B

1. **Диагностика tool_calls ПЕРВЫМ ДЕЛОМ** (шаг 1.2) — запусти скрипт до написания BaseAgent. Если `tool_calls` нет — `call_tool()` автоматически использует `_parse_json_fallback()`. Поведение одинаково для всех агентов.

2. **think= и tools= конфликтуют** — не используй одновременно. `run_verified_task()` решает это правильно: сначала `think()` (отдельный вызов), потом `call_tool()` (отдельный вызов). Два вызова — не баг, это контракт.

3. **128K контекст E4B** — используй для RegulatoryConsultant и LegalAgent где нужен полный ESPR контекст. DPP generation: 8192 токенов достаточно.

4. **Локальная скорость** — 8-12 tokens/sec на CPU. `run_verified_task()` = два вызова = ~2x время. Для регуляторных агентов это приемлемо (они запускаются один раз). Параллельный шаг Vision+Photo компенсирует часть потерь.

5. **Evidence блок — стандарт для всех tool schemas** (добавить при написании каждого агента):

```json
"evidence": {
  "type": "object",
  "description": "Source and confidence of this output. Required for audit trail.",
  "properties": {
    "source_type": {
      "type": "string",
      "description": "Where this data comes from. Use: internal_csv (gwp_coefficients.csv), regulation_text (ESPR/REACH/RoHS), visual_analysis (image), user_input (form field), llm_knowledge (model's training data)",
      "enum": ["internal_csv", "regulation_text", "visual_analysis", "user_input", "llm_knowledge"]
    },
    "confidence": {
      "type": "string",
      "description": "Reliability: lookup_table = exact match in CSV, regulation_text = cited from official source, model_estimate = model inference, insufficient_data = not enough info",
      "enum": ["lookup_table", "regulation_text", "model_estimate", "insufficient_data"]
    },
    "reasoning_summary": {
      "type": "string",
      "description": "Optional: brief explanation of the reasoning. Leave empty string if not applicable."
    }
  },
  "required": ["source_type", "confidence"]
}
```

> Примечание: `reasoning_summary` — **optional по смыслу, required по схеме** (пустая строка допустима).
> Это сделано намеренно: если поле optional — модель его пропустит. Пустая строка лучше чем отсутствие поля.
> `confidence` — **enum из 4 значений**, не float. Float confidence — это сама по себе галлюцинация.
