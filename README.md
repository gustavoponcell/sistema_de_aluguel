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

## Como mudar o tema

Abra o menu **Exibir > Tema** e escolha entre **Claro**, **Escuro** ou **Sistema**.
A preferência é salva em `%APPDATA%\\RentalManager\\config.json` e aplicada
imediatamente (sem precisar reiniciar). Se o modo **Sistema** estiver selecionado,
o app segue o tema do Windows; caso a detecção falhe, o tema claro é usado.

## Build com PyInstaller

### Pré-requisitos

1) Instale as dependências do projeto:

```bash
pip install -r requirements.txt
```

2) Instale o PyInstaller:

```bash
pip install pyinstaller
```

### Comando de build (Windows)

Use o script PowerShell já configurado:

```powershell
.\build_windows.ps1
```

O script gera automaticamente um ícone mínimo em `assets\icon.ico` caso o arquivo não exista.
Para personalizar, substitua o ícone por um `.ico` próprio.

Ou execute o comando diretamente:

```powershell
pyinstaller --noconsole --name RentalManager --icon assets/icon.ico --add-data "assets;assets" --paths "src" --clean --noconfirm src/rental_manager/app.py
```

### Onde fica o executável

O executável principal será gerado em:

```
dist\RentalManager\RentalManager.exe
```

### Como instalar (uso offline)

1) Copie a pasta inteira `dist\RentalManager` para o computador de destino.
2) Execute `RentalManager.exe` diretamente (não requer instalação).

### Checklist pós-build

- Abrir o executável e confirmar que não aparece console.
- Confirmar criação do banco em `%APPDATA%\RentalManager\rental_manager.db`.
- Confirmar criação de logs em `%APPDATA%\RentalManager\logs\`.
- Criar um aluguel de teste e gerar PDF em `%APPDATA%\RentalManager\pdfs\`.
- Executar backup e verificar arquivo em `%APPDATA%\RentalManager\backups\`.
