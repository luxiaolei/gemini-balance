from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config.config import settings
from app.log.logger import get_model_logger
from app.service.client.api_client import GeminiApiClient

logger = get_model_logger()


class ModelService:
    def _is_allowed_model(self, model_id: str) -> bool:
        if settings.FREE_TIER_ONLY and settings.FREE_TIER_MODELS:
            return model_id in settings.FREE_TIER_MODELS
        return True

    async def get_gemini_models(self, api_key: str) -> Optional[Dict[str, Any]]:
        api_client = GeminiApiClient(base_url=settings.BASE_URL)
        gemini_models = await api_client.get_models(api_key)

        if gemini_models is None:
            logger.error("从 API 客户端获取模型列表失败。")
            return None

        try:
            filtered_models_list = []
            for model in gemini_models.get("models", []):
                model_id = model["name"].split("/")[-1]
                if model_id in settings.FILTERED_MODELS:
                    logger.debug(f"Filtered out model: {model_id}")
                    continue
                if not self._is_allowed_model(model_id):
                    logger.debug(f"Filtered out non-free-tier model: {model_id}")
                    continue
                filtered_models_list.append(model)

            gemini_models["models"] = filtered_models_list
            return gemini_models
        except Exception as e:
            logger.error(f"处理模型列表时出错: {e}")
            return None

    async def get_gemini_openai_models(self, api_key: str) -> Optional[Dict[str, Any]]:
        """获取 Gemini 模型并转换为 OpenAI 格式"""
        gemini_models = await self.get_gemini_models(api_key)
        if gemini_models is None:
            return None
        
        return await self.convert_to_openai_models_format(gemini_models)

    async def convert_to_openai_models_format(
        self, gemini_models: Dict[str, Any]
    ) -> Dict[str, Any]:
        openai_format = {"object": "list", "data": [], "success": True}

        for model in gemini_models.get("models", []):
            model_id = model["name"].split("/")[-1]
            if not self._is_allowed_model(model_id):
                continue
            openai_model = {
                "id": model_id,
                "object": "model",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "owned_by": "google",
                "permission": [],
                "root": model["name"],
                "parent": None,
            }
            openai_format["data"].append(openai_model)

            if model_id in settings.SEARCH_MODELS:
                search_model = openai_model.copy()
                search_model["id"] = f"{model_id}-search"
                openai_format["data"].append(search_model)
            if model_id in settings.IMAGE_MODELS:
                image_model = openai_model.copy()
                image_model["id"] = f"{model_id}-image"
                openai_format["data"].append(image_model)
            if model_id in settings.THINKING_MODELS:
                non_thinking_model = openai_model.copy()
                non_thinking_model["id"] = f"{model_id}-non-thinking"
                openai_format["data"].append(non_thinking_model)

        if settings.CREATE_IMAGE_MODEL:
            if not self._is_allowed_model(settings.CREATE_IMAGE_MODEL):
                return openai_format
            if openai_format["data"]:
                image_model = openai_format["data"][0].copy()
            else:
                image_model = {
                    "id": settings.CREATE_IMAGE_MODEL,
                    "object": "model",
                    "created": int(datetime.now(timezone.utc).timestamp()),
                    "owned_by": "google",
                    "permission": [],
                    "root": settings.CREATE_IMAGE_MODEL,
                    "parent": None,
                }
            image_model["id"] = f"{settings.CREATE_IMAGE_MODEL}-chat"
            openai_format["data"].append(image_model)
        return openai_format

    async def check_model_support(self, model: str) -> bool:
        if not model or not isinstance(model, str):
            return False

        model = model.strip()
        if model.endswith("-search"):
            model = model[:-7]
            if model not in settings.SEARCH_MODELS:
                return False
        elif model.endswith("-image"):
            model = model[:-6]
            if model not in settings.IMAGE_MODELS:
                return False
        elif model.endswith("-non-thinking"):
            model = model[:-13]
            if model not in settings.THINKING_MODELS:
                return False
        elif model.endswith("-chat") and settings.CREATE_IMAGE_MODEL:
            if not model.startswith(settings.CREATE_IMAGE_MODEL):
                return False
            model = settings.CREATE_IMAGE_MODEL

        if model in settings.FILTERED_MODELS:
            return False
        if not self._is_allowed_model(model):
            return False
        return True
