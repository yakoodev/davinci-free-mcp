# CHANGELOG

Все существенные изменения проекта фиксируются в этом файле.

## Unreleased

- Добавлены low-level MCP tools для локального анализа аудио и видео: `audio_probe`, `audio_transcribe_segments`, `audio_detect_events`, `video_probe`, `video_detect_shots`, `video_extract_segment_screenshots`, `video_segment_from_speech`, `video_segment_visual`, `video_segment_audio_visual`.
- Добавлен локальный media-analysis слой вне Resolve bridge с сохранением артефактов в `runtime/analysis/<analysis_id>/`.
- Добавлены контракты и тесты для segment-oriented audio/video результатов, включая voiced и no-speech video сценарии.
- `audio_transcribe_segments` и `video_segment_from_speech` теперь автоматически создают и переиспользуют `*.transcript.json` sidecar рядом с исходным файлом через `faster-whisper`.
- Docker image теперь включает `ffmpeg`, а speech runtime настраивается через `DFMCP_TRANSCRIBE_*`.
- Исправлен `video_segment_audio_visual`, чтобы без reliable shot data сохранять реальные границы audio events вместо растяжки на весь клип.
- `video_segment_from_speech` теперь транскрибирует каждую audio track отдельно, сохраняет merged multi-track sidecar и пишет проверяемую копию `transcript.json` в `runtime/analysis/<analysis_id>/`.
- Speech JSON упрощен: sidecar и speech tool outputs теперь используют один плоский массив `segments` с базовыми полями `start`, `end`, `text`, `track_index` и опциональным `screenshot_path`.
- Таймкоды speech-сегментов для видео теперь компенсируют per-track `start_time`, чтобы уменьшить рассинхрон между аудиодорожками; для обычных аудиофайлов смещение остается нулевым.
- `docker-compose.yml` теперь монтирует `C:\Users\Yakoo\Videos\NVIDIA\Counter-strike 2` в контейнер как `/videos/cs2` для live MCP-проверок без `docker cp`.
- JSON-артефакты media-analysis теперь пишутся как читаемый UTF-8 без `\uXXXX`-экранирования кириллицы.

## История изменений

### fa0f0c3 - Add timeline build from paths tool

- Добавлен `timeline_build_from_paths` для rough-cut сборки новой timeline напрямую из списка media paths.
- MCP теперь умеет импортировать файлы и собирать набросок ролика одной low-risk composed командой.

### d05c03d - Add timeline item move tool

- Добавлен `timeline_item_move` для low-level перемещения timeline clip через `copy+delete`.
- Закрыт clip-oriented workflow для переноса item между позициями и треками с явной диагностикой неатомарных сбоев.
- Добавлен live-safe fallback для Resolve cases, где `GetSourceStartFrame/GetSourceEndFrame` возвращают `0/0` для полного clip range.

### 76254be - Add project manager folder navigation tools

- Добавлены `project_manager_folder_list`, `project_manager_folder_open`, `project_manager_folder_up`, `project_manager_folder_path`.
- Расширен low-level project-manager navigation с breadcrumb/path и списком дочерних folders/projects.

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
