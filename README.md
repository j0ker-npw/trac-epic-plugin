# TracEpicPlugin

Epic ↔ ticket linking for **Trac 1.6** (Python 3.13, PostgreSQL 13).
Связывание эпиков и тикетов для **Trac 1.6**.

---

## English

### Overview

TracEpicPlugin introduces an M:N relationship between "epic" tickets and
regular tickets:

* A ticket of type `epic` gets a **Linked Tickets** section listing all of
  its member tickets.
* Any other ticket gets an **Epics** section listing the epics it belongs
  to.
* One ticket may belong to many epics, and one epic may hold many tickets.
* All link changes are written to the ticket **changelog**
  (`ticket_change`, field `epic_link`).
* An **XML-RPC API** (via the XmlRpcPlugin / `tracrpc`) is provided.

### Requirements

| Component   | Version              |
|-------------|----------------------|
| Trac        | 1.6                  |
| Python      | 3.9+ (tested on 3.13)|
| Database    | PostgreSQL 13 (also works on SQLite/MySQL) |
| jQuery      | 3.7.1 (bundled with Trac 1.6) |
| XmlRpcPlugin| optional, for the XML-RPC API |

### Installation

**Method 1: System-wide Trac (Debian/Ubuntu from apt) — Recommended**

When Trac is installed from system packages (`apt install trac`), Python is externally managed (PEP 668). Install the plugin directly into your Trac environment:

```bash
cd /path/to/trac-epic-plugin

# Build the egg file
python3 setup.py bdist_egg

# Copy to your Trac environment's plugins directory
sudo cp dist/TracEpicPlugin-1.0.0-py3.*.egg /path/to/trac-env/plugins/

# Apply database migration
trac-admin /path/to/trac-env upgrade

# Restart the web front-end (Apache/mod_wsgi)
sudo systemctl restart apache2
```

**Method 2: Trac in virtual environment**

If Trac is installed in a virtual environment:

```bash
source /path/to/trac/venv/bin/activate
pip install -e /path/to/trac-epic-plugin
trac-admin /path/to/trac-env upgrade
# Restart your web server
```

**Method 3: System-wide pip (not recommended)**

⚠️ **Warning**: This method bypasses Python's externally-managed environment protection (PEP 668) and may break system packages. Use only if you understand the risks.

```bash
cd /path/to/trac-epic-plugin
pip install -e . --break-system-packages

trac-admin /path/to/trac-env upgrade
sudo systemctl restart apache2
```

### Configuration (`trac.ini`)

Enable the components:

```ini
[components]
tracepic.* = enabled
```

Add the `epic` ticket type (either via the admin UI, *Ticket System →
Ticket Types*, or `trac.ini`):

```ini
[ticket]
# Make sure 'epic' is one of the available types.
# Use the Admin panel, or add it with:
#   trac-admin /path/to/env ticket_type add epic
```

The plugin serves its own static assets (`epic.js`, `epic.css`) and Jinja2
template automatically; no extra template configuration is required.

### XML-RPC API

