# PassportAI — Порядок реализации

## Правило: Test-as-you-go
После каждого шага — запусти тест. Не переходи к следующему шагу если тест не прошёл.

---

## НЕДЕЛЯ 1: Foundation (13–19 апреля)
Цель: текст → валидный JSON-LD паспорт через Gemma 4

### Шаг 1.1 — Ollama + модель (День 1)
Задача: Убедиться что Gemma 4 запускается локально
Файлы: нет (только shell)
Команды:
```bash
ollama pull gemma4:12b-q4_k_m
ollama run gemma4:12b-q4_k_m "Hello, generate JSON: {name: test}"
```
Тест пройден: получили JSON в ответе

---

### Шаг 1.2 — GemmaClient (День 1-2)
Файл: `src/core/gemma_client.py`
Методы: `__init__()`, `generate(prompt) → str`, `think(prompt) → str`
Тест:
```bash
python -c "from src.core.gemma_client import GemmaClient; c=GemmaClient(); print(c.generate('Say OK'))"
```
Тест пройден: в stdout появилась строка с "OK"

---

### Шаг 1.3 — DPP Schema (День 2)
Файл: `schemas/universal_dpp.json`
Задача: создать базовую JSON схему пустого DPP (все поля, типы, required)
Тест:
```bash
python -c "import json; s=json.load(open('schemas/universal_dpp.json')); print('OK', len(s))"
```
Тест пройден: "OK" + число ключей > 0, нет ошибки парсинга

---

### Шаг 1.4 — DPP Generator (текст only) (День 2-3)
Файлы: `src/core/dpp_generator.py` + `prompts/dpp_generation.txt`
Метод: `generate_from_text(description: str) → dict`
Тест: сгенерировать DPP для "Cotton tote bag, made in Ukraine"
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
Тест пройден: в выводе есть `@context` и `type` содержит `VerifiableCredential`

---

### Шаг 1.5 — JSON-LD валидация + офлайн кэш контекстов (День 3)

> ⚠️ ВАЖНО: pyld по умолчанию скачивает @context из интернета (schema.org, w3.org).
> В airplane mode это упадёт с ошибкой. Нужен локальный documentLoader.

Файл: добавить в `dpp_generator.py` метод `validate(passport: dict) → tuple[bool, list]`
Файл: добавить `src/utils/jsonld_loader.py` — локальный documentLoader для pyld

Реализация локального загрузчика:
```python
# src/utils/jsonld_loader.py
from pathlib import Path
import json

CONTEXT_DIR = Path("contexts")

CONTEXT_MAP = {
    "https://www.w3.org/ns/credentials/v2": "w3c_credentials_v2.jsonld",
    "https://schema.org": "schema_org.jsonld",
    "https://schema.org/": "schema_org.jsonld",
    "https://www.gs1.org/voc/": "gs1_voc.jsonld",
}

def local_document_loader(url, options={}):
    """Loads JSON-LD contexts from local cache. Falls back to network if not cached."""
    if url in CONTEXT_MAP:
        file_path = CONTEXT_DIR / CONTEXT_MAP[url]
        if file_path.exists():
            return {
                "url": url,
                "document": json.loads(file_path.read_text()),
                "contextUrl": None
            }
    # fallback to network (only when online)
    from pyld.documentloader.requests import requests_document_loader
    return requests_document_loader()(url, options)
```

Использование в validate():
```python
from pyld import jsonld
from src.utils.jsonld_loader import local_document_loader

def validate(self, passport: dict) -> tuple[bool, list]:
    errors = []
    try:
        jsonld.set_document_loader(local_document_loader)
        expanded = jsonld.expand(passport)
        if not expanded:
            errors.append("Empty after JSON-LD expansion")
    except Exception as e:
        errors.append(f"JSON-LD error: {e}")
    return len(errors) == 0, errors
```

