from ..catalog import family_of
from .ark import ArkAdapter
from .dashscope import DashScopeAdapter
from .minimax import MiniMaxAdapter
from .openai_image import OpenAIImageAdapter

_ADAPTERS = {
    "ark": ArkAdapter(),
    "dashscope": DashScopeAdapter(),
    "minimax": MiniMaxAdapter(),
    "openai_image": OpenAIImageAdapter(),
}


def get_adapter(model_id):
    fam = family_of(model_id)
    if fam is None:
        raise KeyError(f"No adapter for model '{model_id}'. This package does not know how to call it yet; "
                       "update the package or pick another model.")
    return _ADAPTERS[fam]
