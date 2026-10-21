"""Model task sizing policy, independent of connector implementations.

Character budgets are conservative planning estimates, not token capacities.
Unknown models never inherit the capacity of another model from its provider.
"""
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path


@dataclass(frozen=True)
class ModelProfile:
    input_characters: int = 60000
    extraction_characters: int = 12000
    output_tokens: int = 8192
    maximum_units: int = 20
    minimum_split_characters: int = 2500
    maximum_split_depth: int = 4
    adaptive: bool = True

    def __post_init__(self):
        bounds = {'input_characters': (12000, 2000000), 'extraction_characters': (2500, 1000000),
                  'output_tokens': (2048, 200000), 'maximum_units': (8, 80),
                  'minimum_split_characters': (500, 12000), 'maximum_split_depth': (0, 6)}
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'Model profile {name} must be between {low} and {high}.')
        if type(self.adaptive) is not bool:
            raise ValueError('Model profile adaptive must be true or false.')
        if self.extraction_characters > self.input_characters:
            raise ValueError('Extraction budget cannot exceed the input budget.')

    def as_dict(self):
        return asdict(self)


# Explicit connector defaults. These are app policies, not advertised capacities.
PROFILES = {
    ('codex', 'CLI default'): ModelProfile(extraction_characters=40000, output_tokens=16384, maximum_units=40),
    ('deepseek', 'deepseek-flash'): ModelProfile(output_tokens=32768),
}


def resolve_profile(provider, path: Path | None = None):
    supplied = getattr(provider, 'model_profile', None)
    if isinstance(supplied, ModelProfile):
        return supplied
    identity = (getattr(provider, 'name', 'unknown'), getattr(provider, 'model', 'default'))
    fallback_input = int(getattr(provider, 'max_input_chars', 60000))
    profile = PROFILES.get(identity, ModelProfile(input_characters=max(12000, fallback_input)))
    if path is not None and path.is_file():
        records = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(records, dict):
            raise ValueError('Model profiles must be an object keyed by provider:model.')
        override = records.get(':'.join(identity))
        if override is not None:
            if not isinstance(override, dict):
                raise ValueError('Each model profile must be an object.')
            profile = replace(profile, **override)
    return profile