Зависимость:
```bash
pip install pyld requests
```
Тест:
```bash
python -c "
from src.core.gemma_client import GemmaClient
from src.core.dpp_generator import DPPGenerator
client = GemmaClient()
gen = DPPGenerator(client)
passport = gen.generate_from_text('Cotton tote bag')
ok, errors = gen.validate(passport)
print('Valid:', ok, '| Errors:', errors)
"
```
Тест пройден: `Valid: True | Errors: []`

---

### Шаг 1.6 — Промпт refinement в Colab (День 3-4)
Файл: `prompts/dpp_generation.txt`
Задача: в Google Colab (GPU) прогнать 10 итераций промпта на разных описаниях
Критерий качества: 8/10 запусков возвращают валидный JSON без markdown-обёртки
Инструмент: Colab T4 GPU (бесплатно) + тот же Ollama через API
Метрика: считать долю успешных `json.loads()` без вызова `.strip('```json')`

> ⚠️ ВАЖНО (риск Gemini): Промпты оптимизированные на GPU Colab (T4, float16)
> могут давать другой результат на твоём CPU (int4 квантизация).
> После каждой сессии в Colab — обязательно прогони финальный промпт
> локально через Ollama на ноутбуке и убедись что результат аналогичный.
> GPU оптимизация = черновик. Локальный тест = финальное подтверждение.

---

### Шаг 1.7 — Базовый скелет app.py (День 4-5)
Файл: `app.py`
Задача: минимальный запуск без UI — просто проверка импортов
Тест:
```bash
python app.py --test
```
Тест пройден: вывод "All imports OK", код выхода 0

**ИТОГ НЕДЕЛИ 1:** `python -c "..."` генерирует JSON-LD DPP из текстового описания

---

## НЕДЕЛЯ 2: Multimodal (20–26 апреля)
Цель: фото + текст → JSON-LD + стандартизированное фото

### Шаг 2.1 — analyze_image() в GemmaClient (День 1-2)
Файл: `src/core/gemma_client.py`
Метод: `analyze_image(image_path: str, prompt: str) → str`
Зависимость: ollama Python SDK поддерживает параметр `images`
Примечание: передаём изображение как base64 через `ollama.chat(images=[...])`
Тест:
```bash
python -c "
from src.core.gemma_client import GemmaClient
c = GemmaClient()
result = c.analyze_image('tests/fixtures/test_product.jpg', 'List materials visible')
print(result[:200])
"
```
Тест пройден: непустая строка, описывает изображение

---

### Шаг 2.2 — Vision Agent (День 2-3)
Файлы: `src/core/vision.py` + `prompts/vision_analysis.txt`
Метод: `extract_product_attributes(image_path: str, description: str) → dict`
Формат вывода:
```json
{
  "category": "textiles",
  "materials": ["cotton"],
  "colors": ["natural", "beige"],
  "dimensions_estimate": {"width_cm": 38, "height_cm": 42},
  "certifications_visible": [],
  "special_markings": []
}
```
Тест: запустить на фото шопера NikSense → получить атрибуты, `category == "textiles"`

---

### Шаг 2.3 — Photo Agent (День 2)
Файл: `src/processing/photo.py`
Зависимости:
```bash
pip install rembg pillow
```
Метод: `standardize_photo(input_path: str | Path) → Path`
Правило: выход всегда 800x800 PNG, белый фон, объект центрирован
Тест:
```bash
python -c "
from src.processing.photo import standardize_photo
out = standardize_photo('tests/fixtures/test_product.jpg')
from PIL import Image
img = Image.open(out)
print(img.size, img.mode)
"
```
Тест пройден: `(800, 800) RGBA` или `(800, 800) RGB`

---

### Шаг 2.4 — Merge функция (День 3)
Файл: `src/core/dpp_generator.py`
Метод: `merge_inputs(vision_output: dict, user_input: dict) → dict`
Правило: **user_input всегда имеет приоритет над vision_output** (не перезаписывать явно введённые пользователем данные)
Тест:
```bash
python -c "
from src.core.dpp_generator import DPPGenerator
gen = DPPGenerator(None)
vision = {'category': 'electronics', 'materials': ['plastic']}
user   = {'category': 'textiles'}
merged = gen.merge_inputs(vision, user)
assert merged['category'] == 'textiles', 'user_input must win'
print('OK: user_input wins on conflict')
"
```
Тест пройден: `OK: user_input wins on conflict`

