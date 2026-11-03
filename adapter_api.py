"""Public, dependency-free API for CLI adapters. See examples/example_agent.py."""
from dataclasses import dataclass
from typing import Callable, Optional, Tuple
import re


@dataclass(frozen=True)
class Resolution:
    session_id: Optional[str]
    method: str


@dataclass(frozen=True)
class Context:
    pane_id: str
    title: str
    cwd: str
    pids: Tuple[int, ...]
    run: Callable


@dataclass(frozen=True)
class Adapter:
    name: str
    process_names: Tuple[str, ...]
    session_id_pattern: str
    resume_argv: Tuple[str, ...]
    resolve: Callable[[Context], Resolution]

    def validate(self):
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', self.name):
            raise ValueError('Adapter name must be a lowercase identifier')
        if not self.process_names or any(not p or '/' in p for p in self.process_names):
            raise ValueError(f'{self.name}: process_names must contain executable basenames')
        re.compile(self.session_id_pattern)
        if '{session_id}' not in self.resume_argv or not callable(self.resolve):
            raise ValueError(f'{self.name}: need a resolver and a {{session_id}} argument')
        for arg in self.resume_argv:
            if not isinstance(arg, str) or any(c in arg for c in '\r\n\t'):
                raise ValueError(f'{self.name}: resume_argv must contain single-line strings')
            if ('{' in arg or '}' in arg) and arg not in ('{session_id}', '{cwd}'):
                raise ValueError(f'{self.name}: placeholders must be whole arguments')
        # tmux-resurrect interprets this prefix as a regex. A simple command and
        # flags keep it literal, without shell or regex metacharacters.
        prefix = self.restore_prefix
        if not prefix or any(not re.fullmatch(r'[A-Za-z0-9_-]+', a) for a in prefix.split(' ')):
            raise ValueError(f'{self.name}: prefix must be a command/flags in PATH, without shell syntax')
        return self

    @property
    def restore_prefix(self):
        prefix = []
        for arg in self.resume_argv:
            if arg in ('{session_id}', '{cwd}'):
                break
            prefix.append(arg)
        return ' '.join(prefix)

    def command(self, session_id, cwd):
        if not isinstance(session_id, str) or not session_id or not re.fullmatch(self.session_id_pattern, session_id):
            raise ValueError(f'{self.name}: invalid session ID')
        values = {'{session_id}': session_id, '{cwd}': cwd}
        args = [values.get(arg, arg) for arg in self.resume_argv]
        if any(any(char in arg for char in "\r\n\t") for arg in args):
            raise ValueError(f'{self.name}: snapshot arguments must be single-line strings')
        return args
