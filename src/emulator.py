#!/usr/bin/env python3
"""
Эмулятор командной оболочки UNIX-подобной ОС.
Этапы 1–5: REPL, конфигурация, VFS, основные команды, cp.
"""

import os
import sys
import json
import base64
import getpass
import socket
import argparse

# ------------------ Отладочный вывод ------------------
DEBUG = False

def dprint(*args, **kwargs):
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)


# ------------------ Исключения ------------------
class VFSLoadError(Exception):
    pass


class ParseError(Exception):
    pass


class CommandError(Exception):
    pass


# ======================================================
#  ЭТАП 3: VFS
# ======================================================
class VFSNode:
    __slots__ = ('name', 'is_dir', 'content', 'children')

    def __init__(self, name, is_dir=False, content=None, children=None):
        self.name = name
        self.is_dir = is_dir
        self.content = content
        self.children = children if children is not None else {}

    def clone(self):
        n = VFSNode(self.name, self.is_dir, self.content)
        n.children = {k: v.clone() for k, v in self.children.items()}
        return n


class VFS:
    """
    Виртуальная файловая система, загружаемая из JSON в память.
    Все операции производятся только в памяти.
    """

    def __init__(self):
        self.root = VFSNode("/", is_dir=True)
        self.cwd = "/"

    @classmethod
    def from_json(cls, path):
        vfs = cls()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise VFSLoadError(f"VFS file not found: {path}")
        except PermissionError as e:
            raise VFSLoadError(f"Cannot read VFS file: {e}")
        except json.JSONDecodeError as e:
            raise VFSLoadError(f"Invalid VFS JSON format: {e}")
        if not isinstance(data, dict):
            raise VFSLoadError("VFS root must be an object")
        vfs.root = vfs._parse_node("/", data)
        if not vfs.root.is_dir:
            raise VFSLoadError("VFS root must be a directory")
        return vfs

    def _parse_node(self, name, data):
        if not isinstance(data, dict):
            raise VFSLoadError(f"Node '{name}' must be an object")
        t = data.get("type")
        if t == "dir":
            node = VFSNode(name, is_dir=True)
            children = data.get("children", {})
            if not isinstance(children, dict):
                raise VFSLoadError(f"Children of '{name}' must be an object")
            for cn, cd in children.items():
                node.children[cn] = self._parse_node(cn, cd)
            return node
        elif t == "file":
            content = data.get("content", "")
            enc = data.get("encoding", "utf-8")
            if enc == "base64":
                try:
                    content_bytes = base64.b64decode(content)
                except Exception as e:
                    raise VFSLoadError(f"Bad base64 in '{name}': {e}")
            else:
                if not isinstance(content, str):
                    raise VFSLoadError(f"File content '{name}' must be string")
                content_bytes = content.encode('utf-8')
            return VFSNode(name, is_dir=False, content=content_bytes)
        else:
            raise VFSLoadError(f"Unknown node type for '{name}': {t}")

    def normalize(self, path, base=None):
        if path is None or path == "":
            path = self.cwd
        if not path.startswith('/'):
            base = base if base is not None else self.cwd
            path = base.rstrip('/') + '/' + path
        parts = []
        for p in path.split('/'):
            if p == '' or p == '.':
                continue
            if p == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return '/' + '/'.join(parts)

    def get_node(self, path):
        npath = self.normalize(path)
        if npath == '/':
            return self.root
        node = self.root
        for part in npath.strip('/').split('/'):
            if not node.is_dir:
                return None
            if part not in node.children:
                return None
            node = node.children[part]
        return node

    def get_parent_and_name(self, path):
        npath = self.normalize(path)
        if npath == '/':
            return None, None
        parts = npath.strip('/').split('/')
        name = parts[-1]
        parent_path = '/' + '/'.join(parts[:-1])
        parent = self.get_node(parent_path)
        return parent, name


# ======================================================
#  ЭТАП 1: парсер
# ======================================================
def tokenize(line):
    """
    Разбивает строку на токены с поддержкой одинарных/двойных кавычек
    и экранирования через backslash.
    """
    tokens = []
    cur = []
    in_single = False
    in_double = False
    escape = False
    started = False

    for ch in line:
        if escape:
            cur.append(ch)
            escape = False
            started = True
            continue
        if in_single:
            if ch == "'":
                in_single = False
            else:
                cur.append(ch)
            started = True
            continue
        if in_double:
            if ch == '"':
                in_double = False
            elif ch == '\\':
                escape = True
            else:
                cur.append(ch)
            started = True
            continue
        if ch == "'":
            in_single = True
            started = True
            continue
        if ch == '"':
            in_double = True
            started = True
            continue
        if ch == '\\':
            escape = True
            started = True
            continue
        if ch.isspace():
            if started:
                tokens.append(''.join(cur))
                cur = []
                started = False
            continue
        cur.append(ch)
        started = True

    if in_single:
        raise ParseError("unterminated single quote")
    if in_double:
        raise ParseError("unterminated double quote")
    if escape:
        raise ParseError("trailing backslash")
    if started:
        tokens.append(''.join(cur))
    return tokens