---

### Шаг 2.5 — Интегрированный pipeline (День 4-5)
Файл: `src/core/dpp_generator.py`
Метод: `generate_from_photo_and_text(image_path: str, description: str) → dict`
Внутренний порядок:
1. `analyze_image()` → vision_attrs
2. `merge_inputs(vision_attrs, {"description": description})` → product_data
3. `generate_from_text(product_data)` → passport
Тест: фото + описание → полный JSON-LD за один вызов
```bash
python -c "
from src.core.gemma_client import GemmaClient
from src.core.dpp_generator import DPPGenerator
client = GemmaClient()
gen = DPPGenerator(client)
passport = gen.generate_from_photo_and_text('tests/fixtures/test_product.jpg', 'Brand tote bag, cotton')
print('Keys:', list(passport.keys()))
"
```
Тест пройден: в ключах есть `@context`, `credentialSubject`

**ИТОГ НЕДЕЛИ 2:** одна функция принимает фото + текст, возвращает JSON-LD + стандартизированное фото

---

## НЕДЕЛЯ 3: Full DPP Package (27 апр – 3 мая)
Цель: все 5 агентов работают, полный `output/{uuid}/` пакет

### Шаг 3.1 — BaseAgent (День 1)
Файл: `agents/base_agent.py`
Методы: `__init__()`, `run() → abstract`, `_parse_json_response(raw: str) → dict`
Тест:
```bash
python -c "
from agents.base_agent import BaseAgent
class TestAgent(BaseAgent):
    def run(self, **kwargs): return {}
a = TestAgent(None)
result = a._parse_json_response('\`\`\`json\n{\"ok\": true}\n\`\`\`')
assert result == {'ok': True}
print('_parse_json_response OK')
"
```
Тест пройден: `_parse_json_response OK`

---

### Шаг 3.2 — Regulatory Consultant (День 1-2)
Файлы: `agents/regulatory_consultant.py` + `prompts/regulatory_classification.txt`
Вход: `product_name, description, photo_attributes`
Выход:
```json
{
  "espr_category": "textiles",
  "required_fields": ["materialComposition", "recycledContent", "durabilityYears"],
  "deadlines": {"mandatory_dpp": "2027-01-01"},
  "applicable_regulations": ["ESPR 2024/1781", "EU Textile Labelling Regulation"]
}
```
Тест: шопер → `espr_category == "textiles"`

---

### Шаг 3.3 — Legal Agent (День 2)
Файлы: `agents/legal_agent.py` + `prompts/legal_review.txt`
Вход: `passport_draft: dict, material_composition: list, espr_category: str`
Выход:
```json
{
  "ce_required": false,
  "doc_present": false,
  "reach_flags": ["neodymium (SVHC candidate)"],
  "rohs_applicable": false,
  "missing_documents": ["OEKO-TEX certificate"],
  "compliance_flags": ["REACH Article 33 disclosure required"]
}
```
Тест: паспорт с `"ABS plastic 70%, neodymium 5%"` → флаг REACH для неодима
```bash
python -c "
from agents.legal_agent import LegalAgent
# ... setup
assert 'neodymium' in str(result.get('reach_flags', []))
print('REACH flag OK')
"
```

---

### Шаг 3.4 — LCA Specialist (День 2-3)

> ⚠️ ВАЖНО: Не позволяй Gemma 4 «придумывать» цифры GWP.
> Судьи спросят «откуда 3.2 kg CO2e?» — модель не должна гадать.
> Используй lookup table с реальными коэффициентами.

Файлы: `agents/lca_specialist.py` + `prompts/lca_assessment.txt` + `data/gwp_coefficients.csv`

