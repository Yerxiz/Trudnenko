import argparse
import base64
import json
import os
import sys
import getpass
import socket
import shlex

# Чтобы box-drawing символы корректно печатались в Windows-консоли
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class VFSError(Exception):
    """Ошибка виртуальной файловой системы."""


class VFS:
    """Виртуальная ФС, полностью загруженная в память из JSON."""

    def __init__(self, root: dict) -> None:
        if not isinstance(root, dict) or root.get("type") != "directory":
            raise VFSError("VFS root must be a 'directory' node")
        self.root = root

    # ---------- Загрузка и валидация ----------
    @classmethod
    def from_file(cls, path: str) -> "VFS":
        if not os.path.isfile(path):
            raise VFSError(f"VFS file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise VFSError(f"invalid VFS JSON: {exc}") from exc
        vfs = cls(data)
        vfs._validate(vfs.root)
        return vfs

    @classmethod
    def _validate(cls, node: dict) -> None:
        if not isinstance(node, dict):
            raise VFSError("each VFS node must be a JSON object")
        t = node.get("type")
        if t == "directory":
            children = node.get("children", {})
            if not isinstance(children, dict):
                raise VFSError("directory 'children' must be an object")
            for name, child in children.items():
                if not isinstance(name, str) or not name or "/" in name:
                    raise VFSError(f"invalid entry name: {name!r}")
                cls._validate(child)
        elif t == "file":
            if "content" not in node:
                raise VFSError("file node must have 'content'")
            if not isinstance(node["content"], str):
                raise VFSError("file 'content' must be a string")
            enc = node.get("encoding", "utf-8")
            if enc not in ("utf-8", "base64"):
                raise VFSError(f"unsupported file encoding: {enc!r}")
        else:
            raise VFSError(f"unknown VFS node type: {t!r}")

    # ---------- Внутренние помощники ----------
    @staticmethod
    def normalize(cwd: str, path: str) -> str:
        """Абсолютный нормализованный путь относительно cwd."""
        if not path:
            return cwd
        combined = path if path.startswith("/") else (
            cwd.rstrip("/") + "/" + path if cwd != "/" else "/" + path)
        parts = []
        for p in combined.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if parts:
                    parts.pop()
                # выше корня — не выходим, остаёмся в "/"
            else:
                parts.append(p)
        return "/" + "/".join(parts) if parts else "/"

    def _node(self, abs_path: str) -> dict:
        node = self.root
        if abs_path == "/":
            return node
        for part in abs_path.strip("/").split("/"):
            if node.get("type") != "directory":
                raise VFSError(f"not a directory: {abs_path}")
            children = node.get("children", {})
            if part not in children:
                raise VFSError(f"no such file or directory: {abs_path}")
            node = children[part]
        return node

    # ---------- Публичные операции ----------
    def is_dir(self, abs_path: str) -> bool:
        return self._node(abs_path).get("type") == "directory"

    def list_dir(self, cwd: str, path: str = "") -> list[str]:
        target = self.normalize(cwd, path)
        node = self._node(target)
        if node.get("type") != "directory":
            raise VFSError(f"not a directory: {target}")
        return sorted(node.get("children", {}).keys())

    def read_file(self, cwd: str, path: str) -> bytes:
        target = self.normalize(cwd, path)
        node = self._node(target)
        if node.get("type") != "file":
            raise VFSError(f"not a file: {target}")
        content = node["content"]
        enc = node.get("encoding", "utf-8")
        if enc == "base64":
            try:
                return base64.b64decode(content, validate=True)
            except Exception as exc:
                raise VFSError(f"invalid base64 in {target}: {exc}") from exc
        return content.encode("utf-8")

    def stat(self, cwd: str, path: str) -> dict:
        """Информация об узле: {'type': 'file'|'directory', 'size': int}."""
        target = self.normalize(cwd, path)
        node = self._node(target)
        t = node.get("type")
        if t == "directory":
            return {"type": "directory", "size": len(node.get("children", {}))}
        content = node.get("content", "")
        size = len(content)
        if node.get("encoding") == "base64":
            try:
                size = len(base64.b64decode(content, validate=True))
            except Exception:
                pass  # fallback — длина строки
        return {"type": "file", "size": size}

    def tree_lines(self, cwd: str, path: str = "") -> list[str]:
        target = self.normalize(cwd, path)
        node = self._node(target)
        if node.get("type") != "directory":
            raise VFSError(f"not a directory: {target}")
        lines: list[str] = []
        self._tree_walk(node, "", lines)
        return lines

    def _tree_walk(self, node: dict, prefix: str, lines: list[str]) -> None:
        items = sorted(node.get("children", {}).items())
        for i, (name, child) in enumerate(items):
            last = i == len(items) - 1
            branch = "└── " if last else "├── "
            suffix = "/" if child.get("type") == "directory" else ""
            lines.append(f"{prefix}{branch}{name}{suffix}")
            if child.get("type") == "directory":
                next_prefix = prefix + ("    " if last else "│   ")
                self._tree_walk(child, next_prefix, lines)


class Console:
    COMMANDS = ("ls", "cd", "cat", "pwd", "tree",
                "history", "head", "rev", "exit")

    def __init__(self, vfs: VFS, script_path: str | None = None) -> None:
        self.running = True
        self.prompt = "username@hostname:~$ "
        self.vfs = vfs
        self.script_path = os.path.abspath(script_path) if script_path else None
        self.cwd = "/"  # логический путь внутри vfs
        self.history: list[list[str]] = []

    # ---------- Диагностика ----------
    def dump_config(self, vfs_source: str) -> None:
        root_children = len(self.vfs.root.get("children", {}))
        print("=== Shell Emulator: configuration ===")
        print(f"VFS root       : {vfs_source}")
        print(f"VFS in memory  : loaded (root has {root_children} entries)")
        print(f"Startup script : {self.script_path or '<none>'}")
        print("=========================================")

    # ---------- Приглашение ----------
    def get_prompt(self) -> str:
        user = getpass.getuser()
        host = socket.gethostname().split(".")[0]  # короткое имя хоста
        self.prompt = f"{user}@{host}:{self.cwd}$ "
        return self.prompt

    # ---------- Парсер ----------
    @staticmethod
    def parse(line: str) -> list[str]:
        try:
            return shlex.split(line)
        except ValueError as exc:
            raise ValueError(f"parse error: {exc}") from exc

    # ---------- Диспетчер ----------
    def execute(self, argv: list[str]) -> None:
        if not argv:
            return
        self.history.append(argv)
        cmd, args = argv[0], argv[1:]
        handlers = {
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "cat": self.cmd_cat,
            "pwd": self.cmd_pwd,
            "tree": self.cmd_tree,
            "history": self.cmd_history,
            "head": self.cmd_head,
            "rev": self.cmd_rev,
            "exit": self.cmd_exit
        }
        handler = handlers.get(cmd)
        if handler is None:
            print(f"{cmd}: command not found", file=sys.stderr)
            return
        try:
            handler(args)
        except VFSError as exc:
            print(f"{cmd}: {exc}", file=sys.stderr)

    # ---------- exit ----------
    def cmd_exit(self, argv: list[str]) -> None:
        self.running = False

    # ---------- ls ----------
    def cmd_ls(self, argv: list[str]) -> None:
        long_fmt = False
        paths: list[str] = []
        for arg in argv:
            if arg == "-l":
                long_fmt = True
            elif arg.startswith("-") and len(arg) > 1:
                raise VFSError(f"invalid option -- '{arg}'")
            else:
                paths.append(arg)
        if not paths:
            paths = [""]

        multi = len(paths) > 1
        for idx, p in enumerate(paths):
            if multi:
                if idx > 0:
                    print()
                print(f"{p or '.'}:")
            self._print_dir(p, long_fmt)

    def _print_dir(self, path: str, long_fmt: bool) -> None:
        names = self.vfs.list_dir(self.cwd, path)
        if not names:
            return
        if long_fmt:
            for n in names:
                child = self._join_path(path, n)
                info = self.vfs.stat(self.cwd, child)
                t = "d" if info["type"] == "directory" else "-"
                suffix = "/" if info["type"] == "directory" else ""
                print(f"{t} {info['size']:>6}  {n}{suffix}")
        else:
            out = []
            for n in names:
                child = self._join_path(path, n)
                info = self.vfs.stat(self.cwd, child)
                suffix = "/" if info["type"] == "directory" else ""
                out.append(n + suffix)
            print("  ".join(out))

    @staticmethod
    def _join_path(base: str, name: str) -> str:
        if not base:
            return name
        return base.rstrip("/") + "/" + name

    # ---------- cd ----------
    def cmd_cd(self, argv: list[str]) -> None:
        if len(argv) > 1:
            raise VFSError("too many arguments")
        target = self.vfs.normalize(self.cwd, argv[0] if argv else "/")
        if not self.vfs.is_dir(target):
            raise VFSError(f"not a directory: {argv[0] if argv else '/'}")
        self.cwd = target

    # ---------- cat ----------
    def cmd_cat(self, argv: list[str]) -> None:
        if not argv:
            raise VFSError("missing file operand")
        for path in argv:
            data = self.vfs.read_file(self.cwd, path)
            text = data.decode("utf-8", errors="replace")
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")

    # ---------- pwd ----------
    def cmd_pwd(self, argv: list[str]) -> None:
        print(self.cwd)

    # ---------- tree ----------
    def cmd_tree(self, argv: list[str]) -> None:
        if len(argv) > 1:
            raise VFSError("too many arguments")
        path = argv[0] if argv else ""
        target = self.vfs.normalize(self.cwd, path)
        print(target)
        for line in self.vfs.tree_lines(self.cwd, path):
            print(line)

    # ---------- history ----------
    def cmd_history(self, argv: list[str]) -> None:
        if argv and argv[0] == "-c":
            self.history.clear()
            return
        if len(argv) > 1:
            raise VFSError("too many arguments")

        if argv and argv[0].isdigit():
            n = int(argv[0])
            start = max(0, len(self.history) - n)
        else:
            start = 0

        width = len(str(len(self.history))) if self.history else 1
        for i, cmd in enumerate(self.history[start:], start=start + 1):
            print(f"{i:>{width}}  {shlex.join(cmd)}")

    # ---------- head ----------
    def cmd_head(self, argv: list[str]) -> None:
        n = 10
        files: list[str] = []
        i = 0
        while i < len(argv):
            arg = argv[i]
            if arg == "-n":
                i += 1
                if i >= len(argv):
                    raise VFSError("option requires an argument -- 'n'")
                try:
                    n = int(argv[i])
                except ValueError:
                    raise VFSError(f"invalid number of lines: {argv[i]}")
            elif arg.startswith("-n") and len(arg) > 2:
                try:
                    n = int(arg[2:])
                except ValueError:
                    raise VFSError(f"invalid number of lines: {arg[2:]}")
            elif (arg.startswith("-") and len(arg) > 1
                  and arg[1:].isdigit()):
                n = int(arg[1:])  # old-style: head -5 file
            elif arg.startswith("-") and arg != "-":
                raise VFSError(f"invalid option -- '{arg}'")
            else:
                files.append(arg)
            i += 1

        if not files:
            raise VFSError("missing file operand")
        if n < 0:
            raise VFSError(f"invalid number of lines: {n}")

        for f in files:
            data = self.vfs.read_file(self.cwd, f)
            text = data.decode("utf-8", errors="replace")
            lines = text.splitlines()
            for line in lines[:n]:
                print(line)

    # ---------- rev ----------
    def cmd_rev(self, argv: list[str]) -> None:
        if not argv:
            raise VFSError("missing file operand")
        for path in argv:
            data = self.vfs.read_file(self.cwd, path)
            text = data.decode("utf-8", errors="replace")
            for line in text.splitlines():
                print(line[::-1])

    def run_script(self) -> None:
        if not self.script_path:
            return
        if not os.path.isfile(self.script_path):
            print(f"error: startup script not found: {self.script_path}", file=sys.stderr)
            return

        print(f"--- Executing startup script: {self.script_path} ---")
        with open(self.script_path, "r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                line = raw.rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue

                print(f"{self.get_prompt()}{line}")
                try:
                    argv = self.parse(line)
                except ValueError as exc:
                    print(f"script:{lineno}: {exc}", file=sys.stderr)
                    continue
                if not argv:
                    continue
                if argv[0] not in self.COMMANDS:
                    print(f"script:{lineno}: {argv[0]}: command not found", file=sys.stderr)
                    continue
                try:
                    self.execute(argv)
                except Exception as exc:
                    print(f"script:{lineno}: runtime error: {exc}", file=sys.stderr)
                if not self.running:
                    break
        print("--- Startup script finished ---")

    # ---------- REPL ----------
    def repl(self) -> None:
        while self.running:
            try:
                line = input(self.get_prompt())
            except EOFError:  # Ctrl+D
                print()
                break
            except KeyboardInterrupt:  # Ctrl+C
                print()
                continue
            try:
                argv = self.parse(line)
            except ValueError as exc:
                print(exc, file=sys.stderr)
                continue
            self.execute(argv)

    def run(self, vfs_source: str) -> None:
        self.dump_config(vfs_source)
        if self.script_path:
            self.run_script()
        if self.running:
            self.repl()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="terminal",
        description="Эмулятор командной оболочки UNIX-подобной ОС (этап 3).",
    )
    parser.add_argument("--vfs",
                        required=True,
                        help="Путь к JSON-файлу с описанием VFS.",
                        )
    parser.add_argument("--script",
                        default=None,
                        help="Путь к стартовому скрипту.",
                        )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        vfs = VFS.from_file(args.vfs)
    except VFSError as exc:
        print(f"error: failed to load VFS: {exc}", file=sys.stderr)
        return 2
    Console(vfs=vfs, script_path=args.script).run(vfs_source=args.vfs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
