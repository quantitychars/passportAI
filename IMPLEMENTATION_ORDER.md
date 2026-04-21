# PassportAI — IMPLEMENTATION ORDER v3

**Цель этой версии:** успеть к **30.04** без потери функциональности.
**Главное архитектурное решение:**

- `PassportPipeline` — **единственный оркестратор**
- `BaseAgent` — **единственный LLM-контракт**
- между шагами передаётся **typed state**, а не общий reasoning trace
- `run_verified_task()` используется **только там, где есть регуляторный / юридический риск**
- `thinking_orchestrator.py` и отдельный `reasoning_validator.py` **не возвращаются** в архитектуру

---

## 0. Замороженные правила архитектуры

### 0.1. Что запрещено

- Ни один агент не вызывает другой агент напрямую.
- Ни один агент не получает raw reasoning другого агента.
- Никакой shared `ThinkingContext` как межагентной памяти.
- Никакой “умный глобальный оркестратор” поверх `PassportPipeline`.

### 0.2. Что разрешено

- Агенты получают только релевантные входы и возвращают структурированный output.
- `PassportPipeline` отвечает за порядок шагов, обработку ошибок и сборку результата.
- `DataAuditAgent` и pipeline-проверки отвечают за cross-agent consistency.
- `StorageProvider` отвечает за публичный URL, который потом кодируется в QR.

### 0.3. Классы агентов по режиму работы

**A. Детерминированные / почти детерминированные**

- `DataAuditAgent`
- `LCASpecialist` (lookup CSV)
- `GS1Specialist`
- QR / storage / report generation

**B. Structured extraction**

- `VisionAgent`
- `DPPGenerator` (если использует schema-aware fill)

**C. Regulatory / legal interpretation**

- `RegulatoryConsultant`
- `LegalAgent`

Только группа **C** использует `run_verified_task()`.

---

## 1. Что уже считается сделанным

### 1.1 — Ollama + модель

**Статус:** DONE

### 1.2 — `GemmaClient`

**Статус:** DONE

Должно уже быть:

- `generate()`
- `think()`
- `analyze_image()`
- `call_tool()`
- retry / timeout / JSON fallback

### 1.3 — `BaseAgent`

**Статус:** DONE

Должно уже быть:

- единый `__init__`
- `call_tool()`
- `run_verified_task()`
- `_load_prompt()`
- `_format_success()` / `_format_error()`
- единый `AgentResult`

### 1.4 — DPP schema / JSON structure

**Статус:** DONE

Должно уже быть:

- `DPP_SCHEMA.json`
- category schemas в `schemas/`
- базовый JSON-LD/VCDM каркас

---

# 2. Реальный план до 30.04

## Общая стратегия

Не делать “всех реальных агентов, а потом интеграцию”.

Делать так:

1. Зафиксировать pipeline contracts
2. Собрать mock end-to-end
3. По одному заменять mocks на real implementation
4. Только потом делать AWS-слой хранения / публикации

---

## День 1 (утро) — Шаг 1.5 + Шаг 3.0

# Шаг 1.5 — `PipelineState` + `PipelineResult`

**Новые / изменяемые файлы:**

- `src/core/pipeline.py`
- возможно `src/config.py`

### Что сделать

Создать typed state, через который пойдёт весь pipeline.

### Минимальная структура

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PipelineState:
    image_path: str
    description: str
    gtin: str | None = None
    certificates: list[str] = field(default_factory=list)
    storage_mode: str = "local"

    standardized_photo_path: str | None = None
    image_description: str | None = None

    vision_result: dict[str, Any] | None = None
    regulatory_result: dict[str, Any] | None = None
    legal_result: dict[str, Any] | None = None
    lca_result: dict[str, Any] | None = None
    gs1_result: dict[str, Any] | None = None

    passport_json: dict[str, Any] | None = None
    audit_result: dict[str, Any] | None = None

    passport_id: str | None = None
    passport_url: str | None = None
    qr_path: str | None = None

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

