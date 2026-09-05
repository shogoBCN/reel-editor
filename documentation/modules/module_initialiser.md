# Module initialiser

Singleton + lazy load for shared modules. Same pattern as Locaria `adaptria_pulls`.

**Implementation:** [modules/modules_initialiser.py](../../modules/modules_initialiser.py)

```python
from modules.modules_initialiser import get_module

config_store = get_module("config_store")
gemini_client = get_module("gemini_client")
```

Supported names: `config_store`, `gemini_client`. Add new shared clients here instead of constructing them in each pipeline.
