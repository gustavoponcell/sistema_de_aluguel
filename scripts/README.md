# Scripts de utilidade

## Seed de dados de demonstração

O script `seed_demo_data.py` gera um conjunto realista de produtos, clientes, aluguéis, itens e (se existir) pagamentos para testar o sistema como um todo.

### Como executar

Na raiz do repositório:

```bash
python scripts/seed_demo_data.py
```

Ou via módulo:

```bash
python -m scripts.seed_demo_data
```

### Flags disponíveis

- `--reset`: apaga dados das tabelas principais antes de inserir.
- `--dry-run`: não grava no banco; apenas simula e imprime o resumo.
- `--seed N`: controla a aleatoriedade (padrão: 42).

### Observações

- O script detecta automaticamente o caminho do banco SQLite usado pelo app.
- Por segurança, ele pede confirmação antes de inserir dados (exceto em `--dry-run`).
- Para evitar duplicações, os registros gerados usam o prefixo `Seed Demo`.
