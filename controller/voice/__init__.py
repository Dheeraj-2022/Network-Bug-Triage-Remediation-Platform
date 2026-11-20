"""
Secure, bounded conversational voice-first operations assistant for NetResolve AI.
"""

from typing import Any, Optional

from controller.voice.agent import ALL_ALLOWED_INTENTS, ConversationalOpsAgent, voice_allow_ansible
from controller.voice.audit import VoiceAuditStore
from controller.voice.auth import VoiceAuthManager, VoicePrincipal
from controller.voice.conversation import ConversationState, ConversationStore
from controller.voice.engine import VoiceAssistant
from controller.voice.intents import ALLOWED_INTENTS, parse_intent
from controller.voice.security import detect_prompt_injection, redact_obj, redact_secrets

_ASSISTANT: Optional[VoiceAssistant] = None


def get_voice_assistant(service: Any) -> VoiceAssistant:
    global _ASSISTANT
    if _ASSISTANT is None:
        _ASSISTANT = VoiceAssistant(service=service)
    return _ASSISTANT


__all__ = [
    "ALL_ALLOWED_INTENTS",
    "ALLOWED_INTENTS",
    "ConversationalOpsAgent",
    "ConversationState",
    "ConversationStore",
    "VoiceAssistant",
    "VoiceAuditStore",
    "VoiceAuthManager",
    "VoicePrincipal",
    "detect_prompt_injection",
    "get_voice_assistant",
    "parse_intent",
    "redact_obj",
    "redact_secrets",
    "voice_allow_ansible",
]
