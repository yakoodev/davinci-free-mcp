# DavinciFreeMcp: кратко по-русски

## Что это

`DavinciFreeMcp` — это MCP-first сервер и backend для **DaVinci Resolve Free**.

Проект не строится вокруг Studio-only внешнего scripting API. Вместо этого используется практичный подход:

- внутренний executor запускается **изнутри Resolve Free**
- внешний backend работает отдельно
- MCP является внешним интерфейсом
- bridge соединяет внешний backend и внутренний executor

## Что уже есть

Сейчас в проекте уже есть полноценная сквозная связка:

- Dockerized MCP/backend service
- `file_queue` bridge и прототип `local_http`
- standalone bootstrap/executor для запуска внутри Resolve Free
- встроенная модульная система MCP: базовый `core` module плюс opt-in модули через `DFMCP_ENABLED_MODULES` и `DFMCP_DISABLED_MODULES`
- low-level Resolve tools для проектов, media pool, timeline и markers
- локальный media-analysis слой для аудио/видео вне Resolve bridge
- диагностика по `instance_id`, `executor_status.json` и lock ownership
- PowerShell helper scripts для запуска, smoke-check и live validation

Из наиболее полезных публичных tools уже доступны:

- Resolve/project: `resolve_health`, `project_current`, `project_list`, `project_manager_folder_list`, `project_manager_folder_open`, `project_manager_folder_up`, `project_manager_folder_path`, `project_open`
- Media pool: `media_pool_list`, `media_pool_folder_open`, `media_pool_folder_create`, `media_pool_folder_up`, `media_pool_folder_root`, `media_pool_folder_path`, `media_pool_folder_list_recursive`, `media_pool_folder_open_path`, `media_import`, `media_clip_inspect`, `media_clip_inspect_path`
- Timeline/markers: `timeline_list`, `timeline_current`, `timeline_create_empty`, `timeline_set_current`, `timeline_append_clips`, `timeline_clips_place`, `timeline_create_from_clips`, `timeline_build_from_paths`, `timeline_items_list`, `timeline_inspect`, `timeline_track_items_list`, `timeline_track_inspect`, `timeline_item_inspect`, `timeline_item_delete`, `timeline_item_move`, `timeline_item_split`, `timeline_item_set_source_range`, `timeline_gap_close`, `timeline_remove_gaps`, `timeline_insert_gap`, `marker_add`, `marker_list`, `marker_inspect`, `marker_list_range`, `marker_delete`
- Local media analysis: `audio_probe`, `audio_transcribe_segments`, `audio_detect_events`, `video_probe`, `video_detect_shots`, `video_sample_frames`, `video_extract_roi_frames`, `video_build_contact_sheet`, `video_detect_overlay_events`, `video_extract_segment_screenshots`, `video_segment_from_speech`, `video_segment_visual`, `video_segment_audio_visual`, `edit_plan_from_candidates`

## Как это устроено

Основная цепочка такая:

`Codex / MCP client -> MCP server -> backend -> bridge -> executor inside Resolve`

В текущем состоянии:

- `file_queue` — основной рабочий transport
- `local_http` — экспериментальный второй transport
- media-analysis tools выполняются локально в backend и не требуют live Resolve session

## Быстрый старт

1. Подними backend:

```powershell
.\scripts\dev_up.ps1
```

2. Установи bootstrap в папку скриптов Resolve:

```powershell
.\scripts\dev_install_executor.ps1
```

Точный путь установки в текущем Windows-окружении:

```text
C:\Users\Yakoo\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\resolve_executor_bootstrap.py
```

3. Открой DaVinci Resolve Free
Лучше запускать его так:

```powershell
.\scripts\dev_start_resolve_with_python.ps1
```

Это добавляет Python 3.11 в `PATH` именно для процесса Resolve. На этой машине без этого `Workspace -> Scripts` может быть отключен.

4. Открой тестовый проект
5. Запусти:

```text
Workspace -> Scripts -> Utility -> resolve_executor_bootstrap
```

6. Проверь диагностику:

```powershell
.\scripts\dev_diagnostics.ps1
```

## Рекомендуемый live-цикл после новых фич

Если ты поменял backend, bridge или `scripts/resolve_executor_bootstrap.py`, используй такой порядок:

1. Полностью закрыть Resolve и хвосты:

```powershell
.\scripts\dev_kill_davinci.ps1
```

2. Если менялся bootstrap, переустановить его:

```powershell
.\scripts\dev_install_executor.ps1
```

3. Пересоздать backend-контейнер:

```powershell
docker compose down
.\scripts\dev_up.ps1
```

4. Запустить Resolve через:

```powershell
.\scripts\dev_start_resolve_with_python.ps1
```

5. Открыть тестовый проект
Текущий рабочий вариант на этой машине:

- `Untitled Project 5`

6. Включить скрипт:

```text
Workspace -> Scripts -> Utility -> resolve_executor_bootstrap
```

7. Прогнать:

```powershell
.\scripts\dev_diagnostics.ps1
```

Нормальный результат:

- `resolve_health.success = true`
- `executor.running = true`
- открыт нужный проект

## Как понять, что всё работает

Проверь:

```powershell
.\scripts\dev_status.ps1
.\scripts\dev_who_owns_lock.ps1
.\scripts\dev_logs.ps1
```

Нормальный результат:

- `instance_id` в status и lock совпадает
- в логе только один `instance_id`
- `resolve_health`, `project_current`, `project_list`, `timeline_list` успешны
- при локальном анализе появляются артефакты в `runtime/analysis/<analysis_id>/`

## Как тестировать REST-вариант

1. Создай `.env` на основе `.env.example`
2. Укажи:

```text
DFMCP_BRIDGE_ADAPTER=local_http
DFMCP_LOCAL_HTTP_HOST=host.docker.internal
DFMCP_LOCAL_HTTP_BIND_HOST=127.0.0.1
DFMCP_LOCAL_HTTP_PORT=5001
```

3. Перезапусти backend:

```powershell
.\scripts\dev_up.ps1
```

4. Переустанови bootstrap:

```powershell
.\scripts\dev_install_executor.ps1
```

5. Перезапусти Resolve и снова запусти `resolve_executor_bootstrap`
6. После этого проверь:

```powershell
.\scripts\dev_diagnostics.ps1
```

Если `local_http` работает, backend в Docker должен ходить к executor по `host.docker.internal:5001`, а не через `runtime/spool`.

## Полезные документы

- `README.md`
- `docs/RUNNING.md`
- `docs/DEVELOPMENT.md`
- `docs/TROUBLESHOOTING.md`
- `CHANGELOG.md`