@dataclass
class PipelineResult:
    success: bool
    passport_id: str | None
    passport_json: dict[str, Any] | None
    readiness_score: int | None
    passport_url: str | None
    qr_path: str | None
    warnings: list[str]
    errors: list[str]
```

### Зачем это нужно

Чтобы все остальные шаги подключались к одному стабильному контракту.

### Definition of Done

- `src/core/pipeline.py` компилируется
- `PipelineState` и `PipelineResult` существуют
- нигде не осталось зависимости от `ThinkingOrchestrator`

---

# Шаг 3.0 — `PassportPipeline` skeleton

**Файл:** `src/core/pipeline.py`

### Что сделать

Создать **единственный оркестратор системы**.

### Pipeline responsibilities

- принимает `PipelineState`
- вызывает шаги по порядку
- собирает warnings/errors
- останавливается на критических фейлах
- возвращает `PipelineResult`

### Минимальные методы

- `run(state: PipelineState) -> PipelineResult`
- `_run_perception_step()`
- `_run_generation_step()`
- `_run_review_step()`
- `_run_packaging_step()`
- `_build_result()`

### Важно

Никакой shared reasoning логики внутри pipeline.

### Definition of Done

- pipeline запускается даже с mock-агентами
- никакого `await` вне async-функции
- порядок шагов зафиксирован в одном месте

---

## День 1 (вечер) — mock end-to-end demo

# Шаг 1.6 — `DPPGenerator` MVP (не “идеальный”, а рабочий)

**Файл:** `src/core/dpp_generator.py`

### Что сделать

Сначала не multimodal и не “умный генератор”, а **стабильный schema-aware filler**.

### Минимум для MVP

- `generate_from_text(description)`
- `_build_jsonld_wrapper()`
- выбор schema по category
- заполнение минимально обязательных полей
- `merge_inputs()` уже есть, оставить как utility

### Важно

`DPPGenerator` не должен становиться оркестратором. Он только:

- получает уже собранные product facts
- строит `passport_json`
- валидирует базовую структуру

### Definition of Done

- по тексту можно получить валидный `passport_json`
- `tests/test_dpp_generator.py` проходят хотя бы для merge + validate + wrapper

---

# Шаг 1.7 — `Mock agents` для вертикального среза

**Файлы:**

- `agents/vision_agent.py`
- `agents/regulatory_consultant.py`
- `agents/legal_agent.py`
- `agents/lca_specialist.py`
- `agents/data_audit_agent.py`
- `agents/gs1_specialist.py`

### Что сделать

Для каждого skeleton-агента сделать **временную mock-реализацию**, которая возвращает реалистичный output в финальном формате.

### Обязательное правило

Mock должен возвращать **тот же shape**, что и будущая реальная версия.

### Пример

- `VisionAgent.run()` → `{"category": "furniture", "materials": ["oak wood"], ...}`
- `RegulatoryConsultant.run()` → `{"espr_category": "furniture", "required_fields": [...], ...}`
- `DataAuditAgent.run()` → `{"readiness_score": 62, "missing_essential": [...], ...}`

### Definition of Done

- pipeline проходит end-to-end без реального LLM в каждом шаге
- выходы всех mock-агентов уже совпадают с будущими contracts

---

# Шаг 1.8 — `StorageProvider` MVP

**Файлы:**

- `src/storage/base.py`
- `src/storage/local.py`

### Что сделать

Сначала доделать **только local storage**.

### Нужная функциональность

- `save_package()`
- `get_public_url()`
- `file_exists()`
- `delete_package()`

### Definition of Done

- package сохраняется в `output/{passport_id}/`
- есть базовый `passport_url`
- storage уже может быть вызван из pipeline

---

# Шаг 1.9 — `Gradio UI` working demo

**Файлы:**

- `src/ui/gradio_app.py`
- `app.py`

### Что сделать

Собрать рабочее демо:

- upload photo
- description
- нажать Generate
- получить JSON preview
- readiness score
- QR / placeholder QR
- ZIP / placeholder package

### Definition of Done

Есть **демо-проход**, который можно показать:

- фото Brand
- продукт: дубовый стол
- собранный паспорт
- readiness score

---

## День 2 — real `VisionAgent`

# Шаг 2.1 — `VisionAgent` real v1

**Файл:** `agents/vision_agent.py`

### Что сделать

Сделать реальный агент без лишней сложности:

1. `analyze_image()`
2. `call_tool()`
3. structured extraction

### Чего НЕ делать сейчас

- не добавлять отдельный предварительный global think
- не делать adversarial validation
- не пытаться решать regulatory reasoning через vision

### Поля, которые должен возвращать агент

- `category_candidate`
- `materials_detected`
- `visual_features`
- `visible_labels_text`
- `country_of_origin_visible`
- `confidence_visual`
- `evidence`

### Definition of Done

- на реальном фото возвращается структурированный словарь
- mock `VisionAgent` можно удалить
- pipeline использует реальную версию без изменения остальных шагов

---

# Шаг 2.2 — `PhotoProcessor`

**Файл:** `src/processing/photo.py`

### Что сделать

Реализовать:

- background removal
- белый фон
- 800x800 PNG

### Definition of Done

- `standardize_photo()` создаёт корректный PNG
- файл можно класть в output package

---

# Шаг 2.3 — perception step integration

**Файл:** `src/core/pipeline.py`

### Что сделать

Объединить:

- `VisionAgent`
- `standardize_photo()`
- merge с user input

### Режим выполнения

Можно сделать параллельно через `asyncio.to_thread`, но только после того как одиночные вызовы уже работают.

### Definition of Done

- perception step стабилен
- дальше в pipeline передаются уже нормализованные product facts

---

## День 3 — real `DPPGenerator`

# Шаг 2.4 — schema-aware generation

**Файл:** `src/core/dpp_generator.py`

### Что сделать

Довести генератор до реального состояния:

- выбор нужной schema по category
- заполнение `credentialSubject`
- генерация JSON-LD wrapper
- валидация результата
- поддержка multimodal merged input

### Что важно

`DPPGenerator` должен быть **максимально детерминированным**.
Свободного текста модели здесь должно быть меньше, чем структурированного заполнения.

### Definition of Done

- из merged product facts строится реальный `passport.json`
- есть `validate()`
- сгенерированный JSON можно сохранить и показать в UI

---

# Шаг 2.5 — offline JSON-LD / context loading

**Файлы:**

- `src/utils/jsonld_loader.py`
- `contexts/`

### Что сделать

Довести офлайн-кэш и загрузку контекстов до рабочего состояния.

### Definition of Done

- проект не зависит от живого интернета для JSON-LD contexts
- валидация не ломается из-за внешних URL

---

## День 4 — `DataAuditAgent` + cross-consistency

# Шаг 3.1 — `DataAuditAgent` real

**Файл:** `agents/data_audit_agent.py`

### Что сделать

Сделать его **детерминированным**.

### Ответственность агента

- readiness score
- missing essential fields
- missing recommended fields
- warnings
- inconsistencies

### Не делать

- не превращать его в reasoning-heavy LLM agent
- не пытаться дублировать legal/regulatory reasoning

### Definition of Done

- audit работает только на структурах Python
- score воспроизводим

---

# Шаг 3.2 — cross-agent consistency check

**Место:**

- либо внутри `DataAuditAgent`
- либо helper в `src/core/pipeline.py`

### Что проверять

- `VisionAgent.category_candidate` vs `RegulatoryConsultant.espr_category`
- `materials_detected` vs `passport_json.materials`
- `country_of_origin_visible` vs declared origin
- наличие обязательных полей по category

### Режим

`strict_mode=False` по умолчанию:

- конфликт флагируется
- pipeline не блокируется

### Definition of Done

- inconsistencies появляются в audit output
- UI показывает эти флаги

---

## День 5 — `RegulatoryConsultant`

# Шаг 3.3 — `RegulatoryConsultant` real

**Файл:** `agents/regulatory_consultant.py`

### Что сделать

Это первый настоящий агент, который использует `run_verified_task()`.

### Входы

- merged product facts
- candidate category
- visible labels / certificates

### Выходы

- `espr_category`
- `applicable_regulations`
- `required_fields`
- `missing_regulatory_inputs`
- `evidence`

### Definition of Done

- агент даёт category + regulatory requirements
- его результат уже участвует в audit

---

## День 6 — `LegalAgent`

# Шаг 3.4 — `LegalAgent` real

**Файл:** `agents/legal_agent.py`

### Что сделать

Тоже использовать `run_verified_task()`.

### Выходы

- `compliance_flags`
- `missing_documents`
- `legal_risks`
- `reach_flags` / `rohs_flags` / `vat_or_trade_flags` если применимо
- `evidence`

### Definition of Done

- legal result встраивается в `PipelineState`
- audit учитывает legal risks

---

## День 7 — `LCASpecialist`

# Шаг 3.5 — `LCASpecialist` real

**Файл:** `agents/lca_specialist.py`

### Что сделать

Сделать через CSV lookup, а не через reasoning.

### Источник

- `data/gwp_coefficients.csv`

### Выходы

- `estimated_gwp_kg_co2e`
- `coefficient_source`
- `assumptions`
- `confidence`

### Definition of Done

- для известных материалов возвращается воспроизводимый результат
- нет зависимости от LLM там, где можно обойтись таблицей

---

## День 8 — `GS1Specialist` + QR

# Шаг 3.6 — `GS1Specialist` real

**Файл:** `agents/gs1_specialist.py`

### Что сделать

Добавить:

- GTIN normalization
- product identifier assembly
- final public passport URL usage

### Definition of Done

- если GTIN передан, он включается в package
- если GTIN нет, система не падает

---

# Шаг 3.7 — QR generation

**Файл:** `src/processing/qr.py`

### Что сделать

Реализовать `generate_qr()`.

### Жёсткое правило

QR делается **только после** того, как есть стабильный `passport_url`.

### Definition of Done

- QR PNG генерируется
- сканирование ведёт на `passport_url`

---

## День 9 — HTML/PDF + packaging

# Шаг 3.8 — `GapReportGenerator`

**Файл:** `src/core/gap_report.py`

### Что сделать

Сначала сделать минимальную рабочую версию:

- template context
- render Jinja2
- HTML → PDF

### Definition of Done

- `gap_report.pdf` создаётся
- PDF входит в package

---

# Шаг 4.1 — `FastAPI server`

**Файл:** `src/server/passport_server.py`

### Что сделать

Не строить сложный background job server.
Сделать сначала MVP:

- serve local output files
- basic routes for generated passports

### Definition of Done

- локальный `passport_url` открывается в браузере
- JSON / HTML / QR доступны по URL

---

# Шаг 4.2 — `Gradio UI` polishing

**Файл:** `src/ui/gradio_app.py`

### Что сделать

Довести UI до конкурсного состояния:

- прогресс по шагам
- preview outputs
- download package
- понятные ошибки

### Definition of Done

- UI годится для записи демо-видео

---

## День 10 (30.04) — AWS MVP + финальный буфер

# Шаг 3.9 — AWS S3 Storage MVP

**Файл:** `src/storage/aws_s3.py`

### Что сделать

Реализовать только то, что критично для печатного QR:

- `save_package()`
- `get_public_url()`
- `file_exists()`
- `.env.example` для AWS

### Какой scope допустим до дедлайна

**Да:**

- загрузка package в S3
- стабильный публичный URL
- QR на этот URL
- deploy instructions

**Нет, если не останется буфера:**

- полноценная AWS orchestration платформа
- асинхронные job queues
- autoscaling GPU inference layer
- сложный multi-tenant backend

### Definition of Done

- можно выбрать `storage_mode="s3"`
- package реально загружается в bucket
- QR открывает облачный URL

---

# Шаг 4.3 — app.py final entrypoint

**Файл:** `app.py`

### Что сделать

Одна понятная точка входа:

- launch Gradio
- optional FastAPI mount
- env-based mode selection

### Definition of Done

- запуск по README понятен
- локальная и S3-конфигурация не конфликтуют

---

# Шаг 4.4 — Финальный Brand test

### Сценарий

- фото продукта Brand
- описание
- генерация полного package
- `passport.json`
- HTML
- PDF
- QR
- readiness score

### Definition of Done

Это можно показать судьям без ручных оправданий.

---

# Шаг 4.5 — Демо-видео

### Что показать

1. upload product photo
2. generation flow
3. resulting passport
4. readiness / compliance view
5. QR scan → open passport URL

---

# Шаг 5.x — После 30.04 / конкурсная упаковка

## Шаг 5.1 — README

- local setup
- AWS setup
- architecture diagram
- how to add your own product data

## Шаг 5.2 — Kaggle / contest writeup

- problem
- why Gemma
- anti-hallucination design
- schema-first DPP generation
- cloud-ready QR workflow

## Шаг 5.3 — Live demo

Если останется время: HF Spaces / публичный demo endpoint

## Шаг 5.4 — Media gallery

cover + screenshots + QR scan flow

## Шаг 5.5 — Submission checklist

- README
- demo video
- reproducible setup
- sample output package

---

# 3. AWS: что реально успеть

## Реалистичная цель до 30.04

Сделать **AWS storage deployment path**, а не “полный AWS inference platform”.

### Значит:

- inference может продолжать работать локально или на одной машине
- outputs публикуются в S3
- QR кодирует стабильный облачный URL
- любой человек может поднять проект из репозитория, прописать свои AWS credentials и получить печатный QR workflow

## Рекомендуемый AWS scope v1

### Обязательно

- `src/storage/aws_s3.py`
- `HOSTING_URL`
- bucket setup инструкции
- IAM policy example
- README section “Deploy with S3”

### Желательно

- CloudFront-ready URL support
- `HOSTING_URL=https://your-domain-or-cloudfront.net`
- `scripts/create_s3_bucket.sh` или `deploy/aws/README.md`

