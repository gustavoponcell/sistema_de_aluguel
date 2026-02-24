"""Tests for text redaction utilities."""

from __future__ import annotations

import unittest

from rental_manager.utils.redaction import build_generic_context, redact_text


class RedactionTests(unittest.TestCase):
    def test_masks_only_cpf(self) -> None:
        text = (
            "Cliente João ligou (11) 99999-8888 e enviou CPF 123.456.789-00, "
            "CNPJ 12.345.678/0001-90, email teste@example.com."
        )
        redacted = redact_text(text)
        self.assertIn("[cpf]", redacted)
        self.assertNotIn("123.456.789-00", redacted)
        # other dados permanecem
        self.assertIn("(11) 99999-8888", redacted)
        self.assertIn("teste@example.com", redacted)
        self.assertIn("12.345.678/0001-90", redacted)

    def test_build_generic_context(self) -> None:
        context = build_generic_context("Quero ajuda na Agenda e gerar contrato.")
        self.assertIn("agenda", context)
        self.assertIn("contratos", context)


if __name__ == "__main__":
    unittest.main()