Requires the [XmlRpcPlugin](https://trac-hacks.org/wiki/XmlRpcPlugin)
(`tracrpc`) to be installed and enabled, and the `XML_RPC` permission
granted to the calling user.  The endpoint is usually
`https://user:pass@host/trac/login/xmlrpc`.

| Method | Permission | Returns |
|--------|-----------|---------|
| `ticket.getEpics(ticket_id)` | `TICKET_VIEW` | list of epic ids for the ticket |
| `ticket.getEpicLinkedTickets(epic_id)` | `TICKET_VIEW` | list of ticket ids for the epic |
| `ticket.addEpicLink(ticket_id, epic_id)` | `TICKET_MODIFY` | `True` if a new link was created |
| `ticket.removeEpicLink(ticket_id, epic_id)` | `TICKET_MODIFY` | `True` if a link was removed |

Python example:

```python
import xmlrpc.client
server = xmlrpc.client.ServerProxy(
    "https://user:pass@host/trac/login/xmlrpc")
server.ticket.addEpicLink(42, 7)      # link ticket #42 to epic #7
print(server.ticket.getEpics(42))     # -> [7]
print(server.ticket.getEpicLinkedTickets(7))  # -> [42]
server.ticket.removeEpicLink(42, 7)
```

**What is `tracrpc` / the XML-RPC API used for?**
It lets external tools and scripts manage epic links programmatically
without going through the web UI — for example CI pipelines that link a
newly created ticket to a release epic, bulk import/migration scripts,
integrations with other trackers, or dashboards that read the epic
structure. It is optional; the web UI works without it.

### AJAX endpoints (used by the web UI)

* `POST /epic/link` — `action=add|remove`, `epic_id`, `ticket_id`,
  `__FORM_TOKEN`. Returns JSON with the refreshed link list.
* `GET /epic/search` — `q`, `only=epic|ticket`, `exclude` for
  autocomplete. Returns JSON list of matching tickets.

### Data migration

On `trac-admin ... upgrade` the plugin:

1. Creates the `epic_links` table if it does not exist.
2. Scans `ticket_custom` for legacy custom fields named `epic` or
   `parent_epic`. Each numeric value (supports `#123`, comma/space
   separated lists) is converted into a link, **only** when both the epic
   and the ticket exist. Existing links are never duplicated.

The migration is idempotent and safe to re-run.

### Database schema

```sql
CREATE TABLE epic_links (
    id        SERIAL PRIMARY KEY,
    epic_id   INTEGER NOT NULL,
    ticket_id INTEGER NOT NULL,
    author    TEXT,
    created   BIGINT,
    UNIQUE (epic_id, ticket_id)
);
```

### Running the tests

```bash
pip install -e .
python -m pytest tests/ -v
```

---

## Русский

### Обзор

TracEpicPlugin добавляет связь «многие-ко-многим» между тикетами типа
`epic` и обычными тикетами:

* Тикет типа `epic` получает секцию **Linked Tickets** со списком всех
  входящих в него тикетов.
* Любой другой тикет получает секцию **Epics** со списком эпиков, которым
  он принадлежит.
* Один тикет может входить в несколько эпиков, один эпик — содержать много
  тикетов.
* Все изменения связей пишутся в **историю изменений** тикета
  (`ticket_change`, поле `epic_link`).
* Предоставляется **XML-RPC API** (через XmlRpcPlugin / `tracrpc`).

### Требования

| Компонент   | Версия               |
|-------------|----------------------|
| Trac        | 1.6                  |
| Python      | 3.9+ (проверено на 3.13) |
| БД          | PostgreSQL 13 (работает и на SQLite/MySQL) |
| jQuery      | 3.7.1 (входит в Trac 1.6) |
| XmlRpcPlugin| опционально, для XML-RPC API |

### Установка

**Метод 1: Системный Trac (Debian/Ubuntu из apt) — рекомендуется**

Когда Trac установлен из системных пакетов (`apt install trac`), Python находится под управлением системы (PEP 668). Устанавливайте плагин напрямую в директорию окружения Trac:

```bash
cd /path/to/trac-epic-plugin

# Собрать egg-файл
python3 setup.py bdist_egg

# Скопировать в директорию plugins вашего окружения Trac
sudo cp dist/TracEpicPlugin-1.0.0-py3.*.egg /path/to/trac-env/plugins/

# Применить миграцию БД
trac-admin /path/to/trac-env upgrade

# Перезапустить веб-сервер (Apache/mod_wsgi)
sudo systemctl restart apache2
```

**Метод 2: Trac в виртуальном окружении**

Если Trac установлен в виртуальном окружении:

```bash
source /path/to/trac/venv/bin/activate
pip install -e /path/to/trac-epic-plugin
trac-admin /path/to/trac-env upgrade
# Перезапустить веб-сервер
```

**Метод 3: System-wide pip (не рекомендуется)**

⚠️ **Предупреждение**: Этот метод обходит защиту внешне-управляемого окружения Python (PEP 668) и может нарушить работу системных пакетов. Используйте только если понимаете риски.

```bash
cd /path/to/trac-epic-plugin
pip install -e . --break-system-packages

trac-admin /path/to/trac-env upgrade
sudo systemctl restart apache2
```

### Настройка (`trac.ini`)

Включить компоненты:

```ini
[components]
tracepic.* = enabled
```

Добавить тип тикета `epic` (через админку *Ticket System → Ticket Types*
или командой):

```bash
trac-admin /path/to/env ticket_type add epic
```

Статические файлы (`epic.js`, `epic.css`) и Jinja2-шаблон плагин
обслуживает сам — дополнительная настройка не нужна.

### XML-RPC API

Требуется установленный и включённый
[XmlRpcPlugin](https://trac-hacks.org/wiki/XmlRpcPlugin) (`tracrpc`) и
право `XML_RPC` у пользователя.

| Метод | Право | Возвращает |
|-------|-------|-----------|
| `ticket.getEpics(ticket_id)` | `TICKET_VIEW` | список id эпиков тикета |
| `ticket.getEpicLinkedTickets(epic_id)` | `TICKET_VIEW` | список id тикетов эпика |
| `ticket.addEpicLink(ticket_id, epic_id)` | `TICKET_MODIFY` | `True`, если связь создана |
| `ticket.removeEpicLink(ticket_id, epic_id)` | `TICKET_MODIFY` | `True`, если связь удалена |

**Для чего используется плагин `tracrpc` / XML-RPC API?**
Он позволяет внешним инструментам и скриптам управлять связями эпиков
программно, минуя веб-интерфейс: например, CI-пайплайны, которые
привязывают новый тикет к эпику релиза; скрипты массового импорта и
миграции; интеграции с другими трекерами; дашборды, читающие структуру
эпиков. Компонент опционален — веб-интерфейс работает и без него.

### Миграция данных

При выполнении `trac-admin ... upgrade` плагин:

1. Создаёт таблицу `epic_links`, если её нет.
2. Просматривает `ticket_custom` на предмет старых полей `epic` или
   `parent_epic`. Каждое числовое значение (поддерживаются `#123`, списки
   через запятую/пробел) превращается в связь — **только** если и эпик, и
   тикет существуют. Дубликаты не создаются.

Миграция идемпотентна, повторный запуск безопасен.

### Запуск тестов

```bash
pip install -e .
python -m pytest tests/ -v
```

---

## License

BSD-3-Clause.
