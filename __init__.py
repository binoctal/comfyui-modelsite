"""Modelsite ComfyUI node pack: video and image generation nodes with a dynamic model list."""

WEB_DIRECTORY = "./web"
__all__ = ["comfy_entrypoint", "WEB_DIRECTORY"]

# `__package__` is empty when a tool (e.g. pytest) imports this file as a top-level module instead of
# ComfyUI loading it as a package; skip the ComfyUI wiring in that case.
if __package__:
    from .modelsite.comfy_nodes import ModelsiteExtension

    def _register_routes():
        try:
            from server import PromptServer

            from .modelsite import routes

            routes.register(PromptServer.instance.routes)
        except Exception as e:  # ComfyUI server not available or routes already registered
            print(f"[Modelsite] settings routes not registered: {e}")

    _register_routes()

    async def comfy_entrypoint() -> ModelsiteExtension:
        return ModelsiteExtension()
