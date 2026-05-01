"""
Sample DeepSeek responses in DEVSEEK protocol format.

Used by multiple test modules.  Each constant is a complete, realistic
response that DevSeek's pipeline must handle correctly end-to-end.
"""

# ── Minimal responses ─────────────────────────────────────────────────────────

CHAT_ONLY = """\
[DEVSEEK_CHAT]
Apenas uma explicação, sem código.
[/DEVSEEK_CHAT]
[DEVSEEK_FIM]"""

NO_PROTOCOL = """\
Aqui está como fazer:

```python
def hello():
    return "Hello, World!"
```

Basta chamar `hello()` para obter o resultado.
"""

# ── Single file ───────────────────────────────────────────────────────────────

SINGLE_FILE_CREATE = """\
[DEVSEEK_CHAT]
Vou criar um arquivo Python simples com uma função de saudação.
[/DEVSEEK_CHAT]
[DEVSEEK_CREATE: hello.py]
```python
def hello(name: str = "World") -> str:
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(hello())
```
[/DEVSEEK_CREATE]
[DEVSEEK_FIM]"""

SINGLE_FILE_UPDATE = """\
[DEVSEEK_CHAT]
Vou atualizar o arquivo hello.py para aceitar um nome.
[/DEVSEEK_CHAT]
[DEVSEEK_UPDATE: hello.py]
```python
def hello(name: str = "DevSeek") -> str:
    return f"Olá, {name}!"
```
[/DEVSEEK_UPDATE]
[DEVSEEK_FIM]"""

# ── Multiple files (uses DEVSEEK_MAIS) ───────────────────────────────────────

MULTI_FILE_HTML_GAME = """\
[DEVSEEK_CHAT]
Vou criar um jogo simples de cartas com três arquivos.

Estrutura:
- index.html — estrutura
- style.css  — estilo
- game.js    — lógica
[/DEVSEEK_CHAT]
[DEVSEEK_CREATE: index.html]
```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Card Game</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="game"></div>
    <script src="game.js"></script>
</body>
</html>
```
[/DEVSEEK_CREATE]
[DEVSEEK_MAIS]
[DEVSEEK_CREATE: style.css]
```css
body {
    margin: 0;
    background: #1a1a2e;
    color: white;
    font-family: sans-serif;
}
#game {
    display: flex;
    justify-content: center;
    padding: 40px;
}
```
[/DEVSEEK_CREATE]
[DEVSEEK_MAIS]
[DEVSEEK_CREATE: game.js]
```javascript
const game = document.getElementById('game');
game.innerHTML = '<h1>Card Game</h1><p>Em desenvolvimento...</p>';
```
[/DEVSEEK_CREATE]
[DEVSEEK_FIM]"""

# ── MKDIR + CREATE combo ──────────────────────────────────────────────────────

MKDIR_THEN_CREATE = """\
[DEVSEEK_CHAT]
Criando a pasta utils e um arquivo dentro dela.
[/DEVSEEK_CHAT]
[DEVSEEK_MKDIR: utils]
[DEVSEEK_CREATE: utils/helpers.py]
```python
def slugify(text: str) -> str:
    return text.lower().replace(" ", "-")
```
[/DEVSEEK_CREATE]
[DEVSEEK_FIM]"""

# ── REPLACE (patch) ───────────────────────────────────────────────────────────

REPLACE_PATCH = """\
[DEVSEEK_CHAT]
Vou corrigir apenas a linha do retorno.
[/DEVSEEK_CHAT]
[DEVSEEK_REPLACE: hello.py]
SEARCH:
    return f"Hello, {name}!"
REPLACE:
    return f"Olá, {name}! 👋"
[/DEVSEEK_REPLACE]
[DEVSEEK_FIM]"""

# ── UI noise pollution (old web extraction) ───────────────────────────────────

WITH_UI_NOISE = """\
[DEVSEEK_CHAT]
Aqui está o arquivo com ruído de UI.
[/DEVSEEK_CHAT]
[DEVSEEK_CREATE: noisy.py]
Copiar
```python
x = 1
```
Baixar
[/DEVSEEK_CREATE]
[DEVSEEK_FIM]"""

# ── Partial / unclosed (simulates mid-stream capture) ────────────────────────

PARTIAL_UNCLOSED = """\
[DEVSEEK_CHAT]
Vou criar dois arquivos.
[/DEVSEEK_CHAT]
[DEVSEEK_CREATE: a.py]
```python
# arquivo A
x = 1"""

PARTIAL_MAIS_PENDING = """\
[DEVSEEK_CHAT]
Criando dois arquivos.
[/DEVSEEK_CHAT]
[DEVSEEK_CREATE: a.py]
```python
x = 1
```
[/DEVSEEK_CREATE]
[DEVSEEK_MAIS]"""

# ── Expected parsed content for assertions ────────────────────────────────────

# Content of each file after parsing MULTI_FILE_HTML_GAME
EXPECTED_HTML = """\
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Card Game</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="game"></div>
    <script src="game.js"></script>
</body>
</html>"""

EXPECTED_CSS = """\
body {
    margin: 0;
    background: #1a1a2e;
    color: white;
    font-family: sans-serif;
}
#game {
    display: flex;
    justify-content: center;
    padding: 40px;
}"""

EXPECTED_JS = """\
const game = document.getElementById('game');
game.innerHTML = '<h1>Card Game</h1><p>Em desenvolvimento...</p>';"""
