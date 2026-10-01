import os
import sys
import getpass
import socket
import shlex


class Console:
    def __init__(self):
        self.running = True
        self.prompt = "username@hostname:~$ "


    def repl(self):
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


    @staticmethod
    def parse(line : str) -> list[str]:
        try:
            return shlex.split(line)
        except ValueError as exc:
            raise ValueError(f"parse error: {exc}") from exc

    def get_prompt(self) -> str:
        user = getpass.getuser()
        host = socket.gethostname().split(".")[0]  # короткое имя хоста
        cwd = os.getcwd()
        home = os.path.expanduser("~")

        if cwd == home:
            display = "~"
        elif cwd.startswith(home + os.sep):
            display = "~" + cwd[len(home):]
        else:
            display = cwd

        self.prompt = f"{user}@{host}:{display}$ "
        return self.prompt

    '''COMMANDS'''
    def cmd_exit(self, argv: list[str]) -> None:
        self.running = False

    def cmd_ls(self, args : list[str]) -> None:
        print(f"ls: {args}")

    def cmd_cd(self, args : list[str]) -> None:
        print(f"cd: {args}")


def main():
    Console().repl()
    return 0


if __name__ == '__main__':
    main()