### Необязательно до дедлайна

- ECS/Fargate/EC2 automation
- Terraform/CDK
- async queue processing
- managed auth system

---

# 4. Приоритеты, если начнёт гореть дедлайн

Если времени мало, режь scope в таком порядке:

## Нельзя вырезать

- `PassportPipeline`
- `VisionAgent`
- `DPPGenerator`
- `DataAuditAgent`
- `QR`
- `LocalStorage`
- working Gradio demo

## Можно упростить

- `LegalAgent`
- `LCASpecialist`
- `GS1Specialist`
- `GapReportGenerator`
- AWS deployment automation

## Можно отложить

- FastAPI background tasks
- сложный async server
- production-grade cloud orchestration

---

# 5. Итоговое правило реализации

## Правильный порядок

- сначала **contracts + thin pipeline**
- потом **mock vertical slice**
- потом **real agents one by one**
- потом **storage / QR / packaging**
- потом **AWS publication layer**

## Неправильный порядок

- сначала “все агенты”
- потом поздняя интеграция
- потом попытка спасти всё через глобальный orchestrator

---

# 6. Минимальный must-have к 30.04

К финалу у проекта должно быть:

- рабочий `PassportPipeline`
- реальный `VisionAgent`
- реальный `DPPGenerator`
- реальный `DataAuditAgent`
- хотя бы базовый `RegulatoryConsultant`
- `LocalStorage`
- опционально `S3Storage`
- `QR`
- Gradio demo
- один убедительный сценарий: **Brand → дубовый стол → готовый DPP package**

Если всё это есть, проект уже выглядит как конкурсный продукт, а не как набор заготовок.
