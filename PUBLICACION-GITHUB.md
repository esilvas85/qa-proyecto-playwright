# Publicación del proyecto QA en GitHub

Nombre público: **qa-proyecto-playwright**  
Cuenta: **esilvas85**  
URL final prevista: https://github.com/esilvas85/qa-proyecto-playwright

1. Accede a https://github.com/new con tu cuenta.
2. Nombre: `qa-proyecto-playwright` y visibilidad: **Public**.
3. Desmarca crear README, `.gitignore` y licencia.
4. Crea el repositorio vacío.
5. Descomprime este archivo en una carpeta propia y ejecuta desde PowerShell:

```powershell
cd "$HOME\qa-proyecto-playwright"
git init -b main
git add .
git commit -m "Publicación inicial - QA Senior Playwright"
git remote add origin https://github.com/esilvas85/qa-proyecto-playwright.git
git push -u origin main
```

El repositorio incluye las 16 evidencias de la última ejecución y el estado INCONCLUSO del escenario adicional Hyundai, sin modificarlo. Si falla `git commit` porque falta identidad, configura `git config --global user.name` y `git config --global user.email` usando tus datos de GitHub.

No subas `.venv`, resultados temporales de `salidas/`, contraseñas ni tokens. `.gitignore` excluye los archivos temporales habituales.