Сначала создай справочник:
```csv
# data/gwp_coefficients.csv
material,gwp_kg_co2e_per_kg,source,confidence
cotton_conventional,5.9,ecoinvent_3.9,high
cotton_organic,3.8,ecoinvent_3.9,high
polyester,6.4,ecoinvent_3.9,high
steel_virgin,2.3,worldsteel_2023,high
steel_recycled,0.4,worldsteel_2023,high
wood_softwood,0.3,ecoinvent_3.9,medium
aluminium_virgin,11.5,IAI_2023,high
aluminium_recycled,0.6,IAI_2023,high
concrete,0.13,ecoinvent_3.9,medium
glass,1.0,ecoinvent_3.9,medium
```

Промпт агента должен использовать таблицу:
```
You are an LCA specialist. Calculate GWP using ONLY the provided coefficients table.
Do NOT estimate values not in the table — mark them as "estimation_required".
For each material: find coefficient → multiply by weight percentage → sum.
```

Вход: `material_composition: list, country_of_manufacture: str`
Выход:
```json
{
  "gwp_kg_co2e": 3.2,
  "confidence": 0.55,
  "methodology_note": "Estimated via ecoinvent 3.9 proxy factors. Low confidence due to unknown dyeing process."
}
```
Тест: `"100% cotton, Ukraine"` → GWP estimate с `confidence < 0.7` (нет точных данных)

---

### Шаг 3.5 — Data Audit Agent (День 3)
Файлы: `agents/data_audit_agent.py` + `prompts/data_audit.txt`
Вход: `passport_json: dict, required_fields: list`
Выход:
```json
{
  "readiness_score": 54,
  "missing_essential": ["manufacturer", "materialComposition"],
  "missing_recommended": ["recycledContent", "waterConsumption"],
  "inconsistencies": [],
  "warnings": ["countryOfManufacture not matching facilityId.address"]
}
```
Тест: паспорт без `manufacturer` → `readiness_score < 60`, `"manufacturer" in missing_essential`

---

### Шаг 3.6 — GS1 Specialist (День 3-4)
Файл: `agents/gs1_specialist.py`
Методы:
- `validate_gtin(gtin: str) → bool` — проверка контрольной суммы (алгоритм mod-10)
- `generate_did_web(uuid: str) → str` — `did:web:passportai.example.com:passports:{uuid}`
- `build_gs1_digital_link(gtin_or_did: str, base_url: str) → str`
Тест:
```bash
python -c "
from agents.gs1_specialist import GS1Specialist
g = GS1Specialist(None)
assert g.validate_gtin('05901234123457') == True
assert g.validate_gtin('05901234123458') == False
print('GTIN validation OK')
"
```
Тест пройден: `GTIN validation OK`

---

### Шаг 3.7 — Gap Report (День 4)
Файлы: `src/core/gap_report.py` + `prompts/gap_check.txt` + `templates/gap_report.html.jinja2`
Метод: `generate(audit_result: dict, legal_result: dict, passport_json: dict) → Path`
Зависимости:
```bash
pip install jinja2 weasyprint
```
Тест:
```bash
python -c "
from src.core.gap_report import GapReportGenerator
gen = GapReportGenerator(None)
pdf_path = gen.generate({}, {}, {})
import os
assert os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 10_000
print('PDF OK, size:', os.path.getsize(pdf_path))
"
```
Тест пройден: файл существует, размер > 10KB

---

### Шаг 3.8 — Storage (День 4-5)
Файлы: `src/storage/base.py`, `src/storage/local.py`, `src/storage/aws_s3.py`
Интерфейс:
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
Тест S3: только если есть AWS_ACCESS_KEY_ID в окружении

---

### Шаг 3.9 — QR Generator (День 5)
Файл: `src/processing/qr.py`
Метод: `generate_qr(passport_url: str, output_path: Path) → Path`
Зависимости:
```bash
pip install qrcode[pil]
```
Тест:
```bash
python -c "
from src.processing.qr import generate_qr
from pathlib import Path
out = generate_qr('http://localhost:8000/test-uuid', Path('/tmp/test_qr.png'))
from PIL import Image
img = Image.open(out)
print('QR size:', img.size)
assert img.size[0] > 200
print('QR OK')
"
```
Тест пройден: QR PNG файл существует, размер > 200px

