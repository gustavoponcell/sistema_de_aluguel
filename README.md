# RentalManager

Aplicativo desktop para gerenciamento de aluguéis, focado em uso offline no Windows.

## Como rodar em desenvolvimento

1) Crie e ative um ambiente virtual:

```bash
python -m venv .venv
.venv\\Scripts\\activate
```

2) Instale as dependências:

```bash
pip install -r requirements.txt
```

3) Execute o aplicativo:

```bash
python -m rental_manager.app
```

## Onde fica o banco de dados

O banco SQLite fica na pasta de dados do usuário, em `%APPDATA%\\RentalManager`.

## Build com PyInstaller

O processo de build com PyInstaller será detalhado em breve. A ideia é gerar um executável
na pasta `dist/` com todos os recursos necessários para uso offline.
