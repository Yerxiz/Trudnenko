# Shell Emulator

Эмулятор командной оболочки UNIX-подобной ОС на Python 3.
Поддерживает виртуальную файловую систему (VFS) в памяти, загружаемую из
JSON, набор команд, имитирующих работу в `bash`/`sh`, и стартовые скрипты
для автоматического прогона сценариев.

Проект включает пять этапов:

| Этап                      | Что добавлено                                                    |
|---------------------------|------------------------------------------------------------------|
| 1. REPL                   | Интерактивный цикл, приглашение из данных ОС, парсер с кавычками |
| 2. Конфигурация           | Параметры `--vfs` и `--script`, стартовые скрипты                |
| 3. VFS                    | Виртуальная ФС в памяти, загрузка из JSON, base64                |
| 4. Основные команды       | `ls`, `cd`, `history`, `head`, `rev`                             |
| 5. Дополнительные команды | `cp` — копирование внутри VFS                                    |

---

## Содержание

1. [Общее описание](#1-общее-описание)
2. [Функции и настройки](#2-функции-и-настройки)
3. [Сборка и запуск тестов](#3-сборка-и-запуск-тестов)
4. [Примеры использования](#4-примеры-использования)

---

- [Лицензия](#лицензия)

## 1. Общее описание

### Что делает проект

Shell Emulator — консольное приложение, которое ведёт диалог с
пользователем, как настоящая UNIX-оболочка. Все файловые операции
выполняются над виртуальной файловой системой (VFS), загруженной в
оперативную память из JSON-файла. **Реальная файловая система машины,
на которой запущен эмулятор, не затрагивается**: JSON-файл читается
один раз при старте, дальнейшие изменения (`cp`, `cd`) существуют
только в памяти и исчезают после выхода.

### Требования к окружению

- **Python 3.10+** (используется синтаксис `str | None`, `list[str]`,
  `match/case` не задействован, но аннотации типов требуют 3.10).
- Операционная система: Linux, macOS, Windows.
- Никаких внешних зависимостей — только стандартная библиотека.

### Структура проекта

```
emulator/
├── src/
│   └── terminal.py             # весь код эмулятора
├── scripts/
│   ├── startup_vfs.txt         # скрипт этапа 3: все команды работы с VFS
│   ├── startup_stage4.txt      # скрипт этапа 4: ls, cd, history, head, rev
│   ├── startup_stage5.txt      # скрипт этапа 5: cp во всех режимах
│   ├── startup_demo.txt        # демонстрационный скрипт этапа 2
│   ├── startup_with_errors.txt # скрипт с ошибками этапа 2
│   ├── run_all.ps1             # прогон всех тестов (PowerShell)
│   └── run_all.bat             # прогон всех тестов (Windows CMD)
├── vfs/
│   ├── minimal.json            # VFS: один файл
│   ├── basic.json              # VFS: файлы и папки
│   ├── deep.json               # VFS: минимум 3 уровня вложенности
│   ├── binary.json             # VFS: файл в base64
│   ├── invalid.json            # намеренно битый JSON (для тестов)
│   └── README.md               # описание тестовых VFS
├── .gitignore
└── README.md
```

### Архитектура

Код построен вокруг трёх классов:

- **`VFS`** — виртуальная файловая система. Хранит дерево узлов
  (директории и файлы) в виде вложенных словарей Python. Предоставляет
  методы `list_dir`, `read_file`, `is_dir`, `stat`, `tree_lines`, `copy`.
  Все ошибки — через собственное исключение `VFSError`.
- **`Console`** — оболочка. Держит текущую директорию (`cwd`), историю
  команд, разбирает ввод, вызывает хендлеры команд.
- **`main()`** — точка входа. Разбирает аргументы командной строки,
  загружает VFS, создаёт `Console`, запускает REPL или стартовый скрипт.

Такое разделение позволяет легко добавлять команды: новая команда —
это метод `cmd_*` в `Console` и, если нужно, метод в `VFS`.

---

## 2. Функции и настройки

### 2.1. Параметры командной строки

| Параметр          | Обязательный | Описание                                                                                 |
|-------------------|--------------|------------------------------------------------------------------------------------------|
| `--vfs <path>`    | **да**       | Путь к JSON-файлу с описанием VFS                                                        |
| `--script <path>` | нет          | Путь к стартовому скрипту. После его выполнения эмулятор переходит в интерактивный режим |
| `-h`, `--help`    | —            | Справка по параметрам                                                                    |

При запуске печатается отладочный вывод всех заданных параметров:

```
=== Shell Emulator: configuration ===
VFS source     : vfs/basic.json
VFS in memory  : loaded (root has 4 entries)
Startup script : scripts/startup_stage5.txt
=====================================
```

Если VFS-файл не найден или содержит невалидный JSON, эмулятор
завершается с сообщением об ошибке и **кодом возврата 2**.

### 2.2. Формат VFS-файла (JSON)

**Директория:**

```json
{
  "type": "directory",
  "children": {
    "имя_файла": {
      "...узел..."
    },
    "имя_папки": {
      "...узел..."
    }
  }
}
```

**Текстовый файл:**

```json
{
  "type": "file",
  "content": "Hello, world!\n"
}
```

**Бинарный файл (кодировка base64):**

```json
{
  "type": "file",
  "encoding": "base64",
  "content": "SGVsbG8sIGJpbmFyeSB3b3JsZCEK"
}
```

Корневой узел обязательно должен быть `"directory"`. Имена детей не
должны содержать `/`, быть пустыми или повторяться.

### 2.3. Поддерживаемые команды

| Команда   | Синтаксис                    | Описание                                                               |
|-----------|------------------------------|------------------------------------------------------------------------|
| `ls`      | `ls [-l] [path...]`          | Список содержимого директории. `-l` — подробный формат (тип и размер). |
| `cd`      | `cd [path]`                  | Смена текущей директории. Без аргумента — в `/`.                       |
| `pwd`     | `pwd`                        | Печать текущей директории.                                             |
| `cat`     | `cat file...`                | Вывод содержимого файла.                                               |
| `tree`    | `tree [path]`                | Дерево директорий от указанной точки.                                  |
| `history` | `history [N]` / `history -c` | История команд. `N` — последние N, `-c` — очистить.                    |
| `head`    | `head [-n N] file...`        | Первые N строк файла (по умолчанию 10).                                |
| `rev`     | `rev file...`                | Переворот символов в каждой строке файла.                              |
| `cp`      | `cp [-r] source... dest`     | Копирование файлов и директорий внутри VFS.                            |
| `exit`    | `exit`                       | Выход.                                                                 |

### 2.4. Особенности `cp`

- Все изменения — **только в памяти**. JSON-файл VFS не перезаписывается.
- `cp file1 file2` — копия `file1` с новым именем `file2`.
- `cp file /existing_dir` — копия внутрь существующей директории с
  сохранением имени.
- `cp f1 f2 /existing_dir` — несколько источников в директорию.
- `cp -r dir1 dir2` — рекурсивное копирование директории.
- Копирование **не перезаписывает** существующий узел — ошибка
  `cannot overwrite`.
- Копирование директории в себя запрещено — `cannot copy into itself`.

### 2.5. Работа со стартовыми скриптами

Стартовый скрипт — обычный текстовый файл. Каждая строка — команда.

Правила обработки:

- Пустые строки и строки, начинающиеся с `#`, пропускаются.
- Строки, начинающиеся с отступа, тоже обрабатываются (отступ не важен).
- Перед каждой командой печатается приглашение и сама команда — это
  имитирует диалог с пользователем.
- Ошибочные команды (неизвестная команда, синтаксическая ошибка,
  ошибка VFS) **не прерывают** скрипт: печатается сообщение с номером
  строки, обработка продолжается.
- Команда `exit` завершает и скрипт, и эмулятор.

### 2.6. Настройки, изменяемые через код

| Что                    | Где                                   | По умолчанию |
|------------------------|---------------------------------------|--------------|
| Начальная директория   | `Console.__init__` → `self.cwd = "/"` | `/`          |
| Глубина истории команд | не ограничена                         | —            |
| Цвета вывода           | нет (все в stdout)                    | —            |
| Кодировка ввода-вывода | UTF-8 (принудительно в Windows)       | UTF-8        |

---

## 3. Сборка и запуск тестов

### 3.1. Требования

```bash
python --version     # должно быть 3.10 или выше
```

Установка зависимостей **не требуется** — используется только
стандартная библиотека Python.

### 3.2. Запуск эмулятора вручную

Из корня проекта:

```bash
# только VFS, интерактивный режим
python src/terminal.py --vfs vfs/basic.json

# с прогоном стартового скрипта, затем интерактивный режим
python src/terminal.py --vfs vfs/basic.json --script scripts/startup_stage5.txt
```

В Windows, если команда `python` не найдена:

```powershell
py src\terminal.py --vfs vfs\basic.json
```

### 3.3. Полный прогон тестов

Каждый runner-скрипт запускает эмулятор **9 раз** — по одному на разные
варианты VFS и разные стартовые скрипты, включая сценарии ошибок
(несуществующий VFS, битый JSON, отсутствующий стартовый скрипт).

**PowerShell (Windows / Linux / macOS):**

```powershell
./scripts/run_all.ps1
```

**Windows CMD:**

```cmd
scripts\run_all.bat
```

Все скрипты после завершения оставляют окно/терминал открытым,
чтобы был виден вывод. Код возврата эмулятора печатается
после каждого кейса (`Exit code: 0` — успех, `2` — ошибка загрузки VFS).

### 3.4. Что проверяют тесты

| № | VFS            | Стартовый скрипт     | Проверяемая функциональность         |
|---|----------------|----------------------|--------------------------------------|
| 1 | `minimal.json` | `startup_vfs.txt`    | VFS из одного файла                  |
| 2 | `basic.json`   | `startup_vfs.txt`    | VFS с несколькими папками            |
| 3 | `deep.json`    | `startup_vfs.txt`    | Многоуровневая иерархия              |
| 4 | `binary.json`  | `startup_vfs.txt`    | Файл в base64                        |
| 5 | *(нет)*        | —                    | Ошибка: файл VFS не найден           |
| 6 | `invalid.json` | —                    | Ошибка: битый JSON                   |
| 7 | `basic.json`   | *(нет)*              | Ошибка: скрипт не найден             |
| 8 | `basic.json`   | `startup_stage4.txt` | `ls`, `cd`, `history`, `head`, `rev` |
| 9 | `basic.json`   | `startup_stage5.txt` | `cp` во всех режимах                 |

### 3.5. Проверка, что VFS не изменяется на диске

После любого запуска:

```bash
git status vfs/
```

Должно быть «nothing to commit» — Git не увидит изменений в JSON-файлах.
Это подтверждает требование «все операции — только в памяти».

---

## 4. Примеры использования

### 4.1. Простая интерактивная сессия

```bash
$ python src/terminal.py --vfs vfs/basic.json
=== Shell Emulator: configuration ===
VFS source     : vfs/basic.json
VFS in memory  : loaded (root has 4 entries)
Startup script : <none>
=====================================
user@host:/$ pwd
/
user@host:/$ ls
etc/  home/  readme.txt  tmp/
user@host:/$ ls -l /etc
-      20  hosts
-      28  os-release
```

*(в этом примере вывод `ls -l` упрощён — фактически печатается размер и тип)*

```
user@host:/$ cd etc
user@host:/etc$ cat os-release
NAME=EmulatorOS
VERSION=1.0
user@host:/etc$ cd ..
user@host:/$ tree
/
├── etc/
│   ├── hosts
│   └── os-release
├── home/
│   └── user/
│       ├── notes.txt
│       └── todo.md
├── readme.txt
└── tmp/
user@host:/$ exit
```

### 4.2. Обработка ошибок

```bash
user@host:/$ cat /nowhere
cat: no such file or directory: /nowhere
user@host:/$ cd /etc/hosts
cd: not a directory: /etc/hosts
user@host:/$ cp /etc /etc-copy
cp: -r not specified; omitting directory '/etc'
user@host:/$ cp /etc/hosts /etc/hosts
cp: '/etc/hosts' and '/etc/hosts' are the same file
user@host:/$ ls /etc /tmp /nowhere
/etc:
hosts  os-release

/tmp:

/nowhere:
ls: no such file or directory: /nowhere
user@host:/$ head
head: missing file operand
user@host:/$ history abc
history: abc: numeric argument required
user@host:/$ history 1 2
history: too many arguments
```

### 4.3. История команд

```bash
user@host:/$ ls
etc/  home/  readme.txt  tmp/
user@host:/$ cd /etc
user@host:/etc$ pwd
/etc
user@host:/etc$ history
1  ls
2  cd /etc
3  pwd
4  history
user@host:/etc$ history 2
4  history
5  history 2
user@host:/etc$ history -c
user@host:/etc$ history
1  history
user@host:/etc$
```

### 4.4. `head` и `rev`

Допустим, `/home/user/notes.txt` содержит:

```
First note
Second note
```

```bash
user@host:/$ head -n 1 /home/user/notes.txt
First note
user@host:/$ rev /home/user/notes.txt
eton tsriF
eton dnoceS
```

### 4.5. Копирование внутри VFS

```bash
user@host:/$ cp /etc/hosts /etc/hosts.bak
'/etc/hosts' -> '/etc/hosts.bak'
user@host:/$ ls /etc
hosts  hosts.bak  os-release
user@host:/$ cp /etc/hosts /tmp
'/etc/hosts' -> '/tmp/hosts'
user@host:/$ cp -r /etc /etc-backup
'/etc' -> '/etc-backup'
user@host:/$ tree /etc-backup
/etc-backup
├── hosts
├── hosts.bak
└── os-release

# На диске ничего не изменилось:
$ git status vfs/
nothing to commit, working tree clean
```

### 4.6. Прогон стартового скрипта с записью в файл

```bash
python src/terminal.py --vfs vfs/basic.json --script scripts/startup_stage5.txt \
    > stage5.log 2>&1
cat stage5.log
```

Файл `stage5.log` содержит полный диалог: приглашение, команды, вывод,
сообщения об ошибках.

### 4.7. Свой VFS-файл

Создайте `vfs/my.json`:

```json
{
  "type": "directory",
  "children": {
    "data": {
      "type": "directory",
      "children": {
        "hello.txt": {
          "type": "file",
          "content": "Hello!\n"
        }
      }
    }
  }
}
```

Запустите:

```bash
python src/terminal.py --vfs vfs/my.json
```

```
user@host:/$ tree
/
└── data/
    └── hello.txt
user@host:/$ cat /data/hello.txt
Hello!
```

---

## Лицензия

Учебный проект. Свободно используется в образовательных целях.