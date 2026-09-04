# Audion PPTX Print to PDF Tool

**Содержание**

- [Основной сценарий](#основной-сценарий)
- [Канонические названия Workbench](#канонические-названия-workbench)
- [Основные launcher-файлы](#основные-launcher-файлы)
- [Совместимые wrappers](#совместимые-wrappers)
- [Service layer](#service-layer)
- [Ключевые папки](#ключевые-папки)
- [Важно](#важно)

Портативный Windows-инструмент с NiceGUI-shell для пакетной печати PowerPoint через **Microsoft Print to PDF** с последующей обрезкой сохранённых PDF из папки `output` до **16:9** или **A4/A3**.

## Основной сценарий

1. Запустить `launcher_gui.cmd` напрямую или открыть GUI из `launcher_project.cmd` / `launcher_project_ru.cmd`.
2. Подготовить **Microsoft Print to PDF** как принтер по умолчанию.
3. Положить `.pptx` или `.pptm` в папку `input`.
4. Запустить guided-печать. В каждом диалоге Microsoft Print to PDF вставить полный путь из буфера обмена и сохранить PDF.
5. Вернуться в GUI и нажать `PDF СОХРАНЁН` после каждого файла.
6. При необходимости обрезать все PDF в `output` до `16:9` или `A4/A3`, затем вернуть прежний принтер.

## Канонические названия Workbench

GUI использует единый канонический Workbench. Адресная строка называется **Источник / Назначение**, а панель действий содержит одинаковые во всех проектах кнопки: **Источник**, **Добавить файл...**, **Назначение**, **Сбросить**, **Удалить**, **Список**.

- **Источник** принимает папку с презентациями или один файл `.pptx` / `.pptm`.
- **Назначение** указывает папку для сохраняемых и обрезаемых PDF.
- GUI и CLI/backend используют одни и те же выбранные пути.
- **Сбросить** возвращает проектные `input` / `output` и очищает незакреплённый кэш путей.
- **Удалить** является необратимой операцией и запрашивает подтверждение перед общей очисткой.

## Основные launcher-файлы

- `launcher_gui.cmd` - guided GUI-shell с темами, переключением RU/EN, статус-карточками, журналом и child-экранами операций
- `launcher_project.cmd` - английский unified launcher с `FZF + CMD fallback`
- `launcher_project_ru.cmd` - русская зеркальная копия английского launcher с переводом только UI

Если `fzf.exe` отсутствует, launcher автоматически переходит в встроенный `choice`-режим.

## Совместимые wrappers

Простые one-click wrappers сохранены и вызывают `run_action.cmd`:

- `01_Enable_And_Set_Microsoft_Print_to_PDF_Default.cmd`
- `03_Print_All_PPTX_From_Input.cmd`
- `05_Crop_All_PDFs_From_Output_16x9_Exact.cmd`
- `06_Crop_All_PDFs_From_Output_A4_A3.cmd`
- `04_Restore_Previous_Default_Printer.cmd`
- `09_Doctor.cmd`

## Service layer

- `builder_main.cmd` - template-owned точка входа builder-слоя
- `launcher_tools.cmd` - template-owned launcher для tools и release-задач
- `install\` - build, install, verify и release helpers
- `system_core\license\` и `licenses\` - support-layer для release и лицензий

## Ключевые папки

- `input` - исходные PPTX/PPTM
- `output` - сохранённые PDF для обрезки
- `logs` - логи сессий
- `state` - сохранённое состояние принтера
- `config` - настройки проекта
- `report` - отчёты и GUI-артефакты
- `system_core` - PowerShell- и Python-helper-скрипты
- `GitHub` - GitHub-документация проекта
- `._runtime` - temp-файлы launcher-слоя для ветки `FZF`

## Важно

- Этап печати guided, а не silent. Так Microsoft Print to PDF и PowerPoint сохраняют контроль над точным рендерингом шрифтов.
- `--skip-existing` пропускает PDF, которые уже есть в `output`.
- GUI намеренно не показывает всплывашки при простом открытии стандартных папок.
- Temp-схема `FZF` разведена по языкам:
  - `project_menu_en*`
  - `project_menu_ru*`
- В режиме `CMD fallback` папка `._runtime` может оставаться пустой, и это нормально.