# ======================================================
#  SHELL — REPL и команды
# ======================================================
class Shell:
    def __init__(self, vfs):
        self.vfs = vfs
        self.history = []
        self.running = True

    # ---------- Приглашение к вводу (этап 1) ----------
    def prompt(self):
        try:
            user = getpass.getuser()
        except Exception:
            user = os.environ.get('USER', 'user')
        try:
            host = socket.gethostname()
        except Exception:
            host = 'localhost'
        cwd = self.vfs.cwd
        if cwd != '/' and cwd.endswith('/'):
            cwd = cwd.rstrip('/')
        return f"{user}@{host}:{cwd}$ "

    # ---------- Выполнение строки ----------
    def execute_line(self, line):
        stripped = line.strip()
        if not stripped:
            return 0
        self.history.append(line)

        try:
            tokens = tokenize(line)
        except ParseError as e:
            print(f"parse error: {e}", file=sys.stderr)
            return 2

        if not tokens:
            return 0

        cmd = tokens[0]
        args = tokens[1:]
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            print(f"{cmd}: command not found", file=sys.stderr)
            return 127

        try:
            rc = handler(args)
            return rc if isinstance(rc, int) else 0
        except CommandError as e:
            print(f"{cmd}: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"{cmd}: internal error: {e}", file=sys.stderr)
            return 1

    # ---------- exit ----------
    def cmd_exit(self, args):
        if args:
            raise CommandError("too many arguments")
        self.running = False
        return 0

    # ---------- ls (этап 4) ----------
    def cmd_ls(self, args):
        path = None
        show_all = False
        long_fmt = False
        for a in args:
            if a.startswith('-') and a != '-':
                for c in a[1:]:
                    if c == 'a':
                        show_all = True
                    elif c == 'l':
                        long_fmt = True
                    else:
                        raise CommandError(f"invalid option -- '{c}'")
            else:
                if path is not None:
                    raise CommandError("too many arguments")
                path = a

        node = self.vfs.get_node(path) if path else self.vfs.get_node(self.vfs.cwd)
        target_display = path if path else self.vfs.cwd
        if node is None:
            raise CommandError(
                f"cannot access '{target_display}': No such file or directory")

        if node.is_dir:
            names = sorted(node.children.keys())
            if not show_all:
                names = [n for n in names if not n.startswith('.')]
            if not names:
                return 0
            if long_fmt:
                for n in names:
                    c = node.children[n]
                    t = 'd' if c.is_dir else '-'
                    size = 0 if c.is_dir else len(c.content or b'')
                    print(f"{t}rw-r--r-- 1 user user {size:>6} {n}")
            else:
                print('  '.join(names))
        else:
            print(node.name)
        return 0

    # ---------- cd (этап 4) ----------
    def cmd_cd(self, args):
        if len(args) > 1:
            raise CommandError("too many arguments")
        target = args[0] if args else '/'
        node = self.vfs.get_node(target)
        if node is None:
            raise CommandError(f"{target}: No such file or directory")
        if not node.is_dir:
            raise CommandError(f"{target}: Not a directory")
        self.vfs.cwd = self.vfs.normalize(target)
        return 0

    # ---------- history (этап 4) ----------
    def cmd_history(self, args):
        if args:
            raise CommandError("no arguments expected")
        for i, h in enumerate(self.history, 1):
            print(f"{i:>5}  {h}")
        return 0

    # ---------- head (этап 4) ----------
    def cmd_head(self, args):
        n = 10
        files = []
        i = 0
        while i < len(args):
            a = args[i]
            if a == '-n':
                i += 1
                if i >= len(args):
                    raise CommandError("option requires an argument -- 'n'")
                try:
                    n = int(args[i])
                except ValueError:
                    raise CommandError(f"invalid number of lines: '{args[i]}'")
            elif a.startswith('-n') and len(a) > 2:
                try:
                    n = int(a[2:])
                except ValueError:
                    raise CommandError(f"invalid number of lines: '{a[2:]}'")
            elif a.startswith('-') and a != '-':
                raise CommandError(f"invalid option -- '{a}'")
            else:
                files.append(a)
            i += 1

        if not files:
            raise CommandError("missing file operand")

        rc = 0
        for f in files:
            node = self.vfs.get_node(f)
            if node is None:
                print(f"head: cannot open '{f}' for reading: "
                      f"No such file or directory", file=sys.stderr)
                rc = 1
                continue
            if node.is_dir:
                print(f"head: error reading '{f}': Is a directory",
                      file=sys.stderr)
                rc = 1
                continue
            text = (node.content or b'').decode('utf-8', errors='replace')
            for l in text.splitlines()[:n]:
                print(l)
        return rc

    # ---------- rev (этап 4) ----------
    def cmd_rev(self, args):
        if not args:
            raise CommandError("missing file operand")
        rc = 0
        for f in args:
            node = self.vfs.get_node(f)
            if node is None:
                print(f"rev: cannot open '{f}': No such file or directory",
                      file=sys.stderr)
                rc = 1
                continue
            if node.is_dir:
                print(f"rev: '{f}': Is a directory", file=sys.stderr)
                rc = 1
                continue
            text = (node.content or b'').decode('utf-8', errors='replace')
            for line in text.splitlines():
                print(line[::-1])
        return rc

    # ---------- cp (этап 5) ----------
    def cmd_cp(self, args):
        if len(args) < 2:
            raise CommandError("missing file operand")
        if len(args) > 2:
            raise CommandError("extra operand")
        src, dst = args

        src_node = self.vfs.get_node(src)
        if src_node is None:
            raise CommandError(f"cannot stat '{src}': No such file or directory")

        dst_node = self.vfs.get_node(dst)
        if dst_node is not None and dst_node.is_dir:
            target_name = src_node.name
            if target_name in dst_node.children:
                raise CommandError(
                    f"cannot create '{dst.rstrip('/')}/{target_name}': File exists")
            dst_node.children[target_name] = src_node.clone()
            return 0

        parent, name = self.vfs.get_parent_and_name(dst)
        if parent is None:
            raise CommandError(f"cannot create '{dst}': Invalid path")
        if not parent.is_dir:
            raise CommandError(f"cannot create '{dst}': Not a directory")
        if name in parent.children:
            raise CommandError(f"cannot create '{dst}': File exists")
        parent.children[name] = src_node.clone()
        return 0


# ======================================================
#  ЭТАП 2: стартовый скрипт
# ======================================================
def run_startup_script(shell, path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"emulator: startup script not found: {path}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"emulator: error reading startup script: {e}", file=sys.stderr)
        return False

    prompt = shell.prompt()
    for raw in lines:
        line = raw.rstrip('\n')
        # имитируем диалог: показываем приглашение и ввод
        print(f"{prompt}{line}")
        try:
            shell.execute_line(line)
        except Exception as e:
            # ошибочные строки — пропускаем
            print(f"emulator: error in script line: {e}", file=sys.stderr)
        if not shell.running:
            break
        prompt = shell.prompt()
    return True


# ======================================================
#  Интерактивный REPL
# ======================================================
def interactive_loop(shell):
    while shell.running:
        try:
            line = input(shell.prompt())
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue
        shell.execute_line(line)


# ======================================================
#  main
# ======================================================
def main():
    parser = argparse.ArgumentParser(
        description="Эмулятор shell для UNIX-подобной ОС")
    parser.add_argument("-v", "--vfs", default=None,
                        help="Путь к JSON-файлу VFS")
    parser.add_argument("-s", "--script", default=None,
                        help="Путь к стартовому скрипту")
    parser.add_argument("--debug", action="store_true",
                        help="Печатать отладочную информацию")
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    # --- Этап 2: отладочный вывод всех заданных параметров ---
    print("[DEBUG] Параметры запуска эмулятора:", file=sys.stderr)
    print(f"[DEBUG]   VFS path       : {args.vfs}", file=sys.stderr)
    print(f"[DEBUG]   Startup script : {args.script}", file=sys.stderr)
    print(f"[DEBUG]   Debug mode     : {args.debug}", file=sys.stderr)

    # --- Загрузка VFS ---
    vfs = VFS()
    if args.vfs:
        try:
            vfs = VFS.from_json(args.vfs)
        except VFSLoadError as e:
            print(f"emulator: VFS load error: {e}", file=sys.stderr)
            sys.exit(1)

    shell = Shell(vfs)

    # --- Выполнение стартового скрипта ---
    if args.script:
        run_startup_script(shell, args.script)

    # --- Интерактивный режим ---
    if shell.running:
        interactive_loop(shell)


if __name__ == "__main__":
    main()