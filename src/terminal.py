import argparse
import os
import sys
import getpass
import socket
import shlex


class Console:
    def __init__(self, vfs_root: str, script_path: str | None = None) -> None:
        self.running = True
        self.prompt = "username@hostname:~$ "
        self.vfs_root = os.path.abspath(vfs_root)
        self.script_path = os.path.abspath(script_path) if script_path else None
        self.cwd = "/"  # логический путь внутри vfs


    def dump_config(self) -> None:
        print("=== Shell Emulator: configuration ===")
        print(f"VFS root       : {self.vfs_root}")
        print(f"VFS exists     : {os.path.isdir(self.vfs_root)}")
        print(f"Startup script : {self.script_path or '<none>'}")
        print("=========================================")


    def get_prompt(self) -> str:
        user = getpass.getuser()
        host = socket.gethostname().split(".")[0]  # короткое имя хоста
        self.prompt = f"{user}@{host}:{self.cwd}$ "
        return self.prompt


    @staticmethod
    def parse(line : str) -> list[str]:
        try:
            return shlex.split(line)
        except ValueError as exc:
            raise ValueError(f"parse error: {exc}") from exc


    def execute(self, argv: list[str]) -> None:
        if not argv:
            return

        cmd, args = argv[0], argv[1:]
        handlers = {
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "exit": self.cmd_exit,
        }
        handler = handlers.get(cmd)
        if handler is None:
            print(f"{cmd}: command not found", file=sys.stderr)
            return

        handler(args)


    '''COMMANDS'''
    def cmd_exit(self, argv: list[str]) -> None:
        self.running = False

    def cmd_ls(self, args : list[str]) -> None:
        print(f"ls: {args}")

    def cmd_cd(self, args : list[str]) -> None:
        print(f"cd: {args}")


    def run_script(self) -> None:
        if not self.script_path:
            return
        if not os.path.isfile(self.script_path):
            print(f"{self.script_path}: file not found", file=sys.stderr)
            return

        print(f"--- Executing startup script: {self.script_path} ---")
        with open(self.script_path, "r") as f:
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

                if argv[0] not in ['ls', 'cd', 'exit']:
                    print(f"script:{lineno}: {argv[0]}: command not found", file=sys.stderr)
                    continue

                try:
                    self.execute(argv)
                except Exception as exc:
                    print(f"script:{lineno}: runtime error: {exc}", file=sys.stderr)

                if not self.running:
                    break

        print("--- Startup script finished ---")



    def repl(self) -> None:
        while self.running:
            try:
                line = input(self.get_prompt())
            except EOFError:    # Ctrl+D
                print()
                break
            except KeyboardInterrupt:   # Ctrl+C
                print()
                continue

            try:
                argv = self.parse(line)
            except ValueError as exc:
                print(exc, file=sys.stderr)
                continue

            self.execute(argv)

    def run(self) -> None:
        self.dump_config()
        if self.script_path:
            self.run_script()
        if self.running:
            self.repl()




def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="terminal",
        description="Эмулятор командной оболочки UNIX-подобной ОС (этап 2).",
    )
    parser.add_argument("--vfs",
                        required=True,
                        help="Путь к физическому расположению VFS (корень виртуальной ФС).",
    )
    parser.add_argument("--script",
                        default=None,
                        help="Путь к стартовому скрипту с командами эмулятора.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not os.path.isdir(args.vfs):
        print(f"error: VFS path does not exist or is not a directory: {args.vfs}", file=sys.stderr)
        return 2

    Console(vfs_root=args.vfs, script_path=args.script).run()
    return 0


if __name__ == '__main__':
    sys.exit(main())