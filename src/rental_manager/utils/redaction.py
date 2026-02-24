"""Utility helpers to redact sensitive fields before sending to the AI provider."""

from __future__ import annotations

import re

CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CPF_DIGIT_PATTERN = re.compile(r"\b\d{11}\b")

GENERIC_TOPICS = {
    "agenda": ("agenda", "calendário", "calendario"),
    "contratos": ("contrato", "contratos", "recibo"),
    "financeiro": ("financeiro", "pagamento", "pagamentos", "receber"),
    "estoque": ("estoque", "itens", "produtos"),
    "backup": ("backup", "restaurar", "restore"),
    "clientes": ("cliente", "clientes", "cadastro"),
}


def redact_text(text: str) -> str:
    """Mask only CPF identifiers, preserving demais campos."""
    masked = CPF_PATTERN.sub("[cpf]", text)
    masked = CPF_DIGIT_PATTERN.sub("[cpf]", masked)
    return masked


def build_generic_context(user_text: str) -> str:
    """Return a limited context string derived from keywords only."""
    lowered = user_text.lower()
    topics: list[str] = []
    for label, keywords in GENERIC_TOPICS.items():
        if any(keyword in lowered for keyword in keywords):
            topics.append(label)
    if not topics:
        return (
            "Contexto restrito: o usuário preferiu não compartilhar detalhes. "
            "Forneça orientações gerais sobre o uso do sistema de aluguel."
        )
    topics_str = ", ".join(topics)
    return (
        "Contexto restrito: o usuário está consultando os módulos de "
        f"{topics_str} e não enviou dados sensíveis. Responda com orientações gerais."
    )
