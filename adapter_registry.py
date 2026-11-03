"""Discover built-ins and trusted user adapters, with deterministic validation."""
import importlib.util
import os
from pathlib import Path
import sys
from adapter_api import Adapter

ROOT = Path(__file__).resolve().parent


def adapter_directories():
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    directories = [ROOT / 'adapters', config / 'tmux-agent-resurrect/adapters']
    directories += [Path(p).expanduser() for p in os.environ.get('AGENT_RESURRECT_ADAPTER_DIR', '').split(os.pathsep) if p]
    return list(dict.fromkeys(p.resolve() for p in directories))


def load_adapters(directories=None):
    adapters = {}
    for directory in adapter_directories() if directories is None else directories:
        for path in sorted(Path(directory).glob('*.py')):
            if path.name.startswith('_'):
                continue
            module_name = '_agent_adapter_' + str(len(adapters))
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
                adapter = module.ADAPTER
                if not isinstance(adapter, Adapter):
                    raise TypeError('ADAPTER must be an adapter_api.Adapter')
                adapter.validate()
                if adapter.name in adapters:
                    raise ValueError(f'duplicate adapter name: {adapter.name}')
                adapters[adapter.name] = adapter
            except Exception as error:
                raise ValueError(f'Cannot load adapter {path}: {error}') from error
    return list(adapters.values())
