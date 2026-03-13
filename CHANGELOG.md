# CHANGELOG

Все существенные изменения проекта фиксируются в этом файле.

## Unreleased

- Добавлены `project_manager_folder_list`, `project_manager_folder_open`, `project_manager_folder_up`, `project_manager_folder_path`.
- Расширен low-level project-manager navigation с breadcrumb/path и списком дочерних folders/projects.

## История изменений

### 4cad928 - Create missing tracks before clip placement

- `timeline_clips_place` теперь заранее создает недостающие timeline tracks через Resolve API перед placement.
- Исправлен live-баг, из-за которого overlay placement на новый `V2` мог возвращать успех без фактического появления клипа.

### 0e4da3a - Add clip placement and timeline item tools

- Добавлены low-level tools `timeline_clips_place`, `timeline_item_inspect`, `timeline_item_delete`.
- Добавлена placement-семантика с `record_frame`, `track_index`, `start_frame`, `end_frame` и `media_type`.
- Добавлен inspect/delete workflow для конкретного timeline item.
- Исправлены live edge cases для delete summary и default `media_type=1` для video placement.

### 5829441 - Add recursive folder, track, and marker range tools

- Добавлены `media_pool_folder_list_recursive`, `timeline_track_inspect`, `marker_list_range`.
- Расширен low-level inspection для media pool, tracks и диапазонной выборки маркеров.

### 94cb7b8 - Add targeted marker, track, and clip inspection tools

- Добавлены `media_clip_inspect_path`, `timeline_track_items_list`, `marker_inspect`.
- Улучшена адресная инспекция клипов, треков и отдельных маркеров.

### f28a7cd - Add media pool path tools and timeline inspect

- Добавлены `media_pool_folder_root`, `media_pool_folder_path`, `media_pool_folder_open_path`, `timeline_inspect`.
- MCP получил явные path-oriented media pool операции и агрегированную сводку по timeline.

### eefa7ae - Add marker, media folder, and timeline creation tools

- Добавлены инструменты для создания timeline, работы с media pool folders и управления маркерами.
- Расширен mutation surface для базовых Resolve workflow операций.

### 626e3cf - Add timeline context and marker MCP tools

- Добавлены timeline context tools и первая волна marker-oriented MCP операций.
- Улучшена навигация по timeline state через публичный MCP слой.

### 69a6b04 - Add external Resolve automation tooling

- Добавлены внешние automation scripts и tooling для запуска/проверки Resolve вне embedded path.
- Улучшен dev workflow для live validation и startup automation.

### c2d42b6 - Refactor resolve executor command core

- Переработан `resolve_exec.command_core` как общий low-level execution слой.
- Улучшена структура handlers и расширяемость для новых MCP tools.

### 656669f - Add core timeline and media MCP tools

- Добавлены базовые timeline и media tools, формирующие основной MCP surface проекта.
- Заложен low-level workflow для списка timeline/media сущностей и базовых mutation операций.

### 99c33c0 - Fix local HTTP bridge bind host handling

- Исправлена конфигурация bind/connect host для local HTTP bridge.
- Стабилизировано взаимодействие backend container <-> host-side executor bridge.

### 1c3fbf3 - Add full DaVinci shutdown helper and duplicate warnings

- Добавлен helper для полного завершения DaVinci-side runtime процессов.
- Добавлены предупреждения по duplicate executor/runtime state.

### b7d33ee - Add executor diagnostics and local HTTP bridge prototype

- Добавлены diagnostics для embedded executor и прототип local HTTP bridge.
- Подготовлена инфраструктура для live Resolve communication вне file queue-only модели.

### a309fc1 - Initial DavinciFreeMcp MVP scaffold

- Создан первоначальный MVP scaffold проекта.
- Заложена базовая структура backend, contracts, server и resolve executor.