**ИТОГ НЕДЕЛИ 3:** запустить end-to-end тест: фото шопера Brand → полный `output/{uuid}/` со всеми 5 файлами
```bash
python -c "
import asyncio
from src.core.dpp_generator import DPPGenerator
# ... полный pipeline
# проверить наличие: passport.json, photo.png, passport.html, gap_report.pdf, qr.png
"
```

---

## НЕДЕЛЯ 4: UI + Demo (4–10 мая)
Цель: рабочий Gradio UI + FastAPI сервер + тест с реальным продуктом

### Шаг 4.1 — FastAPI Passport Server (День 1-2)
Файл: `src/server/passport_server.py`
Endpoints:
```
GET  /{uuid}       → passport.json (JSON response)
GET  /{uuid}/photo → photo.png    (FileResponse)
GET  /{uuid}/html  → passport.html (HTMLResponse)
POST /generate     → запуск полного pipeline (async, возвращает task_id)
GET  /status/{task_id} → прогресс генерации (шаг 1-13)
```
Тест:
```bash
uvicorn src.server.passport_server:app --port 8000 &
curl -s http://localhost:8000/test-uuid | python -m json.tool
```
Тест пройден: валидный JSON ответ (или 404 с понятным сообщением)

---

### Шаг 4.2 — Gradio UI (День 2-3)
Файл: `src/ui/gradio_app.py`
Компоненты:
- `gr.Image(type="filepath")` — загрузка фото продукта
- `gr.Textbox(label="Product description")` — описание на любом языке
- `gr.Textbox(label="GTIN (optional)")` — штрихкод EAN-14
- `gr.File(file_types=[".pdf"], label="Certificates")` — загрузка сертификатов
- `gr.Dropdown(choices=["local", "s3"])` — режим хранения
- `gr.Button("Generate DPP")` — запуск
- `gr.Progress()` — 13 шагов с подписями
- `gr.JSON()` — превью passport.json
- `gr.Image()` — QR-код
- `gr.File(label="Download ZIP")` — весь output пакет
Тест:
```bash
python src/ui/gradio_app.py
# открыть http://localhost:7860
# загрузить тестовое фото → нажать Generate → получить output
```

---

### Шаг 4.3 — app.py финальный (День 3)
Файл: `app.py`

> ⚠️ ВАЖНО: НЕ запускай FastAPI в отдельном Thread внутри Gradio.
> Это вызывает конфликт asyncio event loop и зависания UI.
> Используй gr.mount_gradio_app() — один процесс, один event loop.

Правильный паттерн (заменяет threading подход):
```python
from fastapi import FastAPI
import gradio as gr
from src.ui.gradio_app import create_ui
from src.server.passport_server import router

app = FastAPI(title="PassportAI")
app.include_router(router)  # все /passport/{uuid} endpoints

@app.get("/health")
def health():
    return {"status": "ok", "model": "gemma4:12b-q4_k_m"}

# Монтируем Gradio прямо в FastAPI — один event loop
ui = create_ui()
app = gr.mount_gradio_app(app, ui, path="/ui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# Доступ: http://localhost:8000/ui  (Gradio UI)
#         http://localhost:8000/{uuid}  (passport JSON)
```

Файл: `app.py`
Паттерн (старый — НЕ использовать):
```python
import threading
import uvicorn

def run_api():
    uvicorn.run(api_app, host="0.0.0.0", port=8000)

thread = threading.Thread(target=run_api, daemon=True)
thread.start()
gradio_app.launch(server_port=7860)
```
Тест:
```bash
python app.py
# в другом терминале:
curl http://localhost:8000/health   # → {"status": "ok"}
curl http://localhost:7860          # → HTML Gradio UI
```

---

### Шаг 4.4 — Тест с Brand (День 4) ← КРИТИЧЕСКИЙ
Задача: получить реальные фото шопера Brand (минимум 3 фото разных ракурсов)
Запустить полный pipeline с реальным продуктом
Проверить качество output:
- [ ] JSON-LD валидируется через pyld
- [ ] Фото 800x800 без фона
- [ ] QR ведёт на рабочий URL
- [ ] Gap report содержит реальные пробелы
- [ ] readiness_score отражает реальное состояние документации
Записать экран для видео (OBS Studio)

