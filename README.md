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

# Build the egg (use -B to avoid pyc permission issues on some systems).
# IMPORTANT: build with the SAME Python that runs Trac, so the egg gets the
# matching -pyX.Y tag (e.g. on Python 3.13 you get ...-py3.13.egg). Trac
# ignores eggs whose Python tag does not match the running interpreter.
python3 -B setup.py bdist_egg

# Copy the freshly built egg into your Trac environment's plugins directory
sudo cp dist/TracEpicPlugin-1.0.2-py3.*.egg /path/to/trac-env/plugins/

# Apply database migration
trac-admin /path/to/trac-env upgrade

# Restart the web front-end (Apache/mod_wsgi)
sudo systemctl restart apache2
```

> **Note on the remaining warning.** `bdist_egg` prints a single
> `setup.py install is deprecated` notice. This is intrinsic to the egg
> format (which Trac requires for drop-in `plugins/` archives) and is
> harmless — the produced egg is valid. The old `tracepic.htdocs` /
> `tracepic.templates` "Package would be ignored" warnings are **gone** as
> of v1.0.2.

**Method 2: Trac in virtual environment (fully warning-free)**

If Trac runs inside a virtualenv, use the standards-based build — it produces
a universal wheel with **zero** warnings:

```bash
source /path/to/trac/venv/bin/activate

cd /path/to/trac-epic-plugin
pip install build           # once
python3 -m build            # -> dist/TracEpicPlugin-1.0.2-py3-none-any.whl
pip install dist/TracEpicPlugin-1.0.2-py3-none-any.whl

# (editable install also works: pip install -e .)

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

#### Table sorting & pagination (`[epic]`)

The *Linked Tickets* / *Epics* table supports Trac-style column sorting
(click a header to sort, click again to toggle direction) and pagination.
Both are configurable:

```ini
[epic]
# Columns shown in the table, in order. Available fields: ticket, summary,
# component, type, status, owner, modified, priority. Unknown tokens are
# ignored, duplicates collapsed. The Remove button is always the last column.
linked_fields = ticket,summary,type,status
# Default sort as <field>/<order>. field ∈ {id, summary, component, type,
# status, owner, modified, priority}; order ∈ {asc, desc}.
# For 'priority', 'desc' lists the most severe tickets first (blocker at top).
linked_default_sort = priority/desc
# Maximum rows per page; the table paginates when there are more links.
linked_page_size = 10
```

If a value is omitted or invalid the defaults `ticket,summary,type,status`,
`priority/desc` and `10` are used.  The **Priority** column (when shown) is a
compact colour-coded badge (its colour matches the row's priority) with the
priority name revealed on hover, so it does not eat into the width of the
Summary column.  **Closed** tickets have their whole row greyed out
(Trac-style) with a strike-through ticket-id link.

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

### Security & permissions

The plugin gates every operation on Trac's standard ticket permissions,
checked **per ticket** (not just globally), so fine-grained policies such as
`AuthzPolicy` or per-component restrictions are honoured:

| Operation | Required permission |
|-----------|--------------------|
| See the *Epics* / *Linked Tickets* section on a ticket | `TICKET_VIEW` on that ticket |
| Autocomplete search (`/epic/search`) | `TICKET_VIEW` — each candidate is additionally filtered by `TICKET_VIEW` on that specific ticket |
| Add or remove a link (web `/epic/link` or RPC `addEpicLink`/`removeEpicLink`) | `TICKET_MODIFY` on **both** the epic and the ticket |

Notes:

* Adding or removing a link mutates the changelog of **both** tickets, so
  `TICKET_MODIFY` is required on each; a user denied on either ticket is
  rejected (HTTP `403` for the web endpoint, an error for RPC).
* The web `/epic/link` endpoint is `POST`-only and validates Trac's
  `__FORM_TOKEN` (CSRF protection) before doing anything.
* All ticket-supplied values are rendered client-side with jQuery
  `.text()`/`.attr()` (never `.html()`), and the server fragment is an
  auto-escaped Jinja2 template, so stored ticket data cannot inject markup.

### Changelog field

Link additions and removals are recorded in each ticket's history under the
change field named **`epic_link`** (constant `CHANGELOG_FIELD` in
`tracepic/api.py`). In Trac's ticket history these entries render generically
(old/new values are the referenced `#id`). If you filter or report on ticket
history programmatically, match on `field = 'epic_link'`.

> **Implementation note.** For efficiency and transactional consistency the
> plugin writes these changelog rows (and the `changetime` bump) directly via
> SQL rather than through Trac's `Ticket` model. As a consequence,
> `ITicketChangeListener` notifications (e.g. e-mail) do **not** fire for link
> changes. This trade-off is documented in `EpicLinkSystem._write_change`.
> Orphaned links are still cleaned up automatically: the plugin implements
> `ITicketChangeListener.ticket_deleted` to drop links referencing a deleted
> ticket.

### Running the tests

```bash
pip install -e .
python -m pytest tests/ -v      # Python model, handlers, authz, config
node tests/test_epic_js.js      # client-side sort/paginate logic
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

# Собрать egg (флаг -B избавляет от проблем с правами на pyc).
# ВАЖНО: собирайте тем же Python, под которым работает Trac, чтобы egg
# получил соответствующий тег -pyX.Y (например, на Python 3.13 будет
# ...-py3.13.egg). Trac игнорирует egg с несовпадающим тегом Python.
python3 -B setup.py bdist_egg

# Скопировать собранный egg в директорию plugins вашего окружения Trac
sudo cp dist/TracEpicPlugin-1.0.2-py3.*.egg /path/to/trac-env/plugins/

# Применить миграцию БД
trac-admin /path/to/trac-env upgrade

# Перезапустить веб-сервер (Apache/mod_wsgi)
sudo systemctl restart apache2
```

> **О единственном оставшемся предупреждении.** `bdist_egg` выводит одно
> уведомление `setup.py install is deprecated`. Оно неотъемлемо для формата
> egg (который Trac требует для plugins-директории) и безвредно — собранный
> egg корректен. Прежние предупреждения `tracepic.htdocs` /
> `tracepic.templates` («Package would be ignored») **устранены** в v1.0.2.

**Метод 2: Trac в виртуальном окружении (полностью без предупреждений)**

Если Trac работает в virtualenv, используйте стандартную сборку — она даёт
универсальный wheel с **нулём** предупреждений:

```bash
source /path/to/trac/venv/bin/activate

cd /path/to/trac-epic-plugin
pip install build           # однократно
python3 -m build            # -> dist/TracEpicPlugin-1.0.2-py3-none-any.whl
pip install dist/TracEpicPlugin-1.0.2-py3-none-any.whl

# (editable-установка тоже работает: pip install -e .)

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

#### Сортировка и постраничный вывод таблицы (`[epic]`)

Таблица *Linked Tickets* / *Epics* поддерживает сортировку по клику на
заголовок столбца (как в отчётах Trac; повторный клик меняет направление)
и постраничный вывод. Оба параметра настраиваются:

```ini
[epic]
# Набор и порядок столбцов таблицы. Доступные поля: ticket, summary,
# component, type, status, owner, modified, priority. Неизвестные токены
# игнорируются, дубликаты убираются. Кнопка Remove всегда последний столбец.
linked_fields = ticket,summary,type,status
# Сортировка по умолчанию в формате <поле>/<направление>.
# поле ∈ {id, summary, component, type, status, owner, modified, priority};
# направление ∈ {asc, desc}.
# Для 'priority' значение 'desc' ставит самые важные тикеты первыми (blocker вверху).
linked_default_sort = priority/desc
# Максимальное число строк на странице; при превышении включается пагинация.
linked_page_size = 10
```

Если параметр не задан или указан неверно, используются значения по
умолчанию `ticket,summary,type,status`, `priority/desc` и `10`. Столбец
**Priority** (если включён) отображается компактным цветным индикатором
(цвет соответствует приоритету строки), а название приоритета показывается
во всплывающей подсказке при наведении — чтобы не сокращать ширину столбца
Summary. Закрытые (**closed**) тикеты отображаются серой строкой (в стиле
Trac) с зачёркнутым номером тикета.

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

### Безопасность и права доступа

Плагин контролирует каждую операцию по стандартным правам Trac на тикеты,
проверяя их **для каждого тикета отдельно** (а не только глобально), поэтому
тонко-гранулированные политики вроде `AuthzPolicy` или ограничений по
компонентам учитываются:

| Операция | Требуемое право |
|----------|-----------------|
| Видеть блок *Epics* / *Linked Tickets* на тикете | `TICKET_VIEW` на этом тикете |
| Поиск-автодополнение (`/epic/search`) | `TICKET_VIEW`; каждый кандидат дополнительно фильтруется по `TICKET_VIEW` на конкретном тикете |
| Добавить/удалить связь (веб `/epic/link` или RPC `addEpicLink`/`removeEpicLink`) | `TICKET_MODIFY` на **обоих** тикетах — эпике и тикете |

Замечания:

* Добавление или удаление связи изменяет историю **обоих** тикетов, поэтому
  требуется `TICKET_MODIFY` на каждом; пользователю, которому запрещён любой
  из тикетов, операция отклоняется (HTTP `403` для веб-эндпоинта, ошибка для
  RPC).
* Веб-эндпоинт `/epic/link` принимает только `POST` и проверяет токен
  `__FORM_TOKEN` (защита от CSRF).
* Все значения из тикетов выводятся на стороне клиента через jQuery
  `.text()`/`.attr()` (никогда `.html()`), а серверный фрагмент — это
  автоэкранируемый шаблон Jinja2, поэтому данные тикетов не могут внедрить
  разметку.

### Поле истории изменений

Добавление и удаление связей записывается в историю каждого тикета под именем
поля **`epic_link`** (константа `CHANGELOG_FIELD` в `tracepic/api.py`). В
истории Trac эти записи отображаются обобщённо (старое/новое значение — это
`#id`). Для программной фильтрации истории используйте `field = 'epic_link'`.

> **Замечание по реализации.** Ради производительности и транзакционной
> целостности плагин пишет эти записи истории (и обновление `changetime`)
> напрямую через SQL, а не через модель `Ticket` Trac. Как следствие,
> уведомления `ITicketChangeListener` (например, e-mail) для изменений связей
> **не** срабатывают. Компромисс задокументирован в
> `EpicLinkSystem._write_change`. Осиротевшие связи при этом очищаются
> автоматически: плагин реализует `ITicketChangeListener.ticket_deleted`,
> удаляя связи, ссылающиеся на удалённый тикет.

### Запуск тестов

```bash
pip install -e .
python -m pytest tests/ -v      # модель, обработчики, права, конфигурация
node tests/test_epic_js.js      # клиентская логика сортировки/пагинации
```

---

## License

BSD-3-Clause.