---

### Шаг 4.5 — Демо-видео (День 5)
Инструмент: OBS Studio (бесплатно, Windows/Mac/Linux)
Длина: 3 минуты ± 20 секунд
Структура:
```
0:00–0:30  Личная история: почему DPP важны для украинского бизнеса
0:30–1:00  Проблема: €30,000 за консалтинг vs 6M+ МСП в ЕС
1:00–1:40  Живое демо: фото шопера → DPP за 6 минут
1:40–2:10  Brand кейс: реальный продукт, реальный passport
2:10–2:30  Технический слой: Gemma 4, офлайн, приватность
2:30–3:00  Закрытие: ссылка на демо + GitHub
```
Загрузить на YouTube (unlisted), скопировать URL для сабмита

**ИТОГ НЕДЕЛИ 4:** рабочий UI + видео отснято + ссылки готовы

---

## НЕДЕЛЯ 5: Submit (11–18 мая)
Цель: все 5 элементов сабмита готовы до 17 мая

### Шаг 5.1 — GitHub README (День 1-2)
Файл: `README.md`
Обязательные секции:
```markdown
# PassportAI
> [Одна строка описания]

## What is a Digital Product Passport?
## Demo
[GIF демо 30 сек]
## Quick Start (3 commands)
## Architecture
## Output Example
## License
```
Ключевые цифры в README: `€30,000 → free`, `6-9 min`, `100% offline`, `CC-BY 4.0`

---

### Шаг 5.2 — Kaggle Writeup (День 2-3)
Лимит: 1,500 слов (жёсткий)
Структура:
```
Impact (500 слов):
  - Проблема: €30,000 за DPP консалтинг
  - Масштаб: 6M+ МСП в ЕС до 2027
  - Решение: бесплатно, офлайн, 6-9 минут

Technical (600 слов):
  - Gemma 4 12B Q4_K_M — почему именно эта модель
  - Multimodal vision pipeline
  - 5 специализированных агентов
  - JSON-LD VCDM 2.0 Level 2

Future (400 слов):
  - Интеграция с EU DPP Registry (2026)
  - Поддержка большего числа категорий ESPR
  - Fine-tuning на реальных DPP данных
```

---

### Шаг 5.3 — Live Demo (День 3-4)
Платформа: Hugging Face Spaces (бесплатно, Gradio native support)
Ограничение HF: Ollama не запустить на CPU Space → использовать меньшую модель или mock
Вариант A: HF Space с gemma4:2b (если влезает в RAM)
Вариант B: HF Space с mock данными + пояснение "full version requires local GPU"
Тест: открыть публичный URL → демо работает без установки

---

### Шаг 5.4 — Media Gallery (День 4)
Cover image: 1280x720 PNG
- Фон: тёмно-синий градиент
- Левая половина: скриншот Gradio UI с загруженным фото
- Правая половина: фрагмент passport.json + QR код
- Логотип PassportAI + слоган "DPP in 6 minutes, 100% offline"
Screenshots (минимум 4):
1. Gradio UI с загруженным фото шопера
2. Фрагмент сгенерированного passport.json
3. QR код + passport.html в браузере
4. Gap Report PDF

---

### Шаг 5.5 — Kaggle Submit (День 5 = 17 мая)
**Deadline: 18 мая 23:59 UTC — сабмитить 17 мая для safety margin!**

Чеклист перед сабмитом:
- [ ] Kaggle writeup опубликован (не черновик!)
- [ ] YouTube video — unlisted или public, ссылка скопирована
- [ ] GitHub repo — публичный, лицензия CC-BY 4.0, README заполнен
- [ ] Live demo URL работает (HF Spaces)
- [ ] Cover image загружена (1280x720)
- [ ] Все 5 полей формы заполнены

После сабмита: сохрани submission ID и скриншот подтверждения.